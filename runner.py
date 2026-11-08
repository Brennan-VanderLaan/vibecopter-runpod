#!/usr/bin/env python3
"""Bounded process execution, isolated profile, and honest process-only receipts."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import uuid

from probe import probe


def run(executable, lane, timeout, extra, output_root):
    if os.geteuid() == 0:
        raise ValueError('Unreal must run as a non-root user; use run-game or SSH as tester')
    exe = Path(executable).resolve(strict=True)
    if not exe.is_file() or not os.access(exe, os.X_OK):
        raise ValueError('Executable must be an executable regular file')
    if timeout < 1 or timeout > 86400:
        raise ValueError('Timeout must be between 1 and 86400 seconds')
    # Keep test identity/profile and lane selection under the runner's control.
    forbidden = ('-nullrhi', '-vulkan', '-opengl', '-dx', '-d3d', '-renderoffscreen',
                 '-userdir', '-profile', '-saveroot', '-scratch', '-bugcrushsession',
                 '-log', '-abslog', '-graphicsadapter', '-prefer')
    if any(a.lower().startswith(forbidden) for a in extra):
        raise ValueError('Extra arguments cannot override lane, profile, log or GPU selection')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = Path(output_root).resolve() / uuid.uuid4().hex
    out.mkdir(parents=True, exist_ok=False)
    profile = out / 'profile'
    profile.mkdir()
    hardware = probe()
    (out / 'hardware.json').write_text(json.dumps(hardware, indent=2))
    args = [str(exe), '-unattended', '-nosplash', '-stdout', '-FullStdOutLogOutput',
            '-UserDir=' + str(out / 'user'), '-SaveRoot=' + str(profile),
            '-ScratchRoot=' + str(out.parent), '-ScratchSession=' + out.name,
            '-abslog=' + str(out / 'Unreal.log')]
    args += ['-nullrhi', '-nosound'] if lane == 'smoke' else ['-vulkan', '-RenderOffscreen', '-graphicsadapter=0']
    args += extra
    receipt = {'schema': 1, 'lane': lane, 'started_utc': stamp,
               'executable': str(exe), 'executable_sha256': file_hash(exe),
               'argv': args, 'hardware': hardware, 'timeout_seconds': timeout,
               'scope': 'Process health only; no gameplay, visual quality, performance or SteamOS acceptance',
               'result': 'PREFLIGHT_FAILED', 'exit_code': None, 'timed_out': False}
    start = time.monotonic()
    if lane != 'gpu' or hardware['gpu_preflight_pass']:
        with (out / 'console.log').open('w') as log:
            try:
                p = subprocess.Popen(args, cwd=exe.parent, stdout=log, stderr=subprocess.STDOUT,
                                     start_new_session=True)
                try:
                    p.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    receipt['timed_out'] = True
                    os.killpg(p.pid, signal.SIGTERM)
                    try:
                        p.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(p.pid, signal.SIGKILL)
                        p.wait()
                finally:
                    # Also reap any surviving child process in this owned group.
                    try:
                        os.killpg(p.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                receipt['exit_code'] = p.returncode
                receipt['result'] = ('PROCESS_EXIT_ZERO' if p.returncode == 0 and not receipt['timed_out']
                                     else 'PROCESS_FAILED')
            except OSError as e:
                receipt['result'] = 'LAUNCH_FAILED'
                receipt['error'] = str(e)
    receipt['elapsed_seconds'] = round(time.monotonic() - start, 3)
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2))
    print(str(out / 'receipt.json'), flush=True)
    return 0 if receipt['result'] == 'PROCESS_EXIT_ZERO' else 1


def file_hash(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lane', choices=('smoke', 'gpu'), required=True)
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('--output-root', default='/workspace/runs')
    parser.add_argument('executable')
    parser.add_argument('extra', nargs=argparse.REMAINDER)
    a = parser.parse_args()
    extra = a.extra[1:] if a.extra[:1] == ['--'] else a.extra
    try:
        raise SystemExit(run(a.executable, a.lane, a.timeout, extra, a.output_root))
    except (ValueError, OSError) as e:
        parser.error(str(e))
