#!/usr/bin/python3
"""Bounded observations for the JUPI instrument; no command or message dispatch."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import sqlite3
import subprocess

STATE = Path('/var/lib/jupi-agent/observatory')
CONFIG = Path('/etc/jupi/observatory.json')
PEERS = {'jupi': 8765, 'nikolai': 18765, 'roach': 18766}


def now():
    return datetime.now(timezone.utc).isoformat()


def text(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def number(path):
    try:
        return int(text(path))
    except (TypeError, ValueError):
        return None


def age(utc, reference=None, maximum=900):
    try:
        stamp = datetime.fromisoformat(utc.replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            raise ValueError('Timezone required')
        seconds = ((reference or datetime.now(timezone.utc)) - stamp).total_seconds()
        return {'seconds': round(seconds, 1), 'fresh': -60 <= seconds <= maximum}
    except (ValueError, TypeError, AttributeError):
        return {'seconds': None, 'fresh': False}


def sensors(root=Path('/sys/class/hwmon'), family=None):
    """Read exported attributes only. Limits are not power/temperature samples."""
    values = []
    for device in sorted(root.glob('hwmon*')):
        driver = text(device / 'name') or 'unknown'
        for path in sorted(device.glob('*_input')):
            match = re.fullmatch(r'(temp|power|fan)([0-9]+)_input', path.name)
            if not match:
                continue
            kind, channel = match.groups()
            raw = number(path)
            if raw is None:
                continue
            prefix = kind + channel
            label = text(device / (prefix + '_label')) or prefix
            relative = kind == 'temp' and driver == 'k10temp' and channel == '1' and (family is None or family < 0x17)
            meaning = ('relative_temperature_control' if relative else 'hwmon_temperature') if kind == 'temp' else {'power': 'reported_power', 'fan': 'fan_speed'}[kind]
            scale = {'temp': 1000, 'power': 1000000, 'fan': 1}[kind]
            unit = 'control_degrees' if relative else {'temp': 'degC', 'power': 'W', 'fan': 'RPM'}[kind]
            limits = {suffix: number(device / (prefix + '_' + suffix)) for suffix in ('max', 'crit', 'crit_hyst')}
            alarms = {suffix: number(device / (prefix + '_' + suffix)) for suffix in ('alarm', 'crit_alarm', 'fault')}
            values.append({'driver': driver, 'path': str(path), 'label': label, 'raw': raw,
                           'value': raw / scale, 'unit': unit, 'meaning': meaning,
                           'limits_raw': limits, 'alarms': alarms,
                           'critical_limit_reached': bool(limits['crit'] and raw >= limits['crit'] and alarms['fault'] != 1)})
    return values


def inventory():
    cpu = text('/proc/cpuinfo') or ''
    match = re.search(r'^cpu family\s*:\s*(\d+)', cpu, re.M)
    family = int(match.group(1)) if match else None
    devices = {name: sorted(str(p) for p in Path('/dev').glob(pattern)) for name, pattern in
               {'gpu_render': 'dri/renderD*', 'cameras': 'video*', 'usb_serial': 'ttyUSB*', 'usb_acm': 'ttyACM*', 'i2c_buses': 'i2c-*'}.items()}
    networks = [{'name': p.name, 'state': text(p / 'operstate'), 'carrier': number(p / 'carrier'),
                 'speed_mbps': number(p / 'speed')} for p in sorted(Path('/sys/class/net').glob('*')) if p.name != 'lo']
    usb = []
    for p in sorted(Path('/sys/bus/usb/devices').glob('*')):
        vid, pid = text(p / 'idVendor'), text(p / 'idProduct')
        if vid and pid:
            usb.append({'bus_device': p.name, 'vendor_id': vid, 'product_id': pid, 'product': text(p / 'product')})
    return {'kernel': platform.release(), 'architecture': platform.machine(), 'cpu_family': family,
            'logical_cpus': os.cpu_count(), 'devices': devices, 'network_interfaces': networks,
            'usb': usb, 'sensors': sensors(family=family),
            'thermal_scope': 'k10temp temp1 on this pre-17h CPU is relative Tctl, not a calibrated die temperature. Only exported kernel attributes are read.',
            'physical_actuation_configured': False, 'device_nodes_opened': False}


def resources():
    memory = {line.split(':')[0]: int(line.split()[1]) * 1024
              for line in (text('/proc/meminfo') or '').splitlines()
              if line.startswith(('MemTotal:', 'MemAvailable:', 'SwapTotal:', 'SwapFree:'))}
    storage = {}
    for path in ('/', '/ps4hdd'):
        v = os.statvfs(path)
        storage[path] = {'available_bytes': v.f_bavail * v.f_frsize, 'total_bytes': v.f_blocks * v.f_frsize}
    pressure = {p.name: text(p) for p in Path('/proc/pressure').glob('*')}
    return {'memory_bytes': memory, 'storage': storage, 'pressure': pressure,
            'pressure_supported': bool(pressure), 'load_average': list(os.getloadavg()),
            'uptime_seconds': float((text('/proc/uptime') or '0').split()[0])}


def run_json(argv, timeout=15):
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        data = json.loads(result.stdout)
        if not isinstance(data, dict):
            raise ValueError('Object required')
        return {'code': result.returncode, 'data': data}
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        return {'code': -1, 'error_class': type(error).__name__}


def peer_health(expected_pin):
    source = Path('/home/pi/fc-link/fcl_cluster.py')
    try:
        if hashlib.sha256(source.read_bytes()).hexdigest() != expected_pin:
            raise ValueError('FC-Link client source differs from its reviewed pin')
        spec = importlib.util.spec_from_file_location('jupi_native_fcl_client', source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except (OSError, ValueError, ImportError):
        return {name: {'ok': False, 'error_class': 'ClientUnavailableOrChanged'} for name in PEERS}

    def check(item):
        name, port = item
        try:
            response = module.FCLink('127.0.0.1', port, timeout=4).health()
            if not isinstance(response, dict) or response.get('ok') is not True:
                raise ValueError('Peer health response invalid')
            return name, {'ok': True, 'version': response.get('version'), 'peer_host': response.get('host'),
                          'peer_time': response.get('time'), 'queue': response.get('queue')}
        except Exception as error:
            # Never persist exception text from transports or key loaders.
            return name, {'ok': False, 'error_class': type(error).__name__}

    with ThreadPoolExecutor(max_workers=3) as pool:
        return dict(pool.map(check, PEERS.items()))


def assess(snapshot, minimum_backing=16 * 1024**3):
    issues = []
    if snapshot['system'].get('runtime_healthy') is not True:
        issues.append('native_runtime_check_failed')
    if snapshot['cluster'].get('instrument_cluster_ready') is not True:
        issues.append('local_cluster_check_failed')
    if snapshot['castor_refresh']['code'] != 0 or not snapshot['castor_freshness']['fresh']:
        issues.append('castor_read_refresh_unavailable_or_stale')
    for name, value in snapshot['peer_health'].items():
        if not value.get('ok'):
            issues.append('peer_health_unavailable:' + name)
    if snapshot['resources']['storage']['/ps4hdd']['available_bytes'] < minimum_backing:
        issues.append('internal_backing_headroom_below_reserve')
    if snapshot['resources']['memory_bytes'].get('MemAvailable', 0) < 256 * 1024**2:
        issues.append('available_memory_below_256MiB')
    if snapshot['clock'].get('synchronized') is not True:
        issues.append('clock_not_confirmed_synchronized')
    for value in snapshot['hardware']['sensors']:
        if value['critical_limit_reached'] or value['alarms'].get('crit_alarm') == 1:
            issues.append('kernel_sensor_critical:' + value['driver'] + ':' + value['label'])
        if value['alarms'].get('fault') == 1:
            issues.append('kernel_sensor_fault:' + value['driver'] + ':' + value['label'])
    return sorted(set(issues))


def settings():
    config = json.loads(CONFIG.read_text())
    if config.get('schema') != 'jupi.observatory.config.v1':
        raise ValueError('Observer config schema differs')
    if type(config.get('keep_samples')) is not int or not 12 <= config['keep_samples'] <= 2016:
        raise ValueError('Observer retention is outside its bound')
    if not re.fullmatch('[0-9a-f]{64}', config.get('fcl_client_sha256', '')):
        raise ValueError('FC-Link source pin required')
    return config


def collect(config):
    system = run_json(['/usr/local/bin/jupi-system', '--json'])
    refresh = run_json(['/usr/local/bin/jupi-castor', 'sync'], timeout=40)
    cluster = run_json(['/usr/local/bin/jupi-cluster', 'status'], timeout=25)
    s, c = system.get('data', {}), cluster.get('data', {})
    castor = refresh.get('data') or {}
    if not castor:
        try:
            castor = json.loads(c.get('verification', {}).get('castor', {}).get('stdout', '{}'))
        except ValueError:
            castor = {}
    try:
        clock = subprocess.run(['timedatectl', 'show', '-p', 'NTPSynchronized', '--value'],
                               capture_output=True, text=True, timeout=5)
        synchronized = clock.returncode == 0 and clock.stdout.strip() == 'yes'
    except (OSError, subprocess.TimeoutExpired):
        synchronized = False
    snapshot = {'schema': 'jupi.observatory.snapshot.v1', 'utc': now(),
                'boot_id': text('/proc/sys/kernel/random/boot_id'),
                'system': {k: s.get(k) for k in ('runtime_healthy', 'runtime_issues', 'root', 'backing_image', 'sleep_targets')},
                'cluster': {'instrument_cluster_ready': c.get('instrument_cluster_ready'), 'issues': c.get('issues'),
                            'memberships': {k: v.get('state') for k, v in c.get('memberships', {}).items()}},
                'castor_refresh': {'code': refresh['code'], 'rows': castor.get('rows'), 'tip': castor.get('tip'),
                                   'observed_utc': castor.get('utc')},
                'castor_freshness': age(castor.get('utc')), 'hardware': inventory(), 'resources': resources(),
                'peer_health': peer_health(config['fcl_client_sha256']),
                'clock': {'synchronized': synchronized},
                'policy': {'external_messages_sent': 0, 'ledger_rows_appended': 0, 'automatic_remediation': False},
                'scope': 'Timestamped instrument observations. Peer failures affect observed availability, not enrollment. No fan, device, boot or actuator writes.'}
    snapshot['issues'] = assess(snapshot)
    snapshot['health'] = 'OK' if not snapshot['issues'] else 'DEGRADED'
    return snapshot


def store(snapshot, keep):
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    with closing(sqlite3.connect(STATE / 'observations.sqlite3', timeout=10)) as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA synchronous=FULL')
        db.execute('PRAGMA journal_size_limit=1048576')
        db.execute('PRAGMA wal_autocheckpoint=64')
        db.execute('CREATE TABLE IF NOT EXISTS samples(id INTEGER PRIMARY KEY,utc TEXT,health TEXT,body TEXT)')
        previous = db.execute('SELECT body FROM samples ORDER BY id DESC LIMIT 1').fetchone()
        old = json.loads(previous[0]) if previous else {}
        transition = old.get('issues') != snapshot['issues'] or old.get('boot_id') != snapshot['boot_id']
        db.execute('INSERT INTO samples(utc,health,body) VALUES(?,?,?)',
                   (snapshot['utc'], snapshot['health'], json.dumps(snapshot, separators=(',', ':'))))
        db.execute('DELETE FROM samples WHERE id NOT IN (SELECT id FROM samples ORDER BY id DESC LIMIT ?)', (keep,))
        count = db.execute('SELECT count(*) FROM samples').fetchone()[0]
        db.commit()
    return {'utc': snapshot['utc'], 'health': snapshot['health'], 'issues': snapshot['issues'],
            'transition': transition, 'stored_samples': count, 'external_messages_sent': 0}


def saved(limit=1):
    path = STATE / 'observations.sqlite3'
    if not path.is_file():
        return []
    with closing(sqlite3.connect('file:' + str(path) + '?mode=ro', uri=True, timeout=5)) as db:
        return [json.loads(row[0]) for row in db.execute('SELECT body FROM samples ORDER BY id DESC LIMIT ?', (limit,))]


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('collect', 'status', 'history', 'inventory'))
    parser.add_argument('--record', action='store_true')
    parser.add_argument('--limit', type=int, default=10, choices=range(1, 101), metavar='1..100')
    args = parser.parse_args()
    if args.record and args.action != 'collect':
        parser.error('--record is only valid with collect')
    if args.action == 'inventory':
        result = inventory()
    elif args.action == 'collect':
        config = settings()
        STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
        with (STATE / 'collect.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                print(json.dumps({'state': 'collection_already_running'}))
                return 0
            snapshot = collect(config)
            result = store(snapshot, config['keep_samples']) if args.record else snapshot
    else:
        records = saved(args.limit if args.action == 'history' else 1)
        if args.action == 'history':
            result = [{'utc': r['utc'], 'boot_id': r['boot_id'], 'health': r['health'], 'issues': r['issues']} for r in records]
        elif records:
            result = records[0]
            result['sample_freshness'] = age(result['utc'])
            if not result['sample_freshness']['fresh']:
                result['health'] = 'DEGRADED'
                result['issues'] = sorted(set(result['issues'] + ['observer_sample_stale']))
        else:
            result = {'health': 'UNAVAILABLE', 'issues': ['no_saved_observation']}
    print(json.dumps(result, indent=2))
    # Stored degraded observations are successful collection, so outages do not
    # create misleading failed systemd units. The status CLI still signals them.
    return 1 if args.action == 'status' and result['health'] != 'OK' else 0


if __name__ == '__main__':
    raise SystemExit(main())
