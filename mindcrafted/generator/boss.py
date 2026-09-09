"""Jefes reproducibles compuestos con conceptos ya validados; sin otra llamada IA."""
from copy import deepcopy
import random


def build_boss(packages, seed, partial=False):
    if not packages: raise ValueError('El jefe requiere lecciones disponibles')
    rng=random.Random(seed)
    pools=[]
    for package in packages:
        cfg=package['config']; puzzles=cfg['practice']['puzzles']
        if not puzzles: raise ValueError('Lección sin conceptos para el jefe')
        pool=[]
        for puzzle in puzzles:
            p=deepcopy(puzzle);p['originChunk']=cfg['chunkId'];p['originTitle']=cfg['title'];pool.append(p)
        rng.shuffle(pool);pools.append(pool)
    candidates=[]
    for i in range(max(map(len,pools))):
        for pool in pools:
            if i<len(pool): candidates.append(pool[i])
    # Prefer distinct mechanics while retaining lessons of origin.
    chosen=[]; kinds=set()
    for p in candidates:
        if p['kind'] not in kinds: chosen.append(p);kinds.add(p['kind'])
        if len(chosen)==3: break
    for p in candidates:
        if len(chosen)==3: break
        if not any(q['originChunk']==p['originChunk'] and q['id']==p['id'] for q in chosen): chosen.append(p)
    if len(chosen)!=3: raise ValueError('El jefe necesita tres retos diferentes')
    world=packages[-1]['config']['practice']['world']
    family={'technology':'Centinela del Nexo','mathematics':'Guardián del Equilibrio','biology':'Custodio del Bosque','laboratory':'Autómata de Energía'}[world]
    variant={'technology':1,'laboratory':1,'mathematics':2,'biology':3}[world]
    return dict(name=family+' '+rng.choice(['Ámbar','Delta','Aurora','Ónice']), seed=seed,
                sprite=f'adventure-boss-{variant}', crest=rng.randrange(3), pattern=rng.choice(['rain','cross','wave']),
                partial=partial, phases=chosen, status='ready')
