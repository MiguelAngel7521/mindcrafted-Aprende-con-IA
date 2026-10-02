"""Application-owned publication; workers can only write to disposable staging."""
from copy import deepcopy
from pathlib import Path
import tempfile
import time

from .agent_execution import worker
from .structured_schema import schema_hash
from .world import world_hash
from .world_package import CHECKS, check_judge


class PublicationAuthority:
    def __init__(self, output_dir, *, allow_real=False):
        self.output_dir=Path(output_dir)
        self.allow_real=allow_real

    async def publish(self, session):
        s=session
        if s.state!='PACKAGED' or s._busy:
            raise ValueError('INVALID_AGENT_TRANSITION: package first')
        started=time.monotonic()
        event={'generationId':s.generation_id,'state':s.state,'tool':'publication_authority',
            'provider':s._provider,'model':s._model,'attempt':1,'repairNumber':s.repairs,
            'schemaVersion':'agent-tools-1','inputHash':schema_hash(s._package),
            'outputHash':None,'result':'REJECTED','errorCategory':None}
        s._busy=True
        try:
            s.assert_budget()
            package=deepcopy(s._package)
            report=s._gate
            if (schema_hash(package)!=s._package_hash or not report
                or report.get('worldHash')!=world_hash(s._world) or report.get('errors')
                or not all(report['checks'].get(k) is True for k in CHECKS)
                or not check_judge(s._judge)):
                raise ValueError('PUBLICATION_REJECTED')
            if s._test_only:
                quality=package['regionQuality'][-1] if 'regionQuality' in package else package['quality']
                if quality['approved'] or not package['developmentDemo'] or quality['judgeAuthority']!='TEST_ONLY_JUDGE':
                    raise ValueError('TEST_ONLY_PUBLICATION_REQUIRED')
            elif not self.allow_real:
                raise ValueError('PUBLICATION_NOT_AUTHORIZED')
            # No overwrite of unrelated application data or previously published directories.
            if self.output_dir.exists():
                raise ValueError('PUBLICATION_DESTINATION_EXISTS')
            self.output_dir.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.TemporaryDirectory(dir=self.output_dir.parent,prefix='.agent-staging-') as staging:
                target=Path(staging)/'package'
                await worker({'operation':'export','package':package,'world':s._world,'source':s._source,
                    'output':str(target),'testOnly':s._test_only},
                    min(s.budgets.tool_timeout,s.budgets.total_timeout-(time.monotonic()-s._started)))
                s.assert_budget()
                if schema_hash(s._package)!=s._package_hash:
                    raise ValueError('CANDIDATE_CHANGED')
                target.rename(self.output_dir)
            s.state='PUBLISHED'
            event.update(result='TEST_ONLY' if s._test_only else 'PUBLISHED',outputHash=s._package_hash)
            return str(self.output_dir/'index.html')
        except BaseException as error:
            event['errorCategory']='PUBLICATION_TIMEOUT' if isinstance(error,TimeoutError) else 'PUBLICATION_REJECTED'
            s.state='REJECTED'
            raise
        finally:
            s._busy=False
            event.update(durationMs=round((time.monotonic()-started)*1000),stateAfter=s.state)
            s._audit.append(event)
