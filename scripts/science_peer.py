#!/usr/bin/python3
"""Bounded stdlib reference worker, executed on the enrolled Ubuntu SSH peer."""
import base64
import hashlib
import json
import math
from pathlib import Path
import platform
import resource
import struct
import sys

MAX_SAMPLES = 65536
MAX_REQUEST = 12 * 1024 * 1024


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def pairs_unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON field')
        result[key] = value
    return result


def dataset(value):
    if not isinstance(value, dict) or value.get('schema') != 'jupi.science.input.v1':
        raise ValueError('Dataset schema differs')
    operation = value.get('operation')
    if operation not in ('calibrate', 'apply'):
        raise ValueError('Unknown science operation')
    points = value.get('samples')
    minimum, columns = (3, 2) if operation == 'calibrate' else (1, 1)
    if not isinstance(points, list) or not minimum <= len(points) <= MAX_SAMPLES:
        raise ValueError('Sample count outside supported bound')
    for point in points:
        if not isinstance(point, list) or len(point) != columns:
            raise ValueError('Sample columns differ')
        if any(type(x) not in (float, int) or not math.isfinite(x) or abs(x) > 1e12 for x in point):
            raise ValueError('Samples must be finite numbers with magnitude at most 1e12')
    return points


def fit(value):
    points = dataset(value)
    n = len(points)
    if value['operation'] == 'apply':
        model = value.get('calibration')
        required = ('x_mean','x_scale','y_mean','y_scale','gain','slope','intercept','x_min','x_max')
        if not isinstance(model, dict) or any(type(model.get(k)) not in (float,int) or not math.isfinite(model[k]) for k in required):
            raise ValueError('Invalid parent calibration')
        if model['x_scale'] <= 0 or model['y_scale'] <= 0 or model['x_min'] >= model['x_max']:
            raise ValueError('Invalid parent calibration scales')
        outside = sum(not model['x_min'] <= p[0] <= model['x_max'] for p in points)
        if outside and value.get('allow_extrapolation') is not True:
            raise ValueError('Application outside the calibration range requires explicit extrapolation')
        return {'model': model, 'samples': n, 'extrapolated_samples': outside, 'fit_metrics': None}
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    xm, ym = math.fsum(xs)/n, math.fsum(ys)/n
    xscale = max(abs(x-xm) for x in xs)
    yscale = max(abs(y-ym) for y in ys) or 1.0
    if xscale == 0:
        raise ValueError('Calibration needs variation in x')
    us, vs = [(x-xm)/xscale for x in xs], [(y-ym)/yscale for y in ys]
    suu = math.fsum(u*u for u in us)
    gain = math.fsum(u*v for u,v in zip(us,vs))/suu
    slope = gain * yscale / xscale
    intercept = ym - slope*xm
    if not all(math.isfinite(x) for x in (gain, slope, intercept)):
        raise ValueError('Calibration coefficients are not representable in float64')
    residuals = [(v-gain*u)*yscale for u,v in zip(us,vs)]
    sse = math.fsum(r*r for r in residuals)
    syy = math.fsum((y-ym)**2 for y in ys)
    sigma_normalized = math.sqrt(math.fsum((v-gain*u)**2 for u,v in zip(us,vs))/(n-2))
    stderr = sigma_normalized/math.sqrt(suu)*yscale/xscale
    return {'model': {'x_mean':xm,'x_scale':xscale,'y_mean':ym,'y_scale':yscale,'gain':gain,
                       'slope':slope,'intercept':intercept,'x_min':min(xs),'x_max':max(xs)},
            'samples':n,'extrapolated_samples':0,
            'fit_metrics': {'rmse':math.sqrt(sse/n),'sse':sse,'r_squared':1-sse/syy if syy else None,
                            'slope_standard_error':stderr if math.isfinite(stderr) else None,
                            'uncertainty_scope':'OLS residual-based standard error; not sensor accuracy or traceable calibration'}}


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def normalized(value, model):
    result = []
    for point in dataset(value):
        u = (point[0]-model['x_mean'])/model['x_scale']
        v = (point[1]-model['y_mean'])/model['y_scale'] if value['operation']=='calibrate' else 0.0
        if not all(math.isfinite(z) and abs(z) <= 1e6 for z in (u,v)):
            raise ValueError('Normalized input outside supported range')
        result.append((f32(u),f32(v)))
    return result


def verify_gpu(value, model, raw):
    inputs = normalized(value, model)
    if len(raw) != len(inputs)*8:
        raise ValueError('GPU result size differs')
    gain = f32(model['gain'])
    failures, maximum, maximum_physical = 0, 0.0, 0.0
    for point, (u,v), (pred,residual) in zip(value['samples'],inputs,struct.iter_unpack('<ff',raw)):
        expected = gain*u
        tolerance = 8*(2**-23)*(abs(expected)+abs(v)+1)
        errors = [abs(pred-expected)]
        if value['operation']=='calibrate':
            errors.append(abs(residual-(v-expected)))
        if not all(math.isfinite(z) for z in (pred,residual)) or any(e>tolerance for e in errors):
            failures += 1
        maximum = max(maximum, *errors)
        original = model['gain']*(point[0]-model['x_mean'])/model['x_scale']
        maximum_physical = max(maximum_physical,abs(pred-original)*model['y_scale'])
    return {'verified':failures==0,'mismatches':failures,'samples':len(inputs),
            'maximum_normalized_error':maximum,'maximum_prediction_error_vs_float64_in_y_units':maximum_physical,
            'tolerance_policy':'8*float32_epsilon*(abs(gain32*u32)+abs(v32)+1), centered/scaled data',
            'scope':'Arithmetic agreement with the supplied model; not physical sensor validation'}


def source_hash():
    if '__file__' in globals():
        return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    args = Path('/proc/self/cmdline').read_bytes().split(b'\0')
    return hashlib.sha256(args[args.index(b'-c')+1]).hexdigest()


def main():
    resource.setrlimit(resource.RLIMIT_AS,(256*1024**2,256*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU,(15,16))
    raw = sys.stdin.buffer.read(MAX_REQUEST+1)
    if len(raw)>MAX_REQUEST:
        raise ValueError('Peer request too large')
    request = json.loads(raw,object_pairs_hook=pairs_unique,parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite JSON')))
    actual_source = source_hash()
    if request.get('worker_sha256') != actual_source:
        raise ValueError('Peer worker source differs')
    value = request['dataset']
    digest = hashlib.sha256(canonical(value)).hexdigest()
    if request.get('dataset_sha256') != digest:
        raise ValueError('Input hash differs')
    fitted = fit(value)
    if request['operation']=='fit':
        result = fitted
    elif request['operation']=='verify':
        if request.get('model') != fitted['model']:
            raise ValueError('Reference model differs from deterministic peer fit')
        gpu = base64.b64decode(request['gpu_output_b64'],validate=True)
        if hashlib.sha256(gpu).hexdigest()!=request.get('gpu_output_sha256'):
            raise ValueError('GPU output hash differs')
        result = verify_gpu(value,fitted['model'],gpu)
    else:
        raise ValueError('Unknown peer operation')
    result.update({'worker_sha256':actual_source,'dataset_sha256':digest,
                   'execution_host':{'hostname':platform.node(),'kernel':platform.release(),
                                     'python':platform.python_version(),'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()},
                   'resource_bounds':{'address_space_bytes':256*1024**2,'cpu_seconds':15},
                   'scope_note':'Computation on the pinned SSH peer; not an independent model acknowledgment'})
    sys.stdout.buffer.write(canonical(result)+b'\n')


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'error_class':type(error).__name__,'error':str(error)[:240]}),file=sys.stderr)
        raise SystemExit(1)
