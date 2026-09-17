# V2.3 — Multiphase bosses

`world_boss.py` composes the three existing deterministic archetypes; it does not
replace `generator/boss.py` (legacy V1 adventure). `BossSystem` integrates the
composition with WorldEngine, its internal EventBus, quests, flags and BKT.
There is one player and one gameplay canvas. Each phase has physical controls,
its own mentor, progressive hints, a gate and the usual world-native recovery.

## Declarative contract

`world_schema.py` is authoritative; `boss-blueprint.schema.json` is its exact export.
`BossBlueprint` version 1 contains ID/title/introduction, required skills/concepts,
1–3 shared variables with finite integer domains, 2–4 `BossPhaseBlueprint`s,
failure policy, hint policy and final flag/XP bonus/description.
Each phase contains a normal PuzzleBlueprint, ID, next phase, exports and bindings.
Compiled `BossPhaseSpec` references that puzzle by ID. At least two distinct
archetypes are required. The phase chain is forward-only and terminating.

An export reads an existing edge (`edge_present`) or configuration control
(`configuration_value`) and maps its finite values using explicit cases. A binding
can only set a known `resource_capacity` or `machine_capacity` limit. Both cite an
existing educational rule and literal source evidence. No expression, callback,
script, arbitrary property path or runtime mutation tool is accepted. Unknown
properties are rejected by schema. Every variable needs one earlier producer and
a later consumer; conflicting writes and unknown references fail validation.

## Composite solver and educational checks

`solve_boss` first runs contract/eligibility validation. For every reachable shared
state it applies bindings to a copy, invokes the existing archetype solver, and
simulates every finite configuration. Every winning configuration exports its
shared state into the next phase. A single reachable winning branch that makes a
future phase impossible rejects the whole boss as `BOSS_CROSS_PHASE_UNSOLVABLE`.
The proof records variant solution counts, a playable route and causal witnesses:
changing a shared value must change a downstream set of valid solutions, with
other inputs held constant. Decorative shared state is rejected.

Bounds: at most 16 shared-state variants, 32,768 solver-evaluated states and the
existing per-archetype bounds. Exceeding them rejects instead of approximating.
Literal evidence and causal witnesses do not establish semantic truth of numeric
transfer tables; educational review remains a separate responsibility of the Judge.

## Prerequisites and campaign

Required skills must equal the skills exercised by phase rules and be included in
prior skills. Campaign assembly additionally derives taught skills from actual
preceding regions; an isolated development boss cannot fabricate prior lessons.
The runtime only advances a campaign after the practice region is completed.
`boss_demo.py` is authored development material, not a real AI-approved campaign.

## Recovery, persistence and events

`retry_current` retains editable mistakes until a manual phase reset.
`checkpoint` automatically resets the failing phase. Completed phases and exported
state remain fixed in either policy. Future phases cannot activate early. Hints
are restricted to the current phase; solving unlocks the next district.

Boss progress is derived from verified puzzle state on restore, rather than trusted
from saved phase indexes/shared values. Invalid upstream solutions invalidate later
solutions and reconstruct rewards/flags. Partial current configurations survive
reload. Solved phases cannot emit rewards or learning observations again.

Events include `boss.started`, `boss.phase.started/completed/failed`,
`boss.recovered` and `boss.completed`; the existing puzzle events drive quests and
visible doors. The final phase sets the boss flag and awards the bounded bonus.
BKT records per-rule observations with world/boss/phase context: attempts, errors,
hints, restarts/checkpoints, solution quality and skill. Reload emits no new evidence.

## Verification and development export

```sh
.venv/bin/python -m pytest -q tests/test_multiphase_boss.py tests/test_boss_runtime.py tests/test_boss_browser.py tests/test_boss_campaign.py
.venv/bin/python -m mindcrafted.generator.world_tools check --boss-demo 3 --output output/multiphase-boss
```

The tests cover two, three and four phases, every winning branch, impossible
transitions, executable-binding rejection, causal state, actual prior practice,
128 seeded recovery trials, Python/JS agreement, unique rewards and BKT.
The independent browser journey uses only keyboard gameplay: practice region →
boss introduction → phase 1 → deliberate phase 2 failure → reset → partial save/
reload → phases 2 and 3 → gate/NPC reaction → completion → reload.
A continuity guard rejects mandatory iframes, overlays and secondary canvases.

QualityGate includes the composite boss proof, Node runtime replay and Chromium.
A deterministic failure vetoes even a perfect Judge. Development export explicitly
states `judge: not_run`; generated publication still requires a real Judge.

## Limits

One boss encounter per world; sequential phases, finite capacity bindings and the
three existing archetypes only. No combat/timers, branching phases, arbitrary shared
expressions or newly invented academic concepts. The read-only blueprint contract
is ready for controlled generation; real-provider reliability is a separate gate.
