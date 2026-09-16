"""Deterministic educational fit; no provider, runtime, randomness or fallback."""
from dataclasses import dataclass

from .knowledge_features import (LearningObjective, build_structure_graph, extract_features,
                                 objective_from_evidence)


@dataclass(frozen=True)
class MechanicProfile:
    id: str
    signal: str
    intent: str
    min_concepts: int = 3
    min_relations: int = 2

    def eligibility(self, features, objective):
        count = features[self.signal + 'Count']
        eligible = features['conceptCount'] >= self.min_concepts and count >= self.min_relations
        additional = True
        if self.id == 'resource_balance':
            additional = features['quantifiedCapacityCount'] > 0
        elif self.id == 'machine_configuration':
            additional = features['dependencyCount'] + features['compatibilityCount'] > 0
        eligible = eligible and additional
        ratio = count / max(1, features['relationCount'])
        if self.id == 'node_connect':
            specialized = min(features['relationCount'], features['resourceCount'] + features['configurationCount'])
            structural = 1 - specialized / max(1, features['relationCount'])
            score = .55 + .25 * structural + .1 * min(count / 6, 1)
        else:
            extra = ('capacityCount', 'quantityCount') if self.id == 'resource_balance' else ('dependencyCount', 'parameterCount')
            score = .65 + .2 * ratio + .05 * sum(features[k] > 0 for k in extra)
        bonus = .04 if objective.intent == self.intent else 0
        score = round(min(1, score + bonus), 4) if eligible else 0.0
        reasons = [f"{count} grounded {self.signal} relationships; minimum {self.min_relations}",
                   f"{features['conceptCount']} source endpoints; minimum {self.min_concepts}",
                   f"{features['relationCount']} relationships in objective {objective.id}",
                   f"objective intent {objective.intent}: bonus {bonus if eligible else 0:.2f}"]
        if self.id == 'resource_balance':
            reasons.append(f"Quantified budget required: {features['quantifiedCapacityCount']} capacity relationships with quantities in the same evidence")
        elif self.id == 'machine_configuration':
            reasons.append(f"Linked controls required: {features['dependencyCount']} dependencies and {features['compatibilityCount']} compatibilities")
        if not eligible:
            reasons.append('Insufficient structural evidence; no fallback')
        return {'archetype': self.id, 'eligible': eligible, 'score': score, 'reasons': reasons,
                'status': 'PASS' if eligible else 'SOURCE_TOO_WEAK_FOR_' + self.id.upper(),
                'relationshipCount': count, 'evidenceRelationIds': features['featureEvidence'][self.signal]}


PROFILES = tuple(MechanicProfile(*args) for args in (
    ('node_connect', 'connection', 'connect'),
    ('resource_balance', 'resource', 'distribute'),
    ('machine_configuration', 'configuration', 'configure')))
PROFILE_BY_ID = {p.id: p for p in PROFILES}
AMBIGUITY_MARGIN = .05


def eligibility(source, archetype):
    """Common public source contract used by all three archetype entry points."""
    graph = build_structure_graph(source)
    objective = LearningObjective('source', 'Analyze source structure')
    features = extract_features(graph, source, objective)
    result = PROFILE_BY_ID[archetype].eligibility(features, objective)
    # Preserve public metrics consumed by historical node validation/bake-off tools.
    result.update(conceptCount=features['conceptCount'], groundedFacts=graph['factCount'],
                  usableNodeRelations=features['connectionCount'],
                  sourceCoverage=round(features['relationCount'] / max(1, graph['factCount']), 3))
    return result


class MechanicSelector:
    def select(self, graph, source, objective, *, mode='AUTO', history=()):
        if mode != 'AUTO' and mode not in PROFILE_BY_ID:
            raise ValueError('MECHANIC_MODE_ERROR: unsupported forced archetype')
        if len(history) > 100 or any(item not in PROFILE_BY_ID for item in history):
            raise ValueError('MECHANIC_HISTORY_ERROR')
        features = extract_features(graph, source, objective)
        candidates = [p.eligibility(features, objective) for p in PROFILES]
        ranked = sorted((c for c in candidates if c['eligible']), key=lambda c: (-c['score'], c['archetype']))
        margin = round(ranked[0]['score'] - ranked[1]['score'], 4) if len(ranked) > 1 else None
        selected, reason = None, 'No eligible mechanic for this objective'
        status = 'NO_ELIGIBLE_MECHANIC'
        if mode != 'AUTO':
            forced = next(c for c in candidates if c['archetype'] == mode)
            if not forced['eligible']:
                raise ValueError('INELIGIBLE_FORCED_MECHANIC: ' + forced['status'])
            selected, status, reason = mode, 'SELECTED', 'Explicit compatible authoring override'
        elif ranked:
            if len(ranked) == 1 or margin > AMBIGUITY_MARGIN:
                selected, status, reason = ranked[0]['archetype'], 'SELECTED', 'Highest educational fit with sufficient margin'
            else:
                status, reason = 'AMBIGUOUS_MECHANIC_SELECTION', 'Educational scores too close; retain candidates'
                # Only equal educational scores can use history, and only after repetition.
                ties = [c for c in ranked if c['score'] == ranked[0]['score']]
                if len(history) >= 2 and history[-1] == history[-2] and len(ties) > 1:
                    alternatives = [c for c in ties if c['archetype'] != history[-1]]
                    if len(alternatives) == 1:
                        selected, status = alternatives[0]['archetype'], 'SELECTED'
                        reason = 'Equal educational fit; avoid third consecutive repeated mechanic'
        return {'version': 1, 'objectiveId': objective.id, 'sourceHash': graph['sourceHash'],
                'features': features, 'candidates': candidates,
                'eligibleMechanics': [c['archetype'] for c in ranked],
                'selectedMechanic': selected, 'recommendedMechanic': selected,
                'status': status, 'margin': margin, 'reason': reason}


def puzzle_eligibility(puzzle, source):
    archetype = puzzle['mechanics']['archetype']
    if archetype not in PROFILE_BY_ID:
        return {'archetype': archetype, 'eligible': True, 'status': 'LEGACY_COMPATIBILITY',
                'reasons': ['Existing V1-compatible archetype outside the three-profile selector']}
    graph = build_structure_graph(source)
    objective = objective_from_evidence(graph, puzzle['objective'],
                                       [r['evidence'] for r in puzzle['knowledge']['requiredRules']],
                                       objective_id=puzzle['id'])
    features = extract_features(graph, source, objective)
    return dict(PROFILE_BY_ID[archetype].eligibility(features, objective), features=features,
                sourceHash=graph['sourceHash'])


def generation_contract(graph, source, objective, *, mode='AUTO', history=()):
    result = MechanicSelector().select(graph, source, objective, mode=mode, history=history)
    if result['status'] != 'SELECTED':
        raise ValueError(result['status'])
    return {'eligibleMechanics': result['eligibleMechanics'],
            'recommendedMechanic': result['recommendedMechanic'],
            'learningObjective': {'id': objective.id, 'text': objective.text, 'intent': objective.intent,
                                  'relationIds': result['features']['relationIds']},
            'mechanicSelection': result}


def verify_objective_binding(puzzle, graph, objective):
    """A scoped generation cannot quietly borrow another objective's facts."""
    from .knowledge_features import scoped_relations, normalized
    allowed = {r['id'] for r in scoped_relations(graph, objective)}
    for rule in puzzle['knowledge']['requiredRules']:
        quote = normalized(rule['evidence'])
        cited = {r['id'] for r in graph['relations'] if normalized(r['evidence']['quote']) in quote}
        if not cited or not cited <= allowed:
            raise ValueError('OBJECTIVE_SCOPE_ERROR: ' + rule['id'])
