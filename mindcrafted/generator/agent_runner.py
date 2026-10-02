"""Bounded provider → structured command → existing guarded dispatcher loop."""
import asyncio
from copy import deepcopy
import json
import time

from .agent_provider import RealProvider
from .agent_tools import TOOLS
from .provider_response import ProviderError, GenerationError
from .structured_schema import validate_response_text, schema_hash
from .world_package import JUDGE_SCHEMA


def command_schema(tool, generation_id, step):
    arguments=deepcopy(tool.arguments.model_json_schema())
    definitions=arguments.pop('$defs',{})
    return {'type':'object','additionalProperties':False,'properties':{
        'tool':{'type':'string','enum':[tool.name]},
        'arguments':arguments,'step':{'type':'integer','enum':[step]},
        'generationId':{'type':'string','enum':[generation_id]}},
        'required':['tool','arguments','step','generationId'],'$defs':definitions}


class AgentRunner:
    def __init__(self, session, provider):
        self.session,self.provider=session,provider
        session._provider=provider.config.provider
        session._model=provider.config.model
        session._test_only=type(provider) is not RealProvider
        session._review=self._review
        self._step=0
        self._diagnostic=None
        self._last_candidate=None

    async def _request(self, payload, schema, step):
        s=self.session
        for attempt in range(s.budgets.max_provider_retries+1):
            s.assert_budget()
            started=time.monotonic()
            event={'generationId':s.generation_id,'state':s.state,'tool':'provider',
                'provider':s._provider,'model':s._model,'step':step,'attempt':attempt+1,
                'repairNumber':s.repairs,'schemaVersion':'agent-tools-1','inputHash':schema_hash(payload),
                'outputHash':None,'result':'REJECTED','errorCategory':None}
            try:
                timeout=min(s.budgets.provider_timeout,s.budgets.total_timeout-(time.monotonic()-s._started))
                raw=await asyncio.wait_for(self.provider.respond(deepcopy(payload),schema,
                    step=step,generation_id=s.generation_id,repair_count=s.repairs),timeout)
                if not isinstance(raw,str) or not raw.strip():
                    raise ProviderError('PROVIDER_EMPTY_RESPONSE','Empty response',retryable=True)
                if len(raw.encode())>s.budgets.max_output_bytes:
                    s.state='REJECTED'
                    raise ValueError('OUTPUT_SIZE_EXCEEDED')
                event['outputHash']=schema_hash(raw)
                result=validate_response_text(raw,schema)
                event['result']='PASS'
                return result
            except (TimeoutError,ProviderError) as error:
                category='PROVIDER_TIMEOUT' if isinstance(error,TimeoutError) else error.category
                event['errorCategory']=category
                allowed={'PROVIDER_TIMEOUT','PROVIDER_RATE_LIMIT','PROVIDER_UPSTREAM_ERROR',
                         'PROVIDER_CONNECTION_ERROR','PROVIDER_EMPTY_RESPONSE'}
                if category not in allowed or attempt==s.budgets.max_provider_retries:
                    raise ProviderError(category,'Provider attempts exhausted',retryable=False) from None
                await asyncio.sleep(min(.25*(attempt+1),1))
            except GenerationError as error:
                event['errorCategory']=error.category
                raise
            except ValueError:
                event['errorCategory']='OUTPUT_SIZE_EXCEEDED'
                raise
            finally:
                event['durationMs']=round((time.monotonic()-started)*1000)
                s._audit.append(event)
        raise AssertionError('unreachable')

    async def _review(self, world, gate):
        return await self._request({'source':self.session._source,'world':world,'tests':gate['checks'],
            'purpose':'Evaluate educational coupling, narrative, fairness and progressive hints. '
                      'Score four categories out of 25; reject concerns.'},JUDGE_SCHEMA,'world_judge')

    async def run(self, *, boss=False):
        s=self.session
        if s.state!='NEW':
            raise ValueError('INVALID_AGENT_TRANSITION: runner requires a fresh session')
        try:
            while s.state!='PACKAGED':
                s.assert_budget()
                if s.state=='REPAIR_REQUIRED' and s.repairs>=s.budgets.max_repairs:
                    s.state='REJECTED'
                    raise ValueError('REPAIR_BUDGET_EXHAUSTED')
                name={'NEW':'analyze_material','ANALYZED':'design_boss' if boss else 'select_mechanic',
                    'PLANNED':'design_world','VALIDATED':'compile_world','COMPILED':'solve_world',
                    'SOLVED':'run_quality_gate','GATED':'judge_candidate','JUDGED':'package_campaign',
                    'REPAIR_REQUIRED':'repair_boss' if boss else 'repair_world'}.get(s.state)
                if name is None:
                    raise ValueError('INVALID_AGENT_TRANSITION')
                tool=next(t for t in TOOLS if t.name==name)
                self._step+=1
                if self._step>s.budgets.max_tool_calls:
                    s.state='REJECTED'
                    raise ValueError('TOOL_BUDGET_EXHAUSTED')
                schema=command_schema(tool,s.generation_id,self._step)
                payload={'generationId':s.generation_id,'step':self._step,'state':s.state,'tool':name,
                    'source':s._source,'knowledgeGraph':s._graph,'selections':s._selections,
                    'priorSkills':sorted(s._prior_skills),'diagnostic':self._diagnostic,
                    'previousCandidate':self._last_candidate if name.startswith('repair_') else None}
                try:
                    command=await self._request(payload,schema,'agent_command')
                    if name.startswith(('design_','repair_')):
                        self._last_candidate=deepcopy(command['arguments'])
                    await s.dispatch(command['tool'],command['arguments'])
                    self._diagnostic=None
                except ProviderError:
                    raise  # Technical exhaustion never consumes semantic repair.
                except (ValueError,TypeError) as error:
                    if s.state=='REJECTED': raise
                    self._diagnostic={'category':getattr(error,'category',None) or
                        (s.audit[-1].get('errorCategory') if s.audit else 'CONTENT_ERROR'),
                        'message':str(error)[:6000],'tool':name}
                    if isinstance(error,GenerationError):
                        # Failed schema still replaces prior candidate; consume a repair attempt.
                        self._last_candidate=getattr(error,'candidate','')[:s.budgets.max_output_bytes]
                        s.invalidate()
                        if name.startswith('repair_'): s.repairs+=1
                        s.state='REPAIR_REQUIRED'
                    elif s.state!='REPAIR_REQUIRED':
                        s.state='REJECTED'
                        raise
            return deepcopy(s._package)
        except BaseException:
            s.invalidate()
            s.state='REJECTED'
            raise
