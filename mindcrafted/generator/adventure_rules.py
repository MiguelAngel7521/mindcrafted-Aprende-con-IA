"""Modelos acotados para redes y algoritmos; las respuestas se calculan localmente."""
from collections import deque


def validate_technical(kind, data):
    from .practice import integer, text, normalized
    if kind == 'packet_route':
        nodes = data.get('nodes')
        if not isinstance(nodes, list) or not 3 <= len(nodes) <= 6:
            raise ValueError('La red necesita de tres a seis nodos')
        nodes = [text(n, 'nodo', maximum=55) for n in nodes]
        if len(set(map(normalized, nodes))) != len(nodes): raise ValueError('Nodos duplicados')
        start = integer(data.get('start'), 'inicio', 0, len(nodes)-1)
        target = integer(data.get('target'), 'destino', 0, len(nodes)-1)
        if start == target: raise ValueError('El origen y destino deben ser diferentes')
        edges = data.get('edges')
        if not isinstance(edges, list) or not 2 <= len(edges) <= 15: raise ValueError('Conexiones inválidas')
        clean = []
        for edge in edges:
            if not isinstance(edge, list) or len(edge) != 2: raise ValueError('Una conexión tiene dos índices')
            a,b = (integer(v, 'nodo conectado', 0, len(nodes)-1) for v in edge)
            if a == b or [a,b] in clean: raise ValueError('Conexión duplicada o circular sobre sí misma')
            clean.append([a,b])
        seen={start}; queue=deque([start])
        while queue:
            a=queue.popleft()
            for origin,destination in clean:
                if origin==a and destination not in seen: seen.add(destination);queue.append(destination)
        if target not in seen: raise ValueError('La red no tiene ruta al destino')
        return dict(nodes=nodes, edges=clean, start=start, target=target)
    initial=integer(data.get('initial'), 'valor inicial', -9, 9)
    operations=data.get('operations')
    if not isinstance(operations,list) or not 3<=len(operations)<=5: raise ValueError('Se necesitan de tres a cinco operaciones')
    result=initial; states=[]; clean=[]
    for item in operations:
        if not isinstance(item,dict) or item.get('op') not in ('add','subtract','multiply'): raise ValueError('Operación no admitida')
        value=integer(item.get('value'),'operando',-9,9)
        result=result+value if item['op']=='add' else result-value if item['op']=='subtract' else result*value
        if abs(result)>99: raise ValueError('Los estados del algoritmo deben estar entre -99 y 99')
        clean.append(dict(op=item['op'],value=value));states.append(result)
    return dict(initial=initial,operations=clean,states=states)


def infer_world(source, subject=''):
    import re
    import unicodedata
    plain=unicodedata.normalize('NFKD',subject+' '+source).encode('ascii','ignore').decode().lower()
    if re.search(r'programaci|algoritm|base de datos|bases de datos|redes|router|enrut|paquetes de datos|inteligencia artificial|software|informatica|servidor|computaci',plain): return 'technology'
    return None
