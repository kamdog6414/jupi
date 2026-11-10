#!/usr/bin/python3
"""Explicit, source-pinned finite CPU/GPU performance gates; benchmark data only."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import uuid

CONFIG = Path('/etc/jupi/gpu-pipeline-bench.json')
STATE = Path('/var/lib/jupi-agent/performance-gates')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def software():
    if CONFIG.is_symlink() or CONFIG.stat().st_uid != 0 or CONFIG.stat().st_mode & 0o022:
        raise ValueError('Software manifest ownership or permissions differ')
    config = json.loads(CONFIG.read_bytes())
    if config.get('schema') != 'jupi.gpu.pipeline.software.v1':
        raise ValueError('Software manifest schema differs')
    for item in config['components'].values():
        path = Path(item['path'])
        if not path.is_absolute() or path.is_symlink():
            raise ValueError('Component path differs')
        info = path.stat()
        if info.st_uid != 0 or info.st_mode & 0o022 or digest(path) != item['sha256']:
            raise ValueError('Reviewed component differs: ' + path.name)
    return config


def write(path, value):
    with path.open('x') as f:
        json.dump(value, f, sort_keys=True, indent=2, allow_nan=False)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())


def environment():
    memory = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        k, v = line.split(':', 1)
        if k in ('MemAvailable', 'SwapFree'):
            memory[k + '_bytes'] = int(v.split()[0]) * 1024
    return {'utc': now(), 'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'affinity': sorted(os.sched_getaffinity(0)), 'load_average': list(os.getloadavg()),
            'resources': memory,
            'tctl_raw': Path('/sys/class/hwmon/hwmon1/temp1_input').read_text().strip(),
            'thermal_scope': 'Relative k10temp control value; not calibrated die temperature'}


def verify(identifier):
    if str(uuid.UUID(identifier)) != identifier:
        raise ValueError('Canonical run UUID required')
    directory = STATE / identifier
    if directory.is_symlink():
        raise ValueError('Symlink run directory refused')
    receipt = json.loads((directory / 'receipt.json').read_bytes())
    if receipt.get('run_id') != identifier or receipt.get('state') != 'passed':
        raise ValueError('No passed receipt for that run')
    if receipt.get('schema') != 'jupi.performance.gate.v1':
        raise ValueError('Receipt schema differs')
    if set(receipt['artifacts']) != {'request.json', 'software.json', 'raw.json', 'stderr.txt'}:
        raise ValueError('Artifact manifest differs')
    for name, expected in receipt['artifacts'].items():
        path = directory / name
        if path.is_symlink() or path.stat().st_size > 2 * 1024**2 or digest(path) != expected:
            raise ValueError('Stored artifact changed: ' + name)
    result = json.loads((directory / 'raw.json').read_bytes())
    request = json.loads((directory / 'request.json').read_bytes())
    if result['samples'] != receipt['samples'] or result['samples'] != request['samples'] or result['steps'] != request['steps']:
        raise ValueError('Workload binding differs')
    if any(lane['mismatches'] for lane in result['lanes']):
        raise ValueError('Numeric qualification differs')
    return receipt


def run(args):
    config = software()
    # Batch placement is an explicit option, confined to this process and children.
    if args.batch:
        os.sched_setaffinity(0, set(range(os.cpu_count())))
    before = environment()
    if before['resources']['MemAvailable_bytes'] < 512 * 1024**2:
        raise RuntimeError('Insufficient memory headroom for this bounded experiment')
    identifier = str(uuid.uuid4())
    directory = STATE / identifier
    directory.mkdir(mode=0o700, parents=True)
    request = {'samples': args.samples, 'steps': args.steps, 'reps': args.reps,
               'staging_policy': args.staging_policy, 'batch_placement': args.batch,
               'classification': 'synthetic performance benchmark; not sensor data'}
    write(directory / 'request.json', request)
    write(directory / 'software.json', config)
    command = [config['components']['binary']['path'], 'bench',
               config['components']['shader']['path'], str(args.samples),
               str(args.steps), str(args.reps), args.staging_policy]
    env = dict(os.environ, LD_LIBRARY_PATH=config['compat_library_directory'],
               OMP_NUM_THREADS='4', OMP_DYNAMIC='FALSE', OMP_PROC_BIND='spread', OMP_PLACES='cores')
    receipt = {'schema': 'jupi.performance.gate.v1', 'run_id': identifier,
               'state': 'failed', 'environment_before': before,
               'samples': args.samples, 'steps': args.steps,
               'scope': 'Finite synthetic array recurrence. No model, physical calibration, peak GFLOPS, energy or whole-system speed claim.'}
    try:
        result = subprocess.run(command, capture_output=True, env=env, timeout=60)
        (directory / 'raw.json').write_bytes(result.stdout[:2*1024**2])
        (directory / 'stderr.txt').write_bytes(result.stderr[:65536])
        if result.returncode or len(result.stdout) > 2*1024**2:
            raise RuntimeError('Benchmark failed; no alternate backend was substituted')
        value = json.loads(result.stdout)
        expected_modes = {'roundtrip', 'resident', 'fused', 'cpu', 'cpu-fused-1', 'cpu-fused-4', 'cpu-staged-4'}
        if value['samples'] != args.samples or value['steps'] != args.steps:
            raise ValueError('Workload differs')
        if {lane['mode'] for lane in value['lanes']} != expected_modes:
            raise ValueError('Lane set differs')
        for lane in value['lanes']:
            if lane['mismatches'] or len(lane['seconds']) != args.reps or any(t <= 0 for t in lane['seconds']):
                raise ValueError('Finite numeric/timing qualification failed')
        receipt.update(state='passed', median_seconds={x['mode']: statistics.median(x['seconds']) for x in value['lanes']},
                       setup_seconds=value['setup_seconds'], device=value['device'],
                       verification=value['verification'], timing_scope=value['timing_scope'])
    except Exception as error:
        receipt.update(error_class=type(error).__name__, error=str(error)[:300])
    receipt['environment_after'] = environment()
    receipt['artifacts'] = {p.name: digest(p) for p in directory.iterdir() if p.is_file()}
    write(directory / 'receipt.json', receipt)
    print(json.dumps({'run_id': identifier, 'state': receipt['state'], 'receipt': str(directory / 'receipt.json'),
                      'median_seconds': receipt.get('median_seconds'), 'error': receipt.get('error')}, indent=2))
    if receipt['state'] == 'passed':
        verify(identifier)
        return 0
    return 1


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='action', required=True)
    sub.add_parser('status')
    v = sub.add_parser('verify'); v.add_argument('run_id')
    r = sub.add_parser('run')
    r.add_argument('--samples', type=int, default=1048576)
    r.add_argument('--steps', type=int, default=8)
    r.add_argument('--reps', type=int, default=7)
    r.add_argument('--batch', action='store_true')
    r.add_argument('--staging-policy', choices=('cached', 'first-coherent'), default='cached')
    args = p.parse_args()
    if args.action == 'status':
        config = software()
        print(json.dumps({'software_verified': True, 'software_id': config['software_id'],
                          'default_staging': 'host-visible, host-coherent, host-cached',
                          'native_job': 'jupi-agent run --timeout 90 -- /usr/local/bin/jupi-pipeline-bench run --batch',
                          'policy': 'Explicit benchmark only; no service or automatic routing changes'}, indent=2))
        return 0
    if args.action == 'verify':
        print(json.dumps({'run_id': args.run_id, 'state': verify(args.run_id)['state'], 'artifacts_verified': 4}))
        return 0
    if not 1 <= args.samples <= 4194304 or not 1 <= args.steps <= 32 or not 1 <= args.reps <= 15:
        p.error('Bounds: samples 1..4194304, steps 1..32, repetitions 1..15')
    return run(args)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'error_class': type(error).__name__, 'error': str(error)[:300]}), file=sys.stderr)
        raise SystemExit(1)
