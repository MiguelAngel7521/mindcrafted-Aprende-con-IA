"""Closed structured dispatch. No model-controlled filesystem or runtime authority."""
from copy import deepcopy
from dataclasses import dataclass
from typing import Literal
from uuid import uuid4
import asyncio
import json
import time

from pydantic import Field

from .knowledge_features import build_structure_graph, LearningObjective
from .mechanic_selector import MechanicSelector
from .structured_schema import schema_hash
from .world_schema import Data, Id, Text, Blueprint, BossBlueprint


class EmptyArguments(Data):
    pass


class SelectionArguments(Data):
    objectiveId: Id
    text: Text
    relationIds: list[Id] = Field(min_length=1, max_length=1024)
    intent: Literal['explore', 'connect', 'distribute', 'configure']
    mode: Literal['AUTO', 'node_connect', 'resource_balance', 'machine_configuration']


class DesignArguments(Data):
    objectiveId: Id
    blueprint: Blueprint


class BossArguments(Data):
    blueprint: BossBlueprint


@dataclass(frozen=True)
class Budgets:
    max_provider_retries: int = 2
    max_repairs: int = 2
    max_tool_calls: int = 40
    provider_timeout: float = 120
    tool_timeout: float = 180
    total_timeout: float = 900
    max_output_bytes: int = 300000

    def __post_init__(self):
        for name in ('max_provider_retries','max_repairs'):
            if type(getattr(self,name)) is not int or not 0 <= getattr(self,name) <= 10:
                raise ValueError('INVALID_BUDGET')
        for name in ('max_tool_calls','max_output_bytes'):
            if type(getattr(self,name)) is not int or getattr(self,name) <= 0:
                raise ValueError('INVALID_BUDGET')
        import math
        if any(not math.isfinite(v) or v <= 0 for v in
               (self.provider_timeout,self.tool_timeout,self.total_timeout)):
            raise ValueError('INVALID_BUDGET')


@dataclass(frozen=True)
class Tool:
    name: str
    permission: str
    arguments: type[Data]
    description: str


TOOLS = (
    Tool('analyze_material', 'ANALYZE', EmptyArguments, 'Analyze the immutable source.'),
    Tool('select_mechanic', 'PLAN', SelectionArguments,
         'Select an eligible mechanic for source-grounded objective references.'),
    Tool('design_world', 'DESIGN', DesignArguments, 'Submit a declarative world for a selected objective.'),
    Tool('design_boss', 'DESIGN', BossArguments, 'Compose existing taught archetypes.'),
    Tool('repair_world', 'REPAIR', DesignArguments, 'Replace the rejected candidate.'),
    Tool('repair_boss', 'REPAIR', BossArguments, 'Replace the rejected composed boss.'),
    Tool('validate_blueprint', 'VALIDATE', EmptyArguments, 'Confirm candidate validation.'),
    Tool('solve_world', 'SOLVE', EmptyArguments, 'Read the compiler solver proof.'),
    Tool('run_quality_gate', 'VALIDATE', EmptyArguments, 'Run all deterministic and browser checks.'),
    Tool('judge_candidate', 'REVIEW', EmptyArguments, 'Request review only after deterministic PASS.'),
    Tool('package_campaign', 'PACKAGE', EmptyArguments, 'Package the current approved snapshot.'),
    Tool('compile_world', 'COMPILE', EmptyArguments, 'Compile the current candidate using deterministic validation.'),
)


def tool_registry():
    """Return detached API schemas; callers cannot mutate the dispatch table."""
    return [{'name': t.name, 'permission': t.permission, 'description': t.description,
             'parameters': t.arguments.model_json_schema()} for t in TOOLS]


class AgentSession:
    """Application owns source and identity. Tools receive only closed arguments.

    Analysis, selection, design and compilation reuse the canonical contracts.
    Publication is an application-owned operation after all gates.
    """
    def __init__(self, source, *, provider='none', model='none', budgets=None, previous_lessons=()):
        if not isinstance(source, str) or not 60 <= len(source.strip()) <= 60000:
            raise ValueError('SOURCE_ERROR: expected 60–60000 characters')
        self.budgets = budgets or Budgets()
        self._started = time.monotonic()
        self.state = 'NEW'
        self.repairs = 0
        self._calls = 0
        self._busy = False
        self._boss = False
        self._proof = self._gate = self._judge = self._package = None
        self._review = None
        self._test_only = True
        self._previous_lessons=deepcopy(previous_lessons)
        self._prior_skills = set()
        self._prior_real = True
        from .world import validate_world, world_hash
        from .world_package import CHECKS, check_judge
        for package, material in deepcopy(previous_lessons):
            report = validate_world(package['world'], material)
            if not report['ok'] or not set(package['world'].get('priorSkills',[])) <= self._prior_skills:
                raise ValueError('INVALID_PRIOR_LESSON')
            quality=package.get('quality',{})
            try:
                real=(quality.get('approved') is True and all(quality.get('checks',{}).get(k) is True for k in CHECKS)
                      and quality.get('worldHash')==world_hash(package['world']) and check_judge(quality.get('judge')))
            except (ValueError,KeyError,TypeError):
                real=False
            self._prior_real = self._prior_real and real
            self._prior_skills.update(r['skill'] for p in package['world']['puzzles'] for r in p['knowledge']['requiredRules'])
        self._source = source
        self._graph = None
        self._selections = {}
        self._objectives = {}
        self._candidate = None
        self._world = None
        self._audit = []
        self._provider, self._model = provider, model
        self.generation_id = str(uuid4())

    @property
    def audit(self):
        return deepcopy(self._audit)

    def assert_budget(self):
        if time.monotonic()-self._started >= self.budgets.total_timeout:
            self.state='REJECTED'
            raise ValueError('TOTAL_EXECUTION_EXHAUSTED')

    def invalidate(self):
        self._candidate = self._world = self._proof = self._gate = self._judge = self._package = None

    async def dispatch(self, name, arguments):
        if self._busy:
            raise ValueError('INVALID_AGENT_TRANSITION: concurrent tool call')
        self._busy=True
        try:
            remaining=self.budgets.total_timeout-(time.monotonic()-self._started)
            return await asyncio.wait_for(self._dispatch(name, arguments),
                max(.000001,min(self.budgets.tool_timeout,remaining)))
        except TimeoutError:
            self.invalidate()
            self.state='REJECTED'
            if self._audit:
                self._audit[-1].update(result='REJECTED',errorCategory='TOOL_TIMEOUT',stateAfter='REJECTED')
            raise
        finally:
            self._busy=False

    async def _dispatch(self, name, arguments):
        tool = next((t for t in TOOLS if t.name == name), None)
        # Unknown caller-controlled names are not copied into audit metadata.
        started=time.monotonic()
        event = {'state':self.state,'repairNumber':self.repairs,'generationId': self.generation_id, 'tool': tool.name if tool else 'UNKNOWN',
                 'provider': self._provider, 'model': self._model, 'step': len(self._audit)+1,
                 'attempt': 1, 'schemaVersion': 'agent-tools-1', 'result': 'REJECTED',
                 'errorCategory': None, 'inputHash': None, 'outputHash': None}
        try:
            self.assert_budget()
            self._calls += 1
            if self._calls > self.budgets.max_tool_calls:
                self.state='REJECTED'
                raise ValueError('TOOL_BUDGET_EXHAUSTED')
            if self.state in ('PACKAGED','PUBLISHED','REJECTED'):
                raise ValueError('INVALID_AGENT_TRANSITION')
            if self.state=='REPAIR_REQUIRED' and not name.startswith('repair_'):
                raise ValueError('INVALID_AGENT_TRANSITION / TOOL_PRECONDITION: repair required')
            if name=='analyze_material' and self.state not in ('NEW','ANALYZED'):
                raise ValueError('INVALID_AGENT_TRANSITION')
            if tool is None:
                raise ValueError('TOOL_NOT_ALLOWED')
            if not isinstance(arguments, dict):
                raise ValueError('TOOL_ARGUMENTS_INVALID')
            if len(json.dumps(arguments).encode()) > self.budgets.max_output_bytes:
                self.state='REJECTED'
                raise ValueError('OUTPUT_SIZE_EXCEEDED')
            event['inputHash'] = schema_hash(arguments)
            if name.startswith('repair_'):
                if self.state!='REPAIR_REQUIRED':
                    raise ValueError('INVALID_AGENT_TRANSITION: no diagnostic to repair')
                self.invalidate()
                if self.repairs >= self.budgets.max_repairs:
                    self.state='REJECTED'
                    raise ValueError('REPAIR_BUDGET_EXHAUSTED')
                self.repairs += 1
            elif name.startswith('design_'):
                self.invalidate()
                if self.state=='REPAIR_REQUIRED':
                    raise ValueError('INVALID_AGENT_TRANSITION: use repair')
            required={'run_quality_gate':{'SOLVED'},'solve_world':{'COMPILED'},
                      'judge_candidate':{'GATED'},'package_campaign':{'JUDGED'},
                      'compile_world':{'VALIDATED'},'validate_blueprint':{'VALIDATED'}}
            if name in required and self.state not in required[name]:
                raise ValueError('INVALID_AGENT_TRANSITION / TOOL_PRECONDITION: '+name)
            args = tool.arguments.model_validate(arguments)
            if name == 'analyze_material':
                self._graph = build_structure_graph(self._source)
                self.invalidate()
                self._selections.clear(); self._objectives.clear()
                self.state='ANALYZED'
                result = self._graph
            elif name == 'select_mechanic':
                if self._graph is None:
                    raise ValueError('TOOL_PRECONDITION: analyze material first')
                objective = LearningObjective(args.objectiveId, args.text,
                    relation_ids=tuple(args.relationIds), intent=args.intent)
                result = MechanicSelector().select(self._graph, self._source, objective, mode=args.mode)
                self._selections[objective.id] = deepcopy(result)
                self._objectives[objective.id] = objective
                self.invalidate()
                self.state='PLANNED'
            elif name in ('design_world','repair_world'):
                # Invalidate earlier derived state even if a replacement is rejected.
                self._candidate = self._world = None
                selection = self._selections.get(args.objectiveId)
                if not selection or selection['status'] != 'SELECTED':
                    raise ValueError('TOOL_PRECONDITION: select an eligible objective first')
                candidate = args.blueprint.model_dump()
                from .mechanic_selector import verify_objective_binding
                from .world import validate_mechanics
                for puzzle in candidate['puzzles']:
                    if puzzle['mechanics']['archetype'] != selection['selectedMechanic']:
                        raise ValueError('INELIGIBLE_MECHANIC')
                    verify_objective_binding(puzzle, self._graph, self._objectives[args.objectiveId])
                    validate_mechanics(puzzle, self._source)
                self._candidate = candidate
                self._boss=False
                self.state='VALIDATED'
                result = {'candidateHash': schema_hash(candidate)}
            elif name == 'compile_world':
                if self._candidate is None:
                    raise ValueError('TOOL_PRECONDITION: design a valid candidate first')
                from .agent_execution import worker
                from .world import world_hash
                compiled=await worker({'operation':'compile','candidate':self._candidate,'source':self._source,
                    'boss':self._boss,'priorSkills':sorted(self._prior_skills)},
                    min(self.budgets.tool_timeout,self.budgets.total_timeout-(time.monotonic()-self._started)))
                self._world,self._proof=compiled['world'],compiled['report']
                self.state='COMPILED'
                result={'worldHash':world_hash(self._world),'checks':self._proof['checks']}
            elif name in ('design_boss','repair_boss'):
                if self._graph is None:
                    raise ValueError('TOOL_PRECONDITION: analyze first')
                self._candidate=args.blueprint.model_dump()
                self._boss=True
                # Composed solver validates each phase's eligibility and all outgoing branches.
                from .agent_execution import worker
                await worker({'operation':'compile','candidate':self._candidate,'source':self._source,
                    'boss':True,'priorSkills':sorted(self._prior_skills)},
                    min(self.budgets.tool_timeout,self.budgets.total_timeout-(time.monotonic()-self._started)))
                self.state='VALIDATED'
                result={'candidateHash':schema_hash(self._candidate)}
            elif name=='validate_blueprint':
                result={'candidateHash':schema_hash(self._candidate),'validated':True}
            elif name=='solve_world':
                result={'solutions':self._proof['solutions'],'boss':self._proof['boss']}
                self.state='SOLVED'
            elif name=='run_quality_gate':
                from .agent_execution import worker
                from .world_package import CHECKS
                self._gate=await worker({'operation':'gate','world':self._world,'source':self._source},
                    min(self.budgets.tool_timeout,self.budgets.total_timeout-(time.monotonic()-self._started)))
                if self._gate['errors'] or not all(self._gate['checks'].get(k) is True for k in CHECKS):
                    raise ValueError('DETERMINISTIC_GATE_FAILURE: '+'; '.join(self._gate['errors']))
                self.state='GATED'
                result=self._gate
            elif name=='judge_candidate':
                if self._review is None:
                    raise ValueError('JUDGE_NOT_CONFIGURED')
                from .world_package import check_judge
                from .world import world_hash
                if self._gate['worldHash']!=world_hash(self._world):
                    raise ValueError('CANDIDATE_CHANGED')
                self._judge=await self._review(self._world,self._gate)
                if not check_judge(self._judge):
                    raise ValueError('AI_JUDGE_REJECTION')
                self.state='JUDGED'
                result={'accepted':True,'authority':'TEST_ONLY_JUDGE' if self._test_only else 'REAL_JUDGE'}
            elif name=='package_campaign':
                from .world_package import make_package, CHECKS, check_judge
                from .world import world_hash
                if (self._gate['worldHash']!=world_hash(self._world) or self._gate['errors']
                    or not all(self._gate['checks'].get(k) is True for k in CHECKS) or not check_judge(self._judge)):
                    raise ValueError('PUBLICATION_REJECTED')
                if not self._test_only and not self._prior_real:
                    raise ValueError('PRIOR_LESSONS_NOT_APPROVED')
                self._package=make_package(self._world,self._source)
                self._package['developmentDemo']=self._test_only
                self._package['quality']=dict(deepcopy(self._gate),approved=not self._test_only,
                    judge=deepcopy(self._judge),judgeAuthority='TEST_ONLY_JUDGE' if self._test_only else 'REAL_JUDGE')
                if self._previous_lessons:
                    from .world_campaign import assemble_campaign
                    previous=[deepcopy(p) for p,_ in self._previous_lessons]
                    if self._test_only:
                        for p in previous: p['developmentDemo']=True
                    self._package=assemble_campaign(previous+[self._package],
                        course_id='agent_'+self.generation_id.replace('-',''),development=self._test_only)
                self._package_hash=schema_hash(self._package)
                self.state='PACKAGED'
                result={'worldHash':world_hash(self._world),'status':'TEST_ONLY_PACKAGE' if self._test_only else 'READY_FOR_PUBLICATION'}
            else:
                raise ValueError('TOOL_NOT_ALLOWED')
            self.assert_budget()
            if time.monotonic()-started > self.budgets.tool_timeout:
                raise TimeoutError('TOOL_TIMEOUT')
            event.update(result='PASS', outputHash=schema_hash(result))
            return deepcopy(result)
        except (ValueError, TypeError, TimeoutError) as error:
            # Store categories only, never raw payloads or exception text.
            from pydantic import ValidationError
            from .world_pipeline import content_error_category
            category=('TOOL_ARGUMENTS_INVALID' if isinstance(error,ValidationError) else
                      'TOOL_TIMEOUT' if isinstance(error,TimeoutError) else content_error_category(error,'semantic'))
            for known in ('BOSS_CROSS_PHASE_UNSOLVABLE','BOSS_CONCEPT_NOT_PREVIOUSLY_INTRODUCED',
                          'INVALID_AGENT_TRANSITION','REPAIR_BUDGET_EXHAUSTED','TOOL_BUDGET_EXHAUSTED',
                          'OUTPUT_SIZE_EXCEEDED','TOTAL_EXECUTION_EXHAUSTED','AI_JUDGE_REJECTION'):
                if known in str(error): category=known
            event['errorCategory']=category
            if isinstance(error,TimeoutError):
                self.invalidate()
                self.state='REJECTED'
            elif name in ('design_world','design_boss','repair_world','repair_boss','compile_world','run_quality_gate','judge_candidate') and self.state!='REJECTED':
                self.invalidate()
                self.state='REPAIR_REQUIRED'
            raise
        finally:
            event.update(durationMs=round((time.monotonic()-started)*1000),stateAfter=self.state,repairNumber=self.repairs)
            self._audit.append(event)
