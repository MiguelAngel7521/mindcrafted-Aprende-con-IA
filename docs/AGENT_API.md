# V2.4 — Guarded Agent API

This extends the original dispatcher; it reuses World V2 schemas, MechanicSelector,
compilers, solvers, BossSystem and QualityGate. It does not introduce a free-running
agent, runtime mutation tools, another provider client or new puzzle archetypes.

## Provider orchestration

`AgentRunner(session, provider).run(boss=False)` drives an explicit state machine.
A provider proposes one structured command at a time: `tool`, `arguments`, `step`,
`generationId`. The schema pins tool/step/generation ID to the permitted next step.
Argument schemas derive from the canonical Pydantic models. Responses pass strict
JSON parsing and schema validation before dispatch; extra fields are rejected.

`RealProvider(ProviderConfig(provider, model, base_url=None))` delegates to existing
`api.generate`, BYOK/environment configuration and normalization. No model/provider
name is hardcoded. Explicit fixed models are required. The default requests real
`json_schema`/`strict=true`; best-effort or JSON mode must be explicitly configured
for compatible endpoints and still undergo local validation. This is structured
command dispatch, **not native chat-completion `tool_calls`**. No new SDK is needed.

`ScriptedProvider` accepts predetermined responses, errors or callbacks for tests.
Any adapter other than the exact production adapter is conservatively TEST_ONLY.
A scripted Judge can test sequencing; it cannot confer real AI approval.

## Registry, permissions and state

| Tool | Permission | Effect |
| --- | --- | --- |
| analyze_material | ANALYZE | Existing grounded structure graph |
| select_mechanic | PLAN | Scoped LearningObjective and deterministic selection |
| design_world / design_boss | DESIGN | Declarative candidate only |
| validate_blueprint | VALIDATE | Exposes successful design-time validation |
| compile_world | COMPILE | Canonical compile and verified solution |
| solve_world | SOLVE | Exposes existing solver/composed-Boss proofs |
| run_quality_gate | VALIDATE | All checks, actual Node runtime and Chromium |
| judge_candidate | REVIEW | Provider review, only after deterministic PASS |
| repair_world / repair_boss | REPAIR | Replaces the failed candidate |
| package_campaign | PACKAGE | Packages approved snapshot in memory |

Design validates schema and semantics before reaching VALIDATED; the explicit
validation tool can inspect that result. Compilation already runs the existing
solver; solve_world exposes its proof without inventing a parallel solver.

`NEW → ANALYZED → PLANNED → VALIDATED → COMPILED → SOLVED → GATED → JUDGED → PACKAGED`

Boss design follows ANALYZED directly and uses the existing per-phase selectors
inside `world_boss`. Content failure invalidates candidate/world/proof/gate/Judge
and moves to REPAIR_REQUIRED. Only a repair tool can continue from that state.
Exhaustion is terminal REJECTED. Concurrent dispatch, skipped gates, replayed command
identity, unknown tools and model-supplied permissions/paths/verdicts are rejected.
The application owns source, budgets, provider, earlier lessons and publication path.
Python callers are trusted application code; these objects are not a Python sandbox.

## Retry and repair

Technical retries cover timeout, connection interruption, empty response, HTTP 429
and temporary upstream failures. Each retries the identical request. The reused API
adapter receives one attempt to avoid multiplying retries. Authentication/refusal
errors stop immediately. Schema/semantic errors never enter the transport retry.

Repair receives the rejected candidate plus concrete diagnostic and source/selection
constraints. Replacement is model-produced, never patched JSON. Every replacement
invalidates earlier derived evidence, including when its schema is malformed.
Diagnostics travel only in bounded provider context; the audit trail contains
categories/hashes rather than raw candidate, prompt, headers or exception text.

## Budgets

Defaults in `Budgets`: 2 provider retries (3 total attempts), 2 content repairs
(3 candidates), 40 command steps, 120 seconds/provider call, 180 seconds/tool,
900 seconds/session, 300,000 bytes/model output or tool arguments. Invalid budget
configuration is rejected. Deadline expiry/size exhaustion cannot authorize a package.

Compile, Boss validation, browser gate and export run in a separate POSIX process
session. Timeout/cancellation kills its process group, including child processes.
Cheap bounded analysis/schema work is checked before and after execution; synchronous
Python validation is not preempted mid-instruction. Worker responses have an 8 MB
cap. Provider token output is also bounded; the byte cap is checked on receipt,
not as a streaming network cap. Session budgets begin at construction.

## Boss integration and prerequisites

BossBlueprint reuses `world_boss.compile_boss` and the composite solver. Its finite
exports, bindings, semantic grounding, per-phase eligibility and every reachable
winning branch must pass. `BOSS_CROSS_PHASE_UNSOLVABLE` triggers repair/rejection.
The agent cannot submit `priorSkills`: they derive from application-supplied prior
lesson packages, validated against their material and teaching order. A real
publication also requires those lessons to carry their real approval evidence.
A Boss package includes the preceding practice regions through existing campaign
assembly, so the player earns the prerequisites before entering the Boss.

## QualityGate and Judge boundary

`run_quality_gate` always enables runtime and browser probes; there is no tool
argument to disable them. Every CHECKS entry must be true with no errors. The Judge
is called only then. Gate hash, compiled-world hash and Judge are rechecked at
packaging. A perfect Judge never overrides deterministic failure.
TEST_ONLY packages have `developmentDemo=true`, `quality.approved=false` and
`judgeAuthority=TEST_ONLY_JUDGE` (per region for campaigns). They cannot be reused
as real approved fallback/publication evidence.

## PublicationAuthority

Packaging is not a write. The application must explicitly call
`await PublicationAuthority(output_dir, allow_real=False).publish(session)`.
Real publication additionally requires `allow_real=True` and a real-provider review.
All session-owned gates/hashes are rechecked; the worker revalidates the world.
The existing campaign writer verifies composed campaigns in Chromium again.
A worker exports only into disposable staging. After successful completion within
budget the whole directory is renamed into a **new** destination. Existing
destinations are rejected, preserving previous artifacts. The agent never receives
filesystem paths or authority objects. No operation writes `courses.json`.

```python
from mindcrafted.generator.agent_tools import AgentSession
from mindcrafted.generator.agent_provider import ProviderConfig, RealProvider
from mindcrafted.generator.agent_runner import AgentRunner
from mindcrafted.generator.agent_publication import PublicationAuthority

# source/model/provider/output are application-controlled inputs; credentials use
# the existing provider-specific environment variables and are never tool arguments.
session = AgentSession(source)
provider = RealProvider(ProviderConfig(provider_name, fixed_model_id))
package = await AgentRunner(session, provider).run()
path = await PublicationAuthority(new_output_directory, allow_real=True).publish(session)
```

This entry point is opt-in; it does not replace the legacy generation endpoints.
World/quest/dialogue/hint content is generated within the canonical Blueprint;
there are no standalone runtime-mutating dialogue tools or AI Planner in this phase.

## Audit trail

`session.audit` returns detached events with generation ID, state before/after,
tool, provider/model, step, attempt, repair number, schema version, input/output
hashes, duration, result and error category. Publication adds an authority event.
Source, prompts, responses, API keys and Authorization headers are not stored there.
ScriptedProvider retains its fixture requests in memory for test assertions only.

## Verification and limitations

Baseline: 459 passing tests, four known warnings. New tests cover invalid sequences,
closed permissions, invented evidence, ineligible mechanics, insoluble puzzles,
Boss cross-phase repair, prerequisites, stale candidates, all budgets, retries,
Judge rejection, hash tampering and publication vetoes. Integrated tests use the
scripted provider with real compilers, solvers, Node and Chromium: first-pass world,
repaired world, exhausted repairs and practice → repaired Boss → campaign export.
No test substitutes fake success for the deterministic gate.

CI installs test dependencies and Chromium, runs full pytest, compileall and all
tracked JS/CJS/MJS syntax checks, then builds a playable Boss development campaign.
The application has no Python distribution metadata; a wheel build is not its
build contract. The separate legacy PyPI tag workflow is not used for this milestone.

No live LLM/Judge or model bake-off is required or claimed. Real-model reliability
remains a separate integration gate. POSIX process-group execution currently targets
Linux/macOS. Publication targets a new directory; replacing a live registry/course
is deliberately an application operation outside this API. Academic truth beyond
literal grounding and deterministic coupling still requires educational review.

## Milestone verification — 2026-10-02

AGENT API: DONE (deterministic infrastructure). The complete suite passed **509
tests**, with no failures or skips and the same four FastAPI deprecation warnings.
This preserves the 459-test baseline and adds 50 tests; 64 tests cover Agent API.
The suite includes scripted-provider repair, exhausted repair, protected publication,
Boss cross-phase rejection/recovery, and real browser integration.

`python -m compileall -q mindcrafted`, syntax checks for all 28 tracked JS/CJS/MJS
files, and `git diff --check` passed. The CI application build command
`world_tools check --boss-demo 3` passed separately: 377 steps, two regions,
three Boss phases, recovery, reload and mobile checks. Its Judge was not run and
the artifact is explicitly a development demo. Local evidence is retained in
`output/agent-full-suite.xml` and `output/ci-agent-boss/` (ignored build artifacts).

`courses.json` stayed unchanged, SHA-256
`aa60696534463f105d72c620416b4777b159a68cba9a2926fdf01fbdfae88d13`.
No API keys or environment files are included. Local verification used Python
3.14; GitHub CI provisions Python 3.11 and independently repeats the checks.
Hosted CI status must be read from its run; local results do not claim remote PASS.

FIRST VERIFIED AI CAMPAIGN: NOT YET APPROVED. No live provider/Judge approval was
fabricated. AI Planner, dynamic NPCs and subsequent phases remain outside this milestone.

## Optional V2.5 planning entry point

[AI_PLANNER.md](AI_PLANNER.md) adds `plan_campaign` (PLAN), `repair_plan` (REPAIR)
and the terminal planning state `PLAN_VALIDATED`. `run(plan_only=True)` returns
validated intentions, not a package. Campaign realization uses the same dispatcher,
provider, repair, gate and publication boundary with application-owned plan bindings.
Existing single-world and Boss callers remain compatible.

## Optional V2.6 read-only NPC wording

[DYNAMIC_NPCS.md](DYNAMIC_NPCS.md) adds NPCDialogueAgent using the existing bounded
structured provider request path. It exposes no dispatcher mutation tools. Invalid
wording uses immediate contextual fallback, not generation/publication authority.
