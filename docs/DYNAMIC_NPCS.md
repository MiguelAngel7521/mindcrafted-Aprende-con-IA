# V2.6 — Dynamic NPCs and contextual hints

AI WRITES — CODE DECIDES. WorldEngine, QuestSystem and the existing static dialogue
effects remain authoritative. Dynamic replies are text data, never commands.

## Architecture and modes

`NPCContextSystem` extends the existing `DialogueSystem` and WorldEngine. Static
quest triggers still start/finish conversations and apply their validated effects.
Dynamic wording only replaces the displayed first line; it cannot advance dialogue,
complete a quest, open a gate, grant XP or submit a learning observation.

- STATIC: use the existing authored dialogue.
- CONTEXTUAL (default): immediate deterministic reactions/hints from actual state.
- AI_DYNAMIC: display contextual wording immediately, optionally request constrained
  AI wording, and keep the contextual answer on any failure. No loading lock.

A late reply is discarded after dialogue advance, reset, restore or region change.
Browser requests have a 2.5-second timeout and use AbortController. Text is rendered
with `textContent`, inside the existing map UI and main canvas.

## Bounded context and memory

The builder reads the current NPC, region, quest stage, active puzzle/archetype,
objective, rule concepts and literal evidence excerpts. It includes actual attempts,
errors, repeated failed-rule signatures, resets, hints used, per-skill mastery,
completed puzzle objectives and only that puzzle's permitted flags. Boss context
identifies only the current or already solved phase; future phases are rejected.
It never sends mechanics, solver results, full savegames or the whole campaign.

Context is capped at 24,000 UTF-8 bytes, at most 12 rules/skills. Long evidence is
shortened to literal prefixes, not model summaries. Larger Unicode inputs receive
shorter excerpts/wording variants before the cap. Building context does not mutate
world state. Runtime events alone maintain structured memory:
`met`, `previousQuest`, `hintsRequested`, `lastHintLevel`, `bossCompleted`, a bounded
reaction list, and repeated-error signature/count.

Memory is serialized in the existing world save and sanitized against current
puzzles on restore. Generated text is not trusted or replayed from a save. Restore
never repeats a hint request, learning event, reward or dialogue effect.

## Contract, grounding and anti-spoiler

`npc_schema.py` defines closed Pydantic schemas for context, profile and output.
`npc-contract.js` is generated from those schemas; a regression test checks exact
parity. Output fields: `text`, `emotion`, `intent`, `hintLevel`, `kind`,
`referencedConcepts`, `sourceRefs`. Unknown fields, malformed JSON, excessive size,
invalid references and higher hint levels are rejected independently in Python and
in the browser. The browser validates against its own original runtime context,
not against a returned context or a model-provided allowance.

`kind` distinguishes `academic_fact` (hints, requiring current evidence refs) from
`narrative_fiction` (approved situational reactions). Facts and role-specific
prefixes come from trusted runtime templates and current puzzle evidence.

**Intentional limitation:** this milestone uses constrained verbalization. The
model selects/composes one of the runtime-approved wording variants and emotion;
it cannot introduce a novel academic paraphrase or arbitrary narrative assertion.
Even labeling a hallucination as fiction cannot bypass validation. This is a
stronger boundary than trying to detect every semantic spoiler with string matching.
Levels 1–2 expose only existing conceptual/strategic hint templates; exact routes,
connections, assignments and final configurations are outside their allowed wording.
No semantic AI Judge or unrestricted chatbot is claimed here.

## Hint policy and BKT

Level 0 is conversation without a hint. Explicit hints start at 1 (conceptual).
Repeated failures with prior hints permit 2 (strategic); persistent failure permits
3 (concrete); sufficient failures, previous hints and a reset permit 4 (near solution).
High mastery delays concrete help. Repeated clicking without errors cannot escalate.
The authored puzzle's existing hint text remains under deterministic runtime control.
No puzzle rules, difficulty, solver or success conditions change.

Only `tracker.get(skill).mastery` values enter the context. NPC code has no BKT
tracker object or `observe` capability. Actual puzzle assessment continues to produce
all learning observations, including the runtime's existing hint-use metrics.

## Agent API, transport and offline behavior

`NPCDialogueAgent` reuses `AgentRunner._request`, the existing provider adapter,
Structured Outputs, technical retry, deadlines, output caps and audit hashes.
The model receives a READ_ONLY_DIALOGUE request and no gameplay/design/publication
tools. Default budgets: one technical retry, one second per provider call, four
seconds total and 8,000 output bytes. Invalid content immediately falls back; it
does not start a costly semantic repair loop during play.

`POST /api/v2/npc-dialogue` accepts only a bounded NPCContext. It is disabled (503)
unless trusted application code explicitly installs `app.state.npc_dialogue_provider`
using the existing configured provider. No model/key/base URL is accepted from the
request. This endpoint does not authenticate a learner's save or change server
progress; the browser's authoritative context remains the final response boundary.

The browser uses this same-origin endpoint, or a trusted application-supplied
`window.mindcraftedNPCProvider(context, {signal})`. Portable file exports, missing
credentials, unavailable network, timeout, schema failure and rejected wording all
retain contextual gameplay. Default CONTEXTUAL mode makes no provider calls.
No live provider or production deployment was used for this milestone.

## Planner and personalities

Each planned quest can specify `npc` with a `role` (mentor, engineer, operator,
researcher, rival, guide), `mode` and fictional `narrativePurpose`. The associated
objective is the quest's existing objectiveId. Agent packaging carries these profiles
as `npcProfiles[worldId][puzzleId]`; Boss phases reuse the corresponding practiced
objective's profile. Role prefixes change tone only, never academic facts.
The purpose is retained as planning metadata; arbitrary purpose text is not emitted
as runtime academic explanation. Old plans without profiles retain defaults.

## Verification

`test_npc_dialogue.py` covers bounded/read-only context, canonical schemas, all hint
levels, mastery influence, roles/modes, malformed/oversized responses, timeout,
technical retry, commands, invented citations, hallucinations disguised as fiction,
spoilers, escalation, BKT-write attempts, stale replies, persistence, future Boss
phases, endpoint fallback and Planner profile boundaries.

`test_npc_browser.py` physically plays the practice/Boss campaign. It meets NPCs,
provokes two errors, requests levels 1 and 2, reloads, recovers, solves and completes
three Boss phases. A scripted provider first returns valid wording, then a forbidden
command; subsequent network requests fail. Chromium verifies final consequences,
NPC reactions, one canvas, no iframe/mandatory overlay, saved memory and unchanged
BKT/rewards after reload. The existing independent Boss browser test also passes.

Final local verification: **566 passed, 4 existing deprecation warnings** (533
baseline + 33 new tests). `compileall`, syntax checks for all 30 JS/CJS/MJS files,
and `git diff --check` pass. The separate exported practice/Boss campaign build
passes Chromium with 377 steps, two regions, three phases, reload, mobile and
recovery checks (`output/npc-campaign/index.html`). The full-suite JUnit evidence
is `output/npc-full-suite.xml`; generated artifacts are not committed.

`courses.json` remains unchanged (SHA-256
`aa60696534463f105d72c620416b4777b159a68cba9a2926fdf01fbdfae88d13`).
No live LLM or real Judge was run: FIRST VERIFIED AI CAMPAIGN remains NOT YET
APPROVED. This milestone verifies deterministic infrastructure and scripted-provider
integration, not production model reliability.
