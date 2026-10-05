# V2.5 — AI Planner

AI PROPOSES — CODE VERIFIES. The Planner produces data and cannot execute gameplay
or publish. It extends the existing Agent API; no second graph extractor, selector,
provider, compiler, solver, Boss engine or QualityGate is introduced.

## Contract

`CampaignPlan` in `generator/campaign_plan.py` is the canonical closed Pydantic
schema (`schemaVersion: 1`). JSON Schema is generated with
`CampaignPlan.model_json_schema()` and the existing Structured Outputs adapter.
There is no manually maintained prompt schema.

- `learningObjectives`: 2–12 objectives, concept/relationship IDs, exact source
  evidence (offsets and quote), prerequisites, expected mastery and difficulty.
- `regions`: 1–4 coherent practice regions, each with 1–3 objectives and quests.
  Several concepts/relations belong to one objective; a concept does not create
  a new region. The existing Boss adds one final region.
- `quests`: objective, puzzle ID, selected mechanic, fictional world problem and
  proposed `open_route` consequence. The canonical compiler creates the actual
  quest, gate, flag and NPC; compiled consequences are checked again.
- `difficultyCurve`: ordered `introduce / practice / apply / combine` intentions.
  Mastery targets cannot decrease. These are curriculum targets, not claims about
  the student's BKT and not hidden changes to live puzzle rules.
- `bossPlan`: 2–4 phases tied to previously practiced objectives/mechanics, after
  the final practice region, with `boss` difficulty.

Narrative title/problem fields explicitly represent fiction. Academic concepts
and relations must refer to the source-derived graph. No executable field exists;
extra fields and obvious code payloads are rejected. All strings remain data.

## Grounding and progression

The validator rebuilds the existing structural KnowledgeGraph from the immutable
material. Every concept must be a relation endpoint; evidence must exactly match
its relation's quote and offsets. Unknown evidence and concepts are rejected.

Objective and region prerequisite graphs must be DAGs. Every objective is mandatory
and must be practiced exactly once in the declared quest order. Missing, cyclic,
unreachable and omitted objectives fail. Regions currently form the linear sequence
supported by the campaign runtime; their prerequisite DAG cannot imply a bypass.

Each scoped existing `LearningObjective` goes through `MechanicSelector`. The plan
may choose only among the highest scoring eligible candidates. Exact score ties
can vary mechanics; a third repetition is rejected when an equally fitting alternative
exists. A lower educational fit is never accepted merely for diversity.

## Realization and Boss

Plan validation is not playable-world approval. `validate_realization` binds each
planned quest to an actual Blueprint puzzle, its objective, selected mechanic and
required source relationships. Missing puzzles, changed order and unused academic
relationships fail before the compiler. Compiled quests and visible route-opening
consequences must exist.

Boss phases must match the plan and every required skill must occur in the previous
playable puzzle for that specific objective. A skill taught by an unrelated objective
is insufficient. Existing Boss exports/bindings may cite additional grounded transfer
relationships; these are validated by the existing cross-phase compiler/solver.
No additional arbitrary evidence is allowed. Impossible branches still fail the
original Boss validator and QualityGate.

## Agent integration and repair

The existing registry adds `plan_campaign` (PLAN) and `repair_plan` (REPAIR).
`AgentRunner.run(plan_only=True)` follows analysis → structured plan → validation
and returns at `PLAN_VALIDATED`, without package/Judge/publication authority.
Schema and semantic failures use its existing bounded repair loop and diagnostics.
A repaired candidate replaces the previous one. Technical retries stay separate.

`CampaignPlanner(source, provider).run()` first plans, then uses the existing agent
for each practice region and finally the Boss, supplying validated prior lessons.
Every region independently passes compile → solver → simulation/QualityGate → Judge
before assembly. Session deadlines and cumulative tool/repair budgets span regions.
Default campaign budget: 100 tool calls, 1,800 seconds total; existing provider,
output-size and tool timeout limits remain. A failure rejects the campaign; no
filesystem write occurs. Audit events retain each session's generation ID.

The finished package retains `campaignPlan`. Explicit application-controlled
`PublicationAuthority.publish(planner.final_session)` is still required to write;
it also runs the existing composed-campaign Chromium check. TEST_ONLY_JUDGE packages
remain development artifacts, never real AI approval.

```python
planner = CampaignPlanner(material, configured_provider)
package = await planner.run()
# Optional, explicit application authorization; never a model tool:
path = await PublicationAuthority(new_directory, allow_real=True).publish(planner.final_session)
```

## Deterministic tests and E2E

`planner_demo.plan_fixture()` is an explicitly authored software/resource fixture,
not a claim of real academic input or live LLM output. It uses the same schema and
validators as the AI path. `ScriptedProvider` scripts only model responses; it does
not stub compilation, solving, QualityGate or browser gameplay.

`tests/test_ai_planner.py` covers schema/grounding, cycles, missing prerequisites,
omitted objectives, inaccessible/oversized regions, forbidden code, quest mismatch,
wrong mechanics, decreasing difficulty, repair/exhaustion, actual Boss prerequisites,
multiple objectives per region, relation coverage and campaign-wide budgets.
The E2E repairs an invalid plan, generates two practice regions and a composed Boss,
then uses protected export and Chromium to play the three-region campaign with
transitions, recovery and reload. Existing browser assertions enforce one canvas,
no mandatory iframe/overlay and final consequences.

## Limits and delivery

The source parser remains the existing bounded bilingual relation grammar; it is
not a semantic truth oracle. Free-text objective wording and narrative coherence
still need the existing educational Judge. Difficulty stages describe progression;
existing archetype validators/solvers determine puzzle complexity, and the Boss
provides verified cross-phase combination. No adaptive difficulty is implemented.

Campaigns are linear, at most four practice regions plus Boss, with the three
existing pillar mechanics and route-opening quest consequences. There is no model
bake-off, new archetype, dynamic NPC or live-provider validation in this milestone.

Agent API commit `26364f2` is preserved. GitHub delivery is currently
`BLOCKED_BY_GITHUB_AUTH`; remote CI cannot be declared green. The existing CI runs
the full suite (including Planner E2E), syntax checks and a playable campaign build.
`FIRST VERIFIED AI CAMPAIGN: NOT YET APPROVED` remains a separate integration gate.

## Verification — 2026-10-05

- Full suite: **533 passed**, zero failures/skips, four known FastAPI warnings.
  The 509-test baseline is preserved, with 24 additional Planner tests.
- Python compileall, all 28 tracked JavaScript syntax checks and diff whitespace:
  PASS. Existing Agent API tests remain intact and pass in the full suite.
- Separate scripted-provider campaign build/export: PASS, **244 gameplay steps**,
  three regions (two practice plus two-phase Boss), reload, recovery and mobile.
- Local ignored evidence: `output/planner-full-suite.xml`,
  `output/planner-20261005/{index.html,campaign.json,game.pkg.json,agent-audit.json}`.
  The package includes the validated plan and is explicitly a development demo.
- `courses.json` unchanged, SHA-256
  `aa60696534463f105d72c620416b4777b159a68cba9a2926fdf01fbdfae88d13`.
- No live LLM calls, paid API usage or real Judge approval. GitHub push/hosted CI
  remain blocked by missing HTTPS authentication, not declared successful.

AI PLANNER: DONE (local deterministic milestone; remote delivery remains blocked).
