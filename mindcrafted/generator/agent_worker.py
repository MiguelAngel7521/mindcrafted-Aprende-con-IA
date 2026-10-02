"""Bounded subprocess entry for existing deterministic validators and browser gate."""
import json
import sys


def execute(job):
    from .world import compile_world, validate_world
    from .world_boss import compile_boss
    from .world_package import quality_gate
    operation=job['operation']
    if operation=='compile':
        world=(compile_boss(job['candidate'],job['source'],prior_skills=job['priorSkills'])
               if job['boss'] else compile_world(job['candidate'],job['source']))
        report=validate_world(world,job['source'])
        if not report['ok']:
            raise ValueError('; '.join(report['errors']))
        return {'world':world,'report':report}
    if operation=='export':
        from pathlib import Path
        from .world_package import render_html,write_world_package
        from .world_campaign import write_campaign
        package=job['package']
        if not validate_world(job['world'],job['source'])['ok']:
            raise ValueError('PUBLICATION_REJECTED')
        out=Path(job['output'])
        if package.get('campaign'):
            write_campaign(package,out)
        elif job['testOnly']:
            out.mkdir(parents=True,exist_ok=True)
            (out/'index.html').write_text(render_html(package),encoding='utf-8')
            (out/'game.pkg.json').write_text(json.dumps(package,ensure_ascii=False,indent=2),encoding='utf-8')
        else:
            write_world_package(package,job['source'],package['quality'],out)
        return {'exported':True}
    if operation=='gate':
        return quality_gate(job['world'],job['source'])
    raise ValueError('WORKER_OPERATION_NOT_ALLOWED')


if __name__=='__main__':
    try:
        result={'ok':True,'value':execute(json.load(sys.stdin))}
    except (ValueError,TypeError,KeyError) as error:
        result={'ok':False,'error':str(error)[:6000]}
    print(json.dumps(result,ensure_ascii=False))
