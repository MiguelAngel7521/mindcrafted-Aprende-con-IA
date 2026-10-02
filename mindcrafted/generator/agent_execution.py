"""Execution budgets for CPU/browser work; timed-out workers cannot publish."""
import asyncio
import json
import os
import signal
import sys


async def worker(job, timeout):
    process=await asyncio.create_subprocess_exec(sys.executable,'-m','mindcrafted.generator.agent_worker',
        stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,
        start_new_session=True)
    try:
        out,err=await asyncio.wait_for(process.communicate(json.dumps(job).encode()),timeout)
    except BaseException:
        if process.returncode is None:
            os.killpg(process.pid,signal.SIGKILL)
            await process.wait()
        raise
    if process.returncode:
        raise ValueError('DETERMINISTIC_WORKER_FAILURE')
    if len(out)>8_000_000:
        raise ValueError('WORKER_OUTPUT_SIZE_EXCEEDED')
    result=json.loads(out)
    if not result['ok']:
        raise ValueError(result['error'])
    return result['value']
