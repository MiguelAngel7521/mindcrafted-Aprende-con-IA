"""Read-only NPC wording through the existing bounded provider orchestration."""
import json
from .agent_tools import AgentSession, Budgets
from .agent_runner import AgentRunner
from .provider_response import GenerationError, ProviderError

from .npc_schema import NPCContext, DialogueOutput
from .structured_schema import schema_hash


def validate_dialogue(value, context):
    c=NPCContext.model_validate(context)
    d=DialogueOutput.model_validate(value)
    if d.hintLevel!=c.maxHintLevel or d.intent!=c.intent:
        raise ValueError('HINT_LEVEL_OR_INTENT_VIOLATION')
    if d.text not in c.allowedTexts:
        raise ValueError('UNVERIFIED_WORDING_OR_SPOILER')
    if d.referencedConcepts!=c.concepts or d.sourceRefs!=c.allowedSourceRefs:
        raise ValueError('DIALOGUE_GROUNDING_ERROR')
    expected='academic_fact' if c.intent=='hint' else 'narrative_fiction'
    if d.kind!=expected or (d.kind=='academic_fact' and not d.sourceRefs):
        raise ValueError('DIALOGUE_GROUNDING_ERROR')
    return d.model_dump()


def contextual(context):
    c=NPCContext.model_validate(context)
    return dict(text=c.allowedTexts[0],emotion='encouraging',intent=c.intent,
        hintLevel=c.maxHintLevel,kind='academic_fact' if c.intent=='hint' else 'narrative_fiction',
        referencedConcepts=c.concepts,sourceRefs=c.allowedSourceRefs)


class NPCDialogueAgent:
    """Only a scoped context enters the model, never a save, source file or tools."""
    def __init__(self, provider, *, budgets=None):
        self.provider=provider
        self.budgets=budgets or Budgets(max_provider_retries=1, provider_timeout=1,
            tool_timeout=3,total_timeout=4,max_output_bytes=8000,max_tool_calls=1,max_repairs=0)
        self.audit=[]

    async def respond(self, context):
        if len(json.dumps(context,ensure_ascii=False).encode())>24000: raise ValueError('NPC_CONTEXT_TOO_LARGE')
        c=NPCContext.model_validate(context).model_dump()
        # Reuse technical retry, structured outputs, size/deadline budgets and audit.
        session=AgentSession('Read-only NPC wording. The only allowed output is declarative dialogue; gameplay authority is never available.',budgets=self.budgets)
        runner=AgentRunner(session,self.provider)
        reason=None
        try:
            value=await runner._request({'permission':'READ_ONLY_DIALOGUE','context':c,
                'instruction':'Compose text from allowedTexts only. Preserve facts, references and hint level. No tools or runtime commands.'},
                DialogueOutput.model_json_schema(),'npc_dialogue')
            answer=validate_dialogue(value,c)
        except (ValueError,TypeError,TimeoutError,GenerationError,ProviderError) as error:
            reason=getattr(error,'category',None) or 'DIALOGUE_REJECTED'
            answer=contextual(c)
        self.audit=session.audit + [{'generationId':session.generation_id,'tool':'validate_dialogue','permission':'READ_ONLY_DIALOGUE',
            'provider':session._provider,'model':session._model,'schemaVersion':'npc-dialogue-1',
            'inputHash':schema_hash(c),'outputHash':schema_hash(answer),
            'result':'FALLBACK' if reason else 'PASS','errorCategory':reason}]
        return {'dialogue':answer,'fallback':reason is not None}
