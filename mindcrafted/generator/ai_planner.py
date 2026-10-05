"""Plan then realize with the existing guarded agent; publication stays external."""
from copy import deepcopy
from .agent_tools import AgentSession, Budgets
from .agent_runner import AgentRunner
from .campaign_plan import validate_plan


class CampaignPlanner:
    def __init__(self, source, provider, *, budgets=None):
        self.source, self.provider = source, provider
        self.budgets = budgets or Budgets(max_tool_calls=100, total_timeout=1800)
        self.sessions = []
        self.plan = None
        self.final_session = None

    async def run(self):
        if self.sessions:
            raise ValueError('INVALID_AGENT_TRANSITION: planner already used')
        planning = AgentSession(self.source, budgets=self.budgets)
        self.sessions.append(planning)
        try:
            self.plan = await AgentRunner(planning, self.provider).run(plan_only=True)
            plan = validate_plan(self.plan, self.source)
            lessons = []
            for region in [*plan.regions, None]:
                # One campaign deadline and aggregate tool/repair counts, not fresh budgets.
                session = AgentSession(self.source, budgets=self.budgets,
                    previous_lessons=lessons if region is None else (),
                    plan_binding={'plan':deepcopy(self.plan),'regionId':region.id if region else None})
                session._started = planning._started
                session._calls = self.sessions[-1]._calls
                session.repairs = self.sessions[-1].repairs
                self.sessions.append(session)
                package = await AgentRunner(session, self.provider).run(boss=region is None)
                if region is not None:
                    lessons.append((package, self.source))
                else:
                    self.final_session = session
                    return package
        except BaseException:
            self.final_session = None
            for session in self.sessions:
                session.invalidate()
                session.state = 'REJECTED'
            raise

    @property
    def audit(self):
        return [event for session in self.sessions for event in session.audit]
