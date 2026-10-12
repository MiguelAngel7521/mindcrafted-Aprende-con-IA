"""Bounded campaign intentions, grounded in the existing source graph and selector."""
from typing import Annotated, Literal
import re
from pydantic import Field
from .world_schema import Data, Id, Text
from .npc_schema import NPCProfile
from .knowledge_features import build_structure_graph, LearningObjective, normalized
from .mechanic_selector import MechanicSelector, verify_objective_binding

Mechanic = Literal['node_connect', 'resource_balance', 'machine_configuration']
Stage = Literal['introduce', 'practice', 'apply', 'combine']
Ids = Annotated[list[Id], Field(max_length=24)]


class Evidence(Data):
    relationId: Id
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    quote: Text


class PlannedObjective(Data):
    id: Id
    text: Text
    concepts: Annotated[list[Id], Field(min_length=3, max_length=100)]
    relations: Annotated[list[Id], Field(min_length=2, max_length=100)]
    evidence: Annotated[list[Evidence], Field(min_length=2, max_length=100)]
    prerequisites: Ids
    expectedMastery: Annotated[float, Field(ge=0.5, le=1)]
    difficulty: Stage
    intent: Literal['explore', 'connect', 'distribute', 'configure']

    def objective(self):
        return LearningObjective(self.id, self.text, tuple(self.relations), tuple(self.concepts), self.intent)


class QuestPlan(Data):
    npc: NPCProfile = Field(default_factory=NPCProfile)
    id: Id
    objectiveId: Id
    puzzleId: Id
    narrativeProblem: Text
    consequence: Literal['open_route']
    mechanic: Mechanic


class RegionPlan(Data):
    id: Id
    narrativeTitle: Text
    objectives: Annotated[list[Id], Field(min_length=1, max_length=3)]
    quests: Annotated[list[QuestPlan], Field(min_length=1, max_length=3)]
    prerequisites: Ids


class BossPhasePlan(Data):
    objectiveId: Id
    mechanic: Mechanic


class BossPlan(Data):
    afterRegion: Id
    phases: Annotated[list[BossPhasePlan], Field(min_length=2, max_length=4)]
    difficulty: Literal['boss']


class CampaignPlan(Data):
    schemaVersion: Literal[1]
    id: Id
    narrativeTitle: Text
    learningObjectives: Annotated[list[PlannedObjective], Field(min_length=2, max_length=12)]
    regions: Annotated[list[RegionPlan], Field(min_length=1, max_length=4)]
    difficultyCurve: Annotated[list[Stage], Field(min_length=2, max_length=12)]
    bossPlan: BossPlan


def unique(items, label):
    if len(items) != len(set(items)):
        raise ValueError('DUPLICATE_PLAN_REFERENCE: ' + label)


def dag(items):
    by_id = {x.id: x for x in items}
    unique([x.id for x in items], 'DAG')
    visited, active = set(), set()
    def visit(key):
        if key not in by_id: raise ValueError('MISSING_PREREQUISITE: ' + key)
        if key in active: raise ValueError('CYCLIC_PREREQUISITES: ' + key)
        if key in visited: return
        active.add(key)
        for parent in by_id[key].prerequisites: visit(parent)
        active.remove(key); visited.add(key)
    for key in by_id: visit(key)


def validate_plan(value, source):
    plan = CampaignPlan.model_validate(value)
    # All prose is data, never interpreted. Reject obvious executable payloads too.
    if re.search(r'<\s*script|javascript:|\b(?:eval|exec|openDoor|completeQuest|giveXP|setSolved|__import__)\s*\(|new\s+Function|\b(?:lambda|import)\s|=>', plan.model_dump_json(), re.I):
        raise ValueError('EXECUTABLE_PLAN_CONTENT')
    graph = build_structure_graph(source)
    relations = {r['id']: r for r in graph['relations']}
    objectives = {o.id: o for o in plan.learningObjectives}
    dag(plan.learningObjectives); dag(plan.regions)
    selections = {}
    for o in plan.learningObjectives:
        unique(o.relations, o.id); unique(o.concepts, o.id)
        if not set(o.relations) <= relations.keys(): raise ValueError('SOURCE_EVIDENCE_ERROR: ' + o.id)
        expected = {relations[r][k] for r in o.relations for k in ('subject', 'object')}
        if set(o.concepts) != expected: raise ValueError('UNGROUNDED_CONCEPT: ' + o.id)
        evidence = {e.relationId: e for e in o.evidence}
        if len(evidence) != len(o.evidence) or set(evidence) != set(o.relations):
            raise ValueError('SOURCE_EVIDENCE_ERROR: ' + o.id)
        for key, e in evidence.items():
            if e.model_dump(exclude={'relationId'}) != relations[key]['evidence']:
                raise ValueError('SOURCE_EVIDENCE_ERROR: ' + key)
        selections[o.id] = MechanicSelector().select(graph, source, o.objective())
        if not selections[o.id]['eligibleMechanics']: raise ValueError('NO_ELIGIBLE_MECHANIC: ' + o.id)
    taught, reached, ordered, history = set(), set(), [], []
    puzzle_ids, quest_ids = [], []
    for index, region in enumerate(plan.regions):
        if (index == 0 and region.prerequisites) or (index and plan.regions[index-1].id not in region.prerequisites) or not set(region.prerequisites) <= reached:
            raise ValueError('UNREACHABLE_REGION: ' + region.id)
        unique(region.objectives, region.id)
        if set(region.objectives) != {q.objectiveId for q in region.quests} or len(region.quests) != len(region.objectives):
            raise ValueError('QUEST_OBJECTIVE_MISMATCH: ' + region.id)
        for q in region.quests:
            if q.objectiveId not in objectives or q.objectiveId in taught:
                raise ValueError('UNREACHABLE_LEARNING_OBJECTIVE: ' + q.objectiveId)
            o = objectives[q.objectiveId]
            if not set(o.prerequisites) <= taught: raise ValueError('UNREACHABLE_LEARNING_OBJECTIVE: ' + o.id)
            candidates = selections[o.id]['candidates']
            best = max(c['score'] for c in candidates if c['eligible'])
            top = [c['archetype'] for c in candidates if c['eligible'] and c['score'] == best]
            if q.mechanic not in top: raise ValueError('INELIGIBLE_OR_LOWER_FIT_MECHANIC: ' + o.id)
            # Diversity breaks exact educational ties only.
            if len(history) >= 2 and history[-2:] == [q.mechanic]*2 and len(top) > 1:
                raise ValueError('AVOIDABLE_MECHANIC_REPETITION: ' + o.id)
            history.append(q.mechanic); ordered.append(o); taught.add(o.id)
            puzzle_ids.append(q.puzzleId); quest_ids.append(q.id)
        reached.add(region.id)
    unique(puzzle_ids, 'puzzles'); unique(quest_ids, 'quests')
    if taught != objectives.keys(): raise ValueError('UNREACHABLE_LEARNING_OBJECTIVE')
    stages = ['introduce', 'practice', 'apply', 'combine']
    if plan.difficultyCurve != [o.difficulty for o in ordered] or any(stages.index(a.difficulty) > stages.index(b.difficulty) or a.expectedMastery > b.expectedMastery for a,b in zip(ordered, ordered[1:])):
        raise ValueError('INVALID_DIFFICULTY_CURVE')
    if plan.bossPlan.afterRegion != plan.regions[-1].id: raise ValueError('UNREACHABLE_BOSS')
    taught_mechanics = {q.objectiveId:q.mechanic for r in plan.regions for q in r.quests}
    if len({p.objectiveId for p in plan.bossPlan.phases}) < 2:
        raise ValueError('BOSS_SKILL_NOT_TAUGHT: combine at least two objectives')
    for phase in plan.bossPlan.phases:
        if taught_mechanics.get(phase.objectiveId) != phase.mechanic:
            raise ValueError('BOSS_SKILL_NOT_TAUGHT: ' + phase.objectiveId)
    return plan


def validate_realization(plan, source, candidate, region_id=None, previous_lessons=()):
    """Bind intentions to actual playable puzzles, before compiler/gate/Judge."""
    plan = validate_plan(plan, source)
    graph = build_structure_graph(source)
    objectives = {o.id:o for o in plan.learningObjectives}
    if region_id is not None:
        region = next(r for r in plan.regions if r.id == region_id)
        quests = {q.puzzleId:q for q in region.quests}
        if {p['id'] for p in candidate['puzzles']} != quests.keys() or len(candidate['puzzles']) != len(quests):
            raise ValueError('MISSING_PLANNED_PUZZLE')
        if candidate['title'] != region.narrativeTitle: raise ValueError('REGION_PLAN_MISMATCH')
        pairs = [(p, quests[p['id']]) for p in candidate['puzzles']]
        if [p['id'] for p in candidate['puzzles']] != [q.puzzleId for q in region.quests]:
            raise ValueError('INVALID_PUZZLE_PROGRESSION')
    else:
        if len(candidate['phases']) != len(plan.bossPlan.phases): raise ValueError('BOSS_PLAN_MISMATCH')
        pairs = [(p['puzzle'],q) for p,q in zip(candidate['phases'],plan.bossPlan.phases)]
        # Every Boss skill must have an actual prior puzzle for the same objective.
        taught = {}
        for region, (package, _) in zip(plan.regions, previous_lessons):
            puzzles = {p['id']:p for p in package['world']['puzzles']}
            for q in region.quests:
                if q.puzzleId in puzzles:
                    taught[q.objectiveId] = {r['skill'] for r in puzzles[q.puzzleId]['knowledge']['requiredRules']}
        for p, q in pairs:
            if not {r['skill'] for r in p['knowledge']['requiredRules']} <= taught.get(q.objectiveId, set()):
                raise ValueError('BOSS_SKILL_NOT_TAUGHT: ' + q.objectiveId)
    transfer_relations = set()
    if region_id is None:
        quotes = [v['evidence'] for phase in candidate['phases'] for v in phase['bindings'] + phase['exports']]
        transfer_relations = {r['id'] for r in graph['relations'] if any(normalized(r['evidence']['quote']) in normalized(q) for q in quotes)}
    for puzzle, binding in pairs:
        if puzzle['mechanics']['archetype'] != binding.mechanic: raise ValueError('PLAN_MECHANIC_MISMATCH')
        objective = objectives[binding.objectiveId]
        if region_id is not None and puzzle['objective'] != objective.text:
            raise ValueError('QUEST_OBJECTIVE_MISMATCH')
        scope = objective.objective()
        if region_id is None:
            scope = LearningObjective(objective.id, objective.text, tuple(set(objective.relations) | transfer_relations))
        verify_objective_binding(puzzle, graph, scope)
        cited = {r['id'] for r in graph['relations'] if any(normalized(r['evidence']['quote']) in normalized(rule['evidence']) for rule in puzzle['knowledge']['requiredRules'])}
        if not set(objective.relations) <= cited: raise ValueError('UNPRACTICED_OBJECTIVE_RELATION: ' + objective.id)
    return True


def validate_compiled_plan(binding, source, world):
    plan = validate_plan(binding['plan'], source)
    if binding['regionId'] is None:
        return  # Existing composed Boss validator checks completion and prerequisites.
    region = next(r for r in plan.regions if r.id == binding['regionId'])
    for quest in region.quests:
        puzzle = next(p for p in world['puzzles'] if p['id'] == quest.puzzleId)
        if not any(q['puzzleId'] == quest.puzzleId for q in world['quests']):
            raise ValueError('QUEST_NOT_REALIZED')
        if not puzzle['success'].get('openEntity') or not puzzle['success'].get('setFlags'):
            raise ValueError('PLANNED_CONSEQUENCE_MISSING')
