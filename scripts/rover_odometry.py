#!/usr/bin/python3
"""Offline differential-drive encoder analysis; never opens devices or actuates."""
import argparse
import csv
from datetime import datetime,timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import uuid

BASE=Path('/var/lib/jupi-agent/rover')
FIELDS=('time_s','left_m','right_m')


def sha(raw):return hashlib.sha256(raw).hexdigest()


def parse(raw):
    if len(raw)>8*1024**2:raise ValueError('Input exceeds 8 MiB')
    reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    if reader.fieldnames!=list(FIELDS):raise ValueError('Required header: time_s,left_m,right_m (cumulative wheel distances in metres)')
    rows=[]
    for row in reader:
        if set(row)!=set(FIELDS):raise ValueError('Extra CSV fields')
        values=tuple(float(row[k]) for k in FIELDS)
        if any(not math.isfinite(x) or abs(x)>1e9 for x in values):raise ValueError('Nonfinite or out-of-range input')
        if values[0]<0 or (rows and values[0]<=rows[-1][0]):raise ValueError('Times must be nonnegative and strictly increasing')
        rows.append(values)
        if len(rows)>100000:raise ValueError('At most 100000 encoder frames')
    if len(rows)<2:raise ValueError('At least two encoder frames')
    return rows


def integrate(rows,wheelbase):
    if not math.isfinite(wheelbase) or not .01<=wheelbase<=10:raise ValueError('Wheel separation must be 0.01..10 metres')
    x=y=theta=distance=0.;poses=[(rows[0][0],x,y,theta,0.,0.)]
    for previous,current in zip(rows,rows[1:]):
        dt=current[0]-previous[0]
        if dt<=0:raise ValueError('Nonpositive sample interval')
        left=current[1]-previous[1];right=current[2]-previous[2]
        travel=(left+right)/2;angle=(right-left)/wheelbase;half=angle/2
        sinc=math.sin(half)/half if abs(half)>1e-8 else 1-half*half/6
        x+=travel*sinc*math.cos(theta+half);y+=travel*sinc*math.sin(theta+half)
        theta+=angle;distance+=abs(travel)
        poses.append((current[0],x,y,math.atan2(math.sin(theta),math.cos(theta)),travel/dt,angle/dt))
    return poses,distance


def trajectory(poses):
    xs=[p[1] for p in poses];ys=[p[2] for p in poses];lo_x,hi_x=min(xs),max(xs);lo_y,hi_y=min(ys),max(ys)
    scale=650/max(hi_x-lo_x,hi_y-lo_y,.1)
    points=' '.join(f'{75+(x-lo_x)*scale:.3f},{725-(y-lo_y)*scale:.3f}' for x,y in zip(xs,ys))
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="800" viewBox="0 0 800 800"><rect width="800" height="800" fill="black"/><text x="40" y="35" fill="white" font-family="monospace">JUPI: encoder-only odometry, relative metres</text><polyline points="{points}" fill="none" stroke="white" stroke-width="2"/><text x="40" y="780" fill="white" font-family="monospace">No absolute localization or actuator control</text></svg>\n'


def verify(directory):
    directory=Path(directory);receipt=json.loads((directory/'receipt.json').read_text())
    for name,expected in receipt['artifacts'].items():
        if Path(name).name!=name or sha((directory/name).read_bytes())!=expected:raise ValueError('Artifact differs: '+name)
    return {'directory':str(directory),'artifacts_verified':len(receipt['artifacts']),'receipt_sha256':sha((directory/'receipt.json').read_bytes()),'classification':receipt['data_origin']}


def execute(raw,wheelbase,synthetic=False,output=None):
    rows=parse(raw);poses,distance=integrate(rows,wheelbase)
    os.umask(0o077);directory=Path(output) if output else BASE/str(uuid.uuid4())
    directory.mkdir(mode=0o700,parents=True,exist_ok=False)
    (directory/'encoders.csv').write_bytes(raw)
    with (directory/'poses.csv').open('x',newline='') as f:
        writer=csv.writer(f,lineterminator='\n');writer.writerow(['time_s','x_m','y_m','yaw_rad','forward_m_s','yaw_rad_s']);writer.writerows(poses)
    (directory/'trajectory.svg').write_text(trajectory(poses))
    (directory/'analyzer.py').write_bytes(Path(__file__).read_bytes())
    receipt={'schema':'jupi.rover.odometry.v1','utc':datetime.now(timezone.utc).isoformat(),'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip() if Path('/proc/sys/kernel/random/boot_id').exists() else None,'data_origin':'synthetic_demo' if synthetic else 'operator_supplied_encoder_data_unverified','input_units':{'time':'seconds','wheel_distance':'cumulative metres'},'frame':'Initial pose (0,0,0), x forward and positive yaw counterclockwise; relative planar frame','wheel_separation_m':wheelbase,'samples':len(rows),'duration_s':rows[-1][0]-rows[0][0],'distance_m':distance,'final_pose':dict(zip(('time_s','x_m','y_m','yaw_rad','forward_m_s','yaw_rad_s'),poses[-1])),'assumptions':['Differential drive with fixed known wheel separation','Wheel distances already calibrated in metres','No wheel slip; encoders alone cannot establish absolute position','No gyro fusion or uncertainty estimate'],'actuator_writes':0,'network_requests':0,'artifacts':{p.name:sha(p.read_bytes()) for p in directory.iterdir() if p.is_file()}}
    with (directory/'receipt.json').open('x') as f:json.dump(receipt,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    return {**verify(directory),'samples':len(rows),'distance_m':distance,'final_pose':receipt['final_pose']}


def demo():
    text=io.StringIO();writer=csv.writer(text,lineterminator='\n');writer.writerow(FIELDS)
    for i in range(501):
        t=i/10;writer.writerow([t,.08*t,.12*t])
    return text.getvalue().encode()


def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    d=s.add_parser('demo');d.add_argument('--output')
    a=s.add_parser('integrate');a.add_argument('csv');a.add_argument('--wheelbase-m',type=float,required=True);a.add_argument('--synthetic',action='store_true');a.add_argument('--output')
    v=s.add_parser('verify');v.add_argument('directory')
    s.add_parser('status');args=p.parse_args()
    if args.action=='demo':result=execute(demo(),.4,True,args.output)
    elif args.action=='integrate':
        path=Path(args.csv)
        if path.stat().st_size>8*1024**2:raise ValueError('Input exceeds 8 MiB')
        result=execute(path.read_bytes(),args.wheelbase_m,args.synthetic,args.output)
    elif args.action=='verify':result=verify(args.directory)
    else:result={'role':'offline encoder analysis','actuator_control':False,'physical_rover_configured':False,'camera_nodes':[str(p) for p in Path('/dev').glob('video*')],'serial_by_id':[str(p) for p in Path('/dev/serial/by-id').glob('*')],'data_root':str(BASE),'example':'jupi-rover integrate encoders.csv --wheelbase-m 0.4','schema':'time_s,left_m,right_m'}
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
