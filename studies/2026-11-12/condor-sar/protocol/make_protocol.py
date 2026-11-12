#!/usr/bin/env python3
"""CONDOR-LINEAGE SAR v0: build the frozen protocol (theory values computed BEFORE any node run)."""
import json, math, random, hashlib, sys
import numpy as np
C=299792458.0; FC=9.6e9; B=150e6; LAM=C/FC; K4=4*math.pi/LAM
R0=1000.0; N=256; D=0.0625; L=N*D; V=100.0; PRF=V/D
RHO_R=C/(2*B); RHO_A=LAM*R0/(2*L)
SEED=20261112
T=[]
def add(name,x,y,a=1.0,ph=0.0,role=''):
    T.append(dict(name=name,x=float(x),y=float(y),amp=float(a),phase=float(ph),role=role))
add('T0',0,R0,role='isolated IRF, scene center')
add('T1',-20,R0-15,role='isolated IRF')
add('T2',20,R0+15,role='isolated IRF')
FAC=[0.7,0.8,0.9,1.0,1.1,1.25,1.5]; XC=[-27,-18,-9,0,9,18,27]
pairs=[]
for i,(f,xc) in enumerate(zip(FAC,XC)):
    s=f*RHO_A; add(f'PA{i}a',xc-s/2,R0-25,role='dense-cluster azimuth pair'); add(f'PA{i}b',xc+s/2,R0-25,role='dense-cluster azimuth pair')
    pairs.append(dict(name=f'PA{i}',axis='az',factor=f,sep_m=s,xc=xc,yc=R0-25,a=f'PA{i}a',b=f'PA{i}b'))
    s=f*RHO_R; add(f'PR{i}a',xc,R0+25-s/2,role='dense-cluster range pair'); add(f'PR{i}b',xc,R0+25+s/2,role='dense-cluster range pair')
    pairs.append(dict(name=f'PR{i}',axis='rg',factor=f,sep_m=s,xc=xc,yc=R0+25,a=f'PR{i}a',b=f'PR{i}b'))
rng=random.Random(SEED); nrand=0
while nrand<6:
    x=rng.uniform(-30,30); y=R0+rng.uniform(-10,10)
    if math.hypot(x-0,y-R0)<6: continue
    if any(math.hypot(x-t['x'],y-t['y'])<6 for t in T if t['name'].startswith('S')): continue
    add(f'S{nrand}',x,y,rng.uniform(0.3,1.0),rng.uniform(-math.pi,math.pi),role='seeded random scatterer'); nrand+=1
WIN=(R0-40.0,R0+40.0); DR=1/16.0; NB=int(round((WIN[1]-WIN[0])/DR))+1
add('E',10,WIN[1],role='swath edge: min range exactly = last recorded range bin (partially supported)')
add('O1',-10,WIN[1]+6,role='outside range window (no support) but inside image grid; must not appear')
add('O2',60,R0+5,role='outside image grid in azimuth, inside range window; alias source under PRF decimation')
tgt={t['name']:t for t in T}
# theory: pair resolution with relative phase
def dip(s,rho,phi,step=1/64):
    u=np.arange(-1.5*rho,s+1.5*rho,step*rho/1.0)
    f=np.abs(np.sinc(u/rho)+np.exp(-1j*phi)*np.sinc((u-s)/rho))**2
    return dip_from_cut(u,f,0.0,s)
def dip_from_cut(u,p,ua,ub):
    m=(ua+ub)/2; L1=(u>=ua-0.5*(ub-ua)-0.3)&(u<=m); L2=(u>=m)&(u<=ub+0.5*(ub-ua)+0.3)
    if L1.sum()<2 or L2.sum()<2: return dict(resolved=False,dip_db=0.0)
    i1=np.where(L1)[0][np.argmax(p[L1])]; i2=np.where(L2)[0][np.argmax(p[L2])]
    if i2<=i1+1: return dict(resolved=False,dip_db=0.0)
    mn=p[i1:i2+1].min(); pk=min(p[i1],p[i2])
    # two distinct local maxima required: minimum strictly interior
    j=i1+int(np.argmin(p[i1:i2+1])); interior=(i1<j<i2)
    d=10*math.log10(max(mn,1e-300)/pk)
    return dict(resolved=bool(interior and d<=-3.0),dip_db=float(d))
ac=(0.0,0.0)
for p in pairs:
    ta,tb=tgt[p['a']],tgt[p['b']]
    phi=K4*(math.hypot(tb['x'],tb['y'])-math.hypot(ta['x'],ta['y']))
    rho=RHO_A if p['axis']=='az' else RHO_R
    p['phi_rel_rad_mod2pi']=float(phi%(2*math.pi))
    th=dip(p['sep_m'],rho,phi); p['theory']=th
    p['theory_inphase']=dip(p['sep_m'],rho,0.0)
# generic in-phase threshold
fs=np.arange(0.5,2.0,0.001); thr=None
for f in fs:
    if dip(f,1.0,0.0,1/256)['resolved']: thr=float(f); break
# decimation ghost predictions
def ghosts(t,M):
    out=[]
    R=math.hypot(t['x'],t['y']); st=t['x']/R
    for m in (-2,-1,1,2):
        sp=st+m*LAM/(2*D*M)
        if abs(sp)>=1: continue
        xp=R*sp; yp=math.sqrt(R*R-xp*xp)
        if -32<=xp<32 and 952<=yp<1048: out.append(dict(order=m,x=xp,y=yp))
    return out
DEC=[1,2,4,8]
gp={str(M):{t['name']:ghosts(t,M) for t in T if ghosts(t,M)} for M in DEC}
onset=None
for M in DEC:
    if gp[str(M)]: onset=M; break
# precision cliff prediction
SWEEP=[1e3,4e3,16e3,64e3,256e3]
def ulp32(x): x=np.float32(x); return float(np.spacing(x))
pred=[]
for R in SWEEP:
    sig=math.sqrt((K4*ulp32(R))**2+ulp32(K4*R)**2)/math.sqrt(12)
    pred.append(dict(R0_m=R,N_pulses=int(256*R/1e3),aperture_m=256*R/1e3*D,pred_phase_rms_rad=sig,pred_gain_loss_db=float(20*math.log10(math.exp(-sig*sig/2))) if sig<3 else -99.0))
P=dict(
 study='CONDOR-LINEAGE SAR v0',created_local='2026-11-12 America/Los_Angeles',
 lineage_note='AFRL Condor (2010, PS3+GPU COTS cluster; SAR image formation among its workloads) is architectural inspiration only. No AFRL code, data or benchmark numbers are used or compared.',
 seed=SEED,
 radar=dict(c=C,fc_hz=FC,lambda_m=LAM,bandwidth_hz=B,R0_m=R0,n_pulses=N,pulse_spacing_m=D,aperture_m=L,platform_speed_mps=V,prf_hz=PRF,
  geometry='2-D slant plane; platform on y=0 at x_n=-L/2+(n+0.5)d; broadside to scene center (0,R0)',
  range_window_m=list(WIN),range_bin_m=DR,n_range_bins=NB,
  signal='range-compressed, unweighted: s_n(r)=sum_k a_k exp(j phi_k) sinc(2B(r-R_kn)/c) exp(-j 4pi R_kn/lambda) (np.sinc convention)',
  backprojection='I(p)=sum_n lerp(s_n, R_pn) exp(+j 4pi R_pn/lambda); lerp valid iff 0<=floor((R-r0)/dr)<=NB-2 else 0'),
 theory=dict(rho_range_nominal_m=RHO_R,rho_az_nominal_m=RHO_A,irw3db_range_m=0.8859*RHO_R,irw3db_az_m=0.8859*RHO_A,pslr_db=-13.26,
  inphase_pair_resolve_threshold_x_rho=thr,decimation_ghosts=gp,predicted_alias_onset_M=onset,precision_prediction=pred),
 targets=T,pairs=pairs,
 image_grid=dict(x0=-32.0,nx=256,y0=952.0,ny=384,dx=0.25,order='row-major [iy][ix], y outer'),
 fine_cuts=dict(step_m=1/16.0,irf_halfspan_m=8.0,irf_targets=['T0','T1','T2','E'],pairs='cut along pair axis from a-3m to b+3m',
  O1='range cut through O1 from y=1036 to 1048'),
 split=dict(JUPI='pulses [0,128)',JUPI2='pulses [128,256)',gather='coherent complex sum on box'),
 cross_witness=dict(K=512,seed_rule='int(sha256(peer partial_grid.c128 bytes)[:16],16) -> random.Random(seed).sample(range(98304),512)',
  method='stdlib-only (system python3, no numpy) re-generation of the needed range bins from the protocol targets + re-backprojection of the peer pulse half',abs_tol=1e-7),
 decimation=dict(M=DEC,rule='keep pulses n%M==0, normalize by M',alias_metric='max |I| outside 3 m of in-image targets and outside y>1034 (edge zone), dB rel T0 peak',alias_threshold_db=-20.0),
 precision=dict(R0_sweep_m=SWEEP,pulse_spacing_m=D,N='256*R0/1km (az resolution held constant)',target='single point at (0,R0)',cut='azimuth cut 129 px at 1/16 m about target',
  modes={'f64':'all float64, np.sum','f32_naive':'float32 coordinates, R=sqrt in f32, phase=k32*R32 in f32, complex64, sequential cumsum accumulation (SPU-like)',
         'f32_refdiff':'reference range Rref_n per pulse in float64 (PPE-side) reduced mod 2pi and stored as complex64 rotation; per-pixel dR via (2(c-a_n).d+|d|^2)/(R+Rref) in f32; complex64 sequential accumulation'},
  cliff_definition='gain loss worse than -1.0 dB vs f64 at the target pixel'),
 pass_criteria=dict(
  irw='measured -3 dB IRW of T0,T1,T2 within +/-10% of 0.8859*rho (both axes, full summed image fine cuts)',
  pslr='measured PSLR of T0,T1,T2 in [-14.0,-12.5] dB (both axes)',
  position='|position error| < 0.5 image pixel (0.125 m) for T0,T1,T2, parabolic peak on main image grid',
  cross_node_int='exact sha256 match of integer detection table (argmax pixel per in-image target window) between JUPI-full, JUPI2-full and summed partials',
  cross_node_float='max|A-B| <= 1e-9 * peak|T0| for float64 images (summed partials vs single-node full; JUPI vs JUPI2 full); f32 sweep outputs rel 1e-4',
  witness='all K=512 witnessed pixels within abs 1e-7 on both nodes',
  outside_target='O1 level at its true pixel < -40 dB rel T0',
  report_only=['pair resolution vs theory','swath-edge target E loss/bias','alias onset vs predicted M','precision cliff vs prediction','throughput']),
 budgets=dict(gate='MemAvailable > 800 MB and swap < 25% before each job',rlimit_as_bytes=512*1024*1024,wall_s_per_node=600,gpu=False,installs=False),
)
json.dump(P,open(sys.argv[1],'w'),indent=1,sort_keys=True)
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
print('inphase thr',thr,'onset',onset); print(json.dumps(gp)[:600]); print(pred)
for p in pairs: print(p['name'],p['factor'],round(p['phi_rel_rad_mod2pi'],2),p['theory'],p['theory_inphase']['resolved'])
