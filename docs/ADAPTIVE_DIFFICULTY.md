# V2.7 — BKT-driven future challenges

BKT INFORMS — CODE DECIDES. The opt-in adaptation boundary is **entry to a future
single-puzzle practice region**. The current region and every active puzzle keep
exactly their original compiled rules. Boss worlds are ineligible for adaptation;
all their phases and shared-state bindings stay frozen. Existing campaigns without
an adaptive catalog behave exactly as before.

## Policy and evidence

`engine/world/difficulty-policy.js` is the one executable policy, used by both the
browser and Python's `recommend_difficulty` generation boundary. It is pure: no
provider, storage, world mutation or BKT writes. Python invokes the same bounded
Node function rather than maintaining a second set of thresholds.

Inputs: objective, archetype, Planner/application base level, previous level,
per-skill mastery/observation counts, and up to 24 prior relevant puzzle outcomes.
All skills of the future puzzle must have evidence; unrelated successes do not
qualify. Outcomes come from authoritative completed region puzzle states, not model
claims. BKT is read through the existing tracker's `get`, never `observe`.

Default version 1 policy:

- EASY / NORMAL / HARD. At most one level change per boundary.
- At least two observations per skill and two distinct completed challenges.
- High mastery: weakest relevant skill >= 0.85 and two successes with no errors,
  hints or resets. Raise the next level once.
- Low mastery <= 0.45, or medium mastery below 0.85, plus persistent support need
  on both recent challenges (at least two errors, two hints or one reset): lower
  the next level once.
- Otherwise retain the level. A cooldown of two further completed relevant challenges after a change
  prevents immediate reversal. Unrelated regions do not consume the cooldown. The broad middle band prevents small probability variations
  from producing alternating levels.
- Missing evidence: use the declared base, with reason
  `INSUFFICIENT_MASTERY_EVIDENCE`. Missing BKT is not low mastery.

These are conservative engineering defaults: 0.85 is above the tracker's existing
0.80 mastered threshold; the 0.45 band is below even odds. Requiring repeated
observable performance avoids relying on a probability alone. These thresholds
are **not pedagogically calibrated**. A closed policy configuration supports band,
evidence, cooldown and min/max limits; maxStepChange remains one. Invalid values,
nonfinite mastery, duplicated evidence and unknown parameters are rejected.

## Verified concrete variants

`generator/adaptive_difficulty.py:attach_variants` accepts three already compiled
worlds, normally produced through the existing Agent API. It does not rewrite
JSON, invent academic facts or implement new solvers. All variants must retain
exactly the objective, concept, skills and source evidence. With a CampaignPlan,
each also passes its existing realization/MechanicSelector objective binding.

The closed Campaign schema contains `AdaptiveRegion`, `DifficultyVariant`,
`DifficultyParameters` and `DifficultyPolicyConfig`. Concrete metrics derive from
mechanics, never model labels:

| Archetype | Choice measure | Constraints |
| --- | --- | --- |
| node_connect | candidate edges | connection rules + goals |
| resource_balance | loads × targets | allocation rules + goals |
| machine_configuration | slot choices + parameter values | configuration rules + goals |

ConceptCombinationCount is the number of required skills. All three levels must
have strictly increasing choice complexity and valid archetype parameters. EASY
maps to existing `study`, NORMAL to `normal`, HARD to `hard`, retaining the original
hard-puzzle and random-success checks. Every variant independently passes schema,
causality, grounding, solver, recoverability, runtime simulation and Chromium
QualityGate before attachment. The campaign hash covers the entire catalog.

The fixture varies plausible and misleading dependency edges. It retains the same
layering, single-entry and reachability rules at all levels: EASY is still a
physical dependency puzzle, never trivia. More alternatives require distinguishing
valid academic relationships; no controls, time pressure or academic truths change.
The catalog also supports verified resource and machine instances; it does not
promise that arbitrary material admits three valid complexities. Failed variants
must be repaired through the existing generation loop or rejected.

## Planner, Agent and authority

The existing Planner retains educational structure. An application may request
three candidates for a planned future practice objective using the existing Agent
API, then attach them through the deterministic catalog validator. No new provider,
MechanicSelector, tool dispatcher, compiler or puzzle engine is introduced.
`recommend_difficulty(context, suggestion)` validates a proposed recommendation
against application-owned input; model disagreement is rejected. No live model is
needed at the gameplay boundary.

Attachment is currently restricted to explicit development packages. Real adaptive
publication is rejected with `ADAPTIVE_REAL_PUBLICATION_REQUIRES_VARIANT_JUDGES`:
a single base-world Judge cannot approve unseen alternatives. This milestone does
not claim a real AI campaign or introduce production provider integration.
`write_campaign` rechecks catalog hashes, semantic validity and per-variant gate
evidence before the composed campaign browser test/export. Design/recommendation
never writes courses.json.

## Runtime, hints and persistence

CampaignSession selects only the upcoming region after completing the current
one. It creates a new WorldEngine for that region and retains the one main canvas.
There is no mid-puzzle adaptation method; calling the boundary early is rejected.
Difficulty never changes on an error, hint, reset or BKT update in the active world.

The existing NPC explains fewer options / more alternatives while preserving the
same concept. HintPolicy is reused unchanged: initial hints remain conceptual
(level 1), never solution disclosure or unavailable recovery. EASY provides a
smaller choice set and explicit invitation to request conceptual assistance.

The save retains the policy version, selected/previous level, reason, mastery band,
evidence IDs, bounded decision inputs and selected world hash. Reload verifies the
saved decision against its original inputs and catalog, **not current BKT**, then
restores that exact variant and puzzle state. Future saved regions are discarded
as before. No observations, rewards or hints are emitted by restoration.
`difficulty.selected` exposes the same bounded decision as an event for metrics.
Local saves are not authenticated anti-cheat records; they remain learner-owned.

## Verification and limitations

Tests cover two deterministic learner profiles, cold start, limits, cooldown,
determinism, malformed mastery, model override, objective drift, invalid parameters,
insolubility, catalog ordering, forbidden boundaries and per-archetype metrics.
Chromium physically plays both profiles through two prior practice regions and an
adapted third region, checking NPC wording, hints, errors, active-world immutability,
changed BKT followed by reload, world consequences and no duplicate BKT.

The policy proves technical adaptation and verification, **not improved learning**.
That requires evaluation with students. Choice counts are interpretable structural
proxies, not measured cognitive difficulty. This release does not change Bosses,
add archetypes, run a model bake-off or claim real-provider approval.

## Final local verification — 2026-11-03

- **594 tests PASS**, zero failures/skips, four known FastAPI deprecation warnings:
  566 preserved baseline tests + 28 adaptive tests.
- All three archetypes have verified EASY/NORMAL/HARD fixture variants; every
  variant passes its deterministic gate and actual Chromium probe.
- Adaptive campaign export: **164 gameplay steps**, three regions, reload,
  recovery and mobile PASS. Both student trajectories separately pass browser E2E.
- Independent Boss regression build: **377 steps**, two regions, three phases,
  reload, recovery and mobile PASS; Judge not run.
- Python compileall, all 31 tracked/new JavaScript syntax checks, whitespace check
  and changed-file secret-pattern scan PASS.
- `courses.json` unchanged: SHA-256
  `aa60696534463f105d72c620416b4777b159a68cba9a2926fdf01fbdfae88d13`.
- Ignored local evidence: `output/adaptive-full-suite.xml`,
  `output/adaptive-campaign-20261103/`, `output/adaptive-regression-campaign/`.
  These development artifacts do not assert real AI/Judge approval.

### Hosted CI compatibility correction

The first V2.7 hosted run (`41696024797`) passed all 594 test bodies but failed
teardown of the existing NPC endpoint test: repeated monkeypatches of dynamic
`Starlette.State` attributes caused a second deletion of the same missing key.
The test now isolates and restores the application's State object once. All
endpoint assertions remain, and no runtime or gate was relaxed. The full local
suite was repeated after this fix: **594 passed, zero errors/skips**, with the
four existing deprecation warnings.
