#!/usr/bin/python3
"""Summarize retained JUPI benchmark observations without rerunning workloads."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import statistics


def stats(values):
    if not values:raise ValueError('Missing observations')
    return {'samples':len(values),'median':statistics.median(values),'minimum':min(values),'maximum':max(values),'coefficient_of_variation':statistics.pstdev(values)/statistics.mean(values) if statistics.mean(values) else None}


def percentile(values,q):
    values=sorted(values);i=(len(values)-1)*q;lo=int(i);hi=min(lo+1,len(values)-1)
    return values[lo]+(values[hi]-values[lo])*(i-lo)


def summarize(directory,offline=None,native_math=None):
    directory=Path(directory);raw=json.loads((directory/'raw.json').read_text());data={r['name']:r for r in raw}
    cpu={str(t):stats([float(re.search(r'events per second:\s*([\d.]+)',r['stdout']).group(1)) for name,r in data.items() if name.startswith(f'cpu-t{t}-')]) for t in (1,2,4,8)}
    matrix={name.removeprefix('matrix-'):json.loads(r['stdout']) for name,r in data.items() if name.startswith('matrix-')}
    memory=json.loads(data['memory']['stdout'])
    cl=[json.loads(r['stdout']) for name,r in data.items() if name.startswith('gpu-opencl-')]
    assert all(x['mismatches']==0 for x in cl)
    gles={}
    for resolution in ('1280x720','1920x1080'):
        tests=[]
        for name,r in data.items():
            if not name.startswith('gpu-gles-'+resolution+'-'):continue
            assert int(re.search(r'mismatched_channels=(\d+)',r['stdout']).group(1))==0
            frames=[float(x) for x in re.findall(r'^frame_ms_\d+=([\d.]+)',r['stdout'],re.M)]
            assert len(frames)==180
            tests.append({'median_frame_ms':statistics.median(frames),'p95_frame_ms':percentile(frames,.95),'p99_frame_ms':percentile(frames,.99),'frames':len(frames)})
        gles[resolution]={'trials':tests,'median_frame_ms':statistics.median(x['median_frame_ms'] for x in tests),'scope':'Offscreen full-target checkerboard, glFinish after every draw; microbenchmark wall times, not game FPS or desktop presentation'}
    io={}
    for name,r in data.items():
        if not name.startswith('io-'):continue
        mode=name.rsplit('-r',1)[0].removeprefix('io-');j=json.loads(r['stdout'])['jobs'][0];assert j['error']==0
        x=j['read' if 'read' in mode else 'write']
        io.setdefault(mode,[]).append({'MiB_s':x['bw_bytes']/2**20,'IOPS':x['iops'],'mean_completion_ms':x['clat_ns']['mean']/1e6,'fsync_mean_ms':j.get('sync',{}).get('lat_ns',{}).get('mean',0)/1e6,'bytes':x['io_bytes']})
    network=json.loads(data['network']['stdout'])
    encode={str(t):stats([90/float(re.search(r'rtime=([\d.]+)',r['stderr']).group(1)) for name,r in data.items() if name.startswith(f'encode-t{t}-')]) for t in (1,2,4)}
    model=json.loads(data['model']['stdout']);model_stats={str(t):stats([x['tokens_per_second'] for x in model['results'] if x['threads']==t]) for t in (1,2,3,4)}
    telemetry=[json.loads(x) for x in (directory/'telemetry.jsonl').read_text().splitlines()]
    result={'schema':'jupi.benchmark.report.v1','utc':datetime.now(timezone.utc).isoformat(),'directory':str(directory),'raw_sha256':hashlib.sha256((directory/'raw.json').read_bytes()).hexdigest(),'telemetry_sha256':hashlib.sha256((directory/'telemetry.jsonl').read_bytes()).hexdigest(),'run_manifest':json.loads((directory/'manifest.json').read_text()),'cpu_sysbench_prime_events_s':cpu,'cpu_eight_to_one_speedup':cpu['8']['median']/cpu['1']['median'],'matrix':matrix,'memory_nominal_GB_s':stats(memory['nominal_GB_s']),'memory_working_set_bytes':memory['working_set_bytes'],'gpu_vector_nominal_GB_s':stats([x['nominal_GB_s'] for x in cl]),'gpu_vector_mismatches':0,'gpu_gles':gles,'storage_trials':io,'storage_scope':'Live ext4 on loop0, DIO=0 backing image on crypt/UFS. Guest direct=1 does not bypass backing cache; reads are cache-influenced. First write includes fresh extent allocation. No raw-HDD read speed claim.','network_ssh_Mbit_s':{direction:stats([x['Mbit_s'] for x in network['results'] if x['direction']==direction]) for direction in ('upload','download')},'network_scope':network['scope'],'encode_720p_x264_veryfast_fps':encode,'model_qwen3_06b_tokens_s':model_stats,'model_scope':'CPU generation timing for the installed small model; not reasoning quality. CPUQuota configured but unsupported by this kernel; thread count is explicit.','thermal':{'sensor':'relative k10temp Tctl, not calibrated die temperature','minimum':min(x['relative_Tctl'] for s in telemetry for x in s['sensors']),'maximum':max(x['relative_Tctl'] for s in telemetry for x in s['sensors']),'available_memory_minimum_bytes':min(s['memory']['MemAvailable'] for s in telemetry),'samples':len(telemetry)},'scope_limits':['Live instrument and desktop services retained; no isolated laboratory ambient/power/acoustic measurements','No CPU frequency controls exposed; no overclock, voltage or fan changes','No gaming, desktop GLX, hardware video encoder or Vulkan presentation validation','Short bounded repeated workloads; not prolonged thermal or memory burn-in','No physical rover, encoder, IMU, GPS or camera attached during qualification']}
    if offline:
        path=Path(offline)/'offline.json';v=json.loads(path.read_text());result['offline_qualification']={'directory':str(path.parent),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'passed':True,'peer_connect_errno':v['peer_connect_errno'],'interfaces':v['interfaces'],'memory_after_restart':v['memory_after_agent_restart']['value'],'job_record_after_restart':v['job_record_after_restart'],'rover_included':'rover_job' in v}
    if native_math:result['native_math_comparison']=json.loads(Path(native_math).read_text())
    return result,telemetry


def plot(result,telemetry,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.style.use('dark_background');fig,axes=plt.subplots(2,3,figsize=(15,9),constrained_layout=True)
    def bars(ax,rows,title,unit):
        labels=list(rows);values=[rows[k]['median'] for k in labels]
        ax.bar(labels,values,color='#dddddd',edgecolor='white',yerr=[[v-rows[k]['minimum'] for k,v in zip(labels,values)],[rows[k]['maximum']-v for k,v in zip(labels,values)]],capsize=4,error_kw={'ecolor':'#999999'})
        ax.set_title(title);ax.set_ylabel(unit);ax.set_xlabel('CPU threads');ax.grid(axis='y',alpha=.2)
    bars(axes[0,0],result['cpu_sysbench_prime_events_s'],'CPU: prime-number workload','sysbench events/s')
    rows={k:stats([2*v['n']**3/t/1e9 for t in v['seconds']]) for k,v in result['matrix'].items()}
    bars(axes[0,1],rows,'Float64 matrix multiply (384 × 384)','nominal GFLOP/s');axes[0,1].set_xlabel('library and threads');axes[0,1].tick_params(axis='x',rotation=18)
    bars(axes[0,2],result['encode_720p_x264_veryfast_fps'],'720p x264 CPU encoding','frames/s')
    bars(axes[1,0],result['model_qwen3_06b_tokens_s'],'Local qwen3:0.6b generation','output tokens/s')
    bars(axes[1,1],result['network_ssh_Mbit_s'],'Verified 32 MiB SSH transfers','Mbit/s');axes[1,1].set_xlabel('JUPI direction; includes copying and hashing')
    ax=axes[1,2];values=[(datetime.fromisoformat(s['utc']),x['relative_Tctl']) for s in telemetry for x in s['sensors']];begin=values[0][0];ax.plot([(t-begin).total_seconds() for t,v in values],[v for t,v in values],color='white');ax.set_xlabel('elapsed seconds');ax.set_ylabel('relative Tctl control degrees');ax.set_title('Kernel thermal telemetry (not die °C)');ax.grid(alpha=.2)
    fig.suptitle('JUPI · hardware and workflow measurements · 7 November 2026\nThree repeats; bars show min–max. Final service affinity qualification is recorded separately.',fontsize=16)
    fig.savefig(path,dpi=140);plt.close(fig)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory');p.add_argument('--offline');p.add_argument('--native-math');p.add_argument('--plot',action='store_true');args=p.parse_args()
    r,t=summarize(args.directory,args.offline,args.native_math);directory=Path(args.directory);(directory/'summary.json').write_text(json.dumps(r,indent=2)+'\n')
    if args.plot:plot(r,t,directory/'benchmark-chart.png')
    print(json.dumps({'summary':str(directory/'summary.json'),'chart':str(directory/'benchmark-chart.png') if args.plot else None,'cpu_8_to_1':r['cpu_eight_to_one_speedup'],'offline':r.get('offline_qualification')},indent=2))


if __name__=='__main__':main()
