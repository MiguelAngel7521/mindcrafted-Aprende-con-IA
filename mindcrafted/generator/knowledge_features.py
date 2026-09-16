"""Source-first structural graph, independent of puzzle designs and renderers.

A deliberately bounded bilingual relation grammar, not a semantic truth oracle.
Every accepted edge retains exact source offsets; externally supplied graphs are
recomputed before use. Unsupported prose yields fewer edges, never invented ones.
"""
from dataclasses import dataclass
import hashlib
import re

MAX_SOURCE_CHARS = 60000
MAX_RELATIONS = 512
BINARY_COMPATIBILITY = re.compile(r'\b(?:son|are) (incompatibles?|compatibles?)(?:[: ,]|$)', re.I)
# Predicates require nonempty subject and object; lists of topic words are not edges.
PREDICATE = re.compile(
    r'\b(?:depende(?:n)?\s+(?:únicamente\s+)?de|depends?\s+on|'
    r'conecta(?:do|n)?\s+(?:con|a)|connects?\s+to|relacion(?:a|es?)\s+(?:con|entre)|'
    r'recibe(?:n)?|receives?|extrae(?:n)?|extracts?|produce(?:n)?|produces?|ajusta|'
    r'permite(?:n)?|allows?|requiere(?:n)?|requires?|utiliza(?:n)?|uses?|aprende\s+con|'
    r'encuentra|reconoce|impulsa|contiene|contains?|incluye|includes?|'
    r'necesita(?:n)?|needs?|consume(?:n)?|consumes?|asigna(?:da|do|n)?|allocates?|'
    r'debe(?:n)?|must|cannot|no puede|limits?|supera(?:r|n)?|exceeds?|'
    r'es compatible con|is compatible with|es incompatible con|is incompatible with)\b|→|->', re.I)
RESOURCE = re.compile(r'\b(?:carga\w*|capacidad\w*|recurso\w*|presupuesto\w*|load\w*|capacity|resources?|budget\w*)\b', re.I)
CONTROL = re.compile(r'\b(?:configur\w*|component\w*|parámetr\w*|parameter\w*|modo\w*|modes?|módulo\w*|modules?|opci[oó]n\w*|estado\w*|states?)\b', re.I)
ALLOCATION = re.compile(r'requier|asign|super|necesita|consume|máximo|require|exceed|limit|allocat', re.I)
CONFIGURATION = re.compile(r'requier|necesita|depend|incompatible|no puede|compatible|debe|permite|require|must|cannot', re.I)
NUMBER = re.compile(r'\b(?:\d+(?:[.,]\d+)?|cero|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|zero|two|three|four|five|six|seven|eight|nine|ten)\b', re.I)


def normalized(text):
    return ' '.join(text.split()).casefold()


def _id(kind, text):
    return kind + '_' + hashlib.sha256(text.encode()).hexdigest()[:24]


def build_structure_graph(source):
    if not isinstance(source, str) or len(source) > MAX_SOURCE_CHARS:
        raise ValueError('SOURCE_BOUNDS_ERROR: expected text of at most 60000 characters')
    concepts, relations, seen = {}, [], set()
    fact_count = 0
    for segment in re.finditer(r'[^\n.;]+', source):
        raw = segment.group()
        quote = raw.strip(' •\t\r')
        text = normalized(quote)
        if len(text) < 15 or text in seen:
            continue
        seen.add(text)
        fact_count += 1
        pair = BINARY_COMPATIBILITY.search(quote)
        endpoints = re.split(r'\s+(?:y|and)\s+', quote[:pair.start()], maxsplit=1, flags=re.I) if pair else []
        match = PREDICATE.search(quote)
        if len(endpoints) == 2:
            left, right, predicate = endpoints[0], endpoints[1], pair.group(1)
        elif match:
            left, right = quote[:match.start()].strip(), quote[match.end():].strip()
            predicate = match.group()
        else:
            continue
        left, right = left.strip(), right.strip()
        if not left or not right or not re.search(r'\w', left) or not re.search(r'\w', right):
            continue
        subject, target = (_id('concept', normalized(v)) for v in (left, right))
        if subject == target:
            continue
        concepts[subject] = {'id': subject, 'label': left}
        concepts[target] = {'id': target, 'label': right}
        start = segment.start() + raw.index(quote)
        tags = ['connection']
        if re.search(r'depend|requiere|require|necesita|needs?', predicate, re.I):
            tags.append('dependency')
        if RESOURCE.search(quote) and ALLOCATION.search(quote):
            tags.append('resource')
        if CONTROL.search(quote) and CONFIGURATION.search(quote):
            tags.append('configuration')
        if re.search(r'capacidad|capacity|presupuesto|budget|no debe superar|no puede superar|cannot exceed|at most', quote, re.I):
            tags.append('capacity')
        if re.search(r'incompatib|compatib', quote, re.I):
            tags.append('compatibility')
        if re.search(r'debe|must|requiere|requires?|cannot|no puede|limit', quote, re.I):
            tags.append('constraint')
        if re.search(r'component|módulo|module', quote, re.I):
            tags.append('component')
        if re.search(r'parámetr|parameter|\bmodo\b|\bmode\b', quote, re.I):
            tags.append('parameter')
        if NUMBER.search(right):
            tags.append('quantity')
        if 'quantity' in tags and 'capacity' in tags:
            tags.append('quantifiedCapacity')
        relations.append({'id': _id('relation', text), 'subject': subject, 'object': target,
                          'predicate': predicate, 'features': tags,
                          'evidence': {'start': start, 'end': start + len(quote), 'quote': quote}})
        if len(relations) > MAX_RELATIONS:
            raise ValueError('SOURCE_BOUNDS_ERROR: too many grounded relations')
    return {'format': 'mindcrafted-educational-structure', 'version': 1,
            'sourceHash': hashlib.sha256(source.encode()).hexdigest(), 'sourceLength': len(source),
            'factCount': fact_count, 'concepts': list(concepts.values()), 'relations': relations}


def validate_structure_graph(graph, source):
    if graph != build_structure_graph(source):
        raise ValueError('GROUNDING_ERROR: structure, predicates or evidence differ from source analysis')


@dataclass(frozen=True)
class LearningObjective:
    id: str
    text: str
    relation_ids: tuple[str, ...] | None = None
    concept_ids: tuple[str, ...] | None = None
    intent: str = 'explore'

    def __post_init__(self):
        if (not isinstance(self.id, str) or not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_-]{0,63}', self.id)
                or not isinstance(self.text, str) or not 1 <= len(self.text) <= 2000
                or self.intent not in ('explore', 'connect', 'distribute', 'configure')):
            raise ValueError('OBJECTIVE_ERROR: id, text and supported intent required')
        for ids in (self.relation_ids, self.concept_ids):
            if ids is not None and (not isinstance(ids, tuple) or len(ids) > 1024 or any(not isinstance(i, str) for i in ids)):
                raise ValueError('OBJECTIVE_ERROR: references must be bounded tuples of IDs')


def scoped_relations(graph, objective):
    relations = graph['relations']
    if objective.relation_ids is not None:
        ids = set(objective.relation_ids)
        if not ids <= {r['id'] for r in relations}:
            raise ValueError('REFERENCE_ERROR: objective has unknown relations')
        relations = [r for r in relations if r['id'] in ids]
    if objective.concept_ids is not None:
        ids = set(objective.concept_ids)
        if not ids <= {c['id'] for c in graph['concepts']}:
            raise ValueError('REFERENCE_ERROR: objective has unknown concepts')
        relations = [r for r in relations if {r['subject'], r['object']} <= ids]
    return relations


def extract_features(graph, source, objective):
    validate_structure_graph(graph, source)
    relations = scoped_relations(graph, objective)
    features = {name + 'Count': sum(name in r['features'] for r in relations) for name in
                ('dependency', 'connection', 'resource', 'capacity', 'quantity', 'constraint',
                 'component', 'parameter', 'compatibility', 'configuration', 'quantifiedCapacity')}
    features['featureEvidence'] = {tag: [r['id'] for r in relations if tag in r['features']]
                                   for tag in ('connection', 'resource', 'configuration', 'quantifiedCapacity')}
    features.update(conceptCount=len({r[k] for r in relations for k in ('subject', 'object')}),
                    relationCount=len(relations), relationIds=[r['id'] for r in relations])
    return features


def objective_from_evidence(graph, text, quotes, *, objective_id='puzzle', intent='explore'):
    """Use only complete source relations actually cited by this learning objective."""
    evidence = [normalized(q) for q in quotes]
    ids = tuple(r['id'] for r in graph['relations'] if any(normalized(r['evidence']['quote']) in q for q in evidence))
    return LearningObjective(objective_id, text, relation_ids=ids, intent=intent)
