#!/usr/bin/env python3
"""CONDOR-LINEAGE SAR v0 node/box program. Our own code (no AFRL code).
modes:
  produce <protocol> <sha> <seat> <half> <outdir>     numpy: phase history, partial BP, decimation, precision sweep
  witness <protocol> <sha> <seat> <own_partial> <own_half> <peer_partial> <peer_half> <outdir>   stdlib only
"""
import sys, os, json, hashlib, math, time, resource, platform
def gate():
    m={}
    for l in open('/proc/meminfo'):
        k,v=l.split(':'); m[k]=int(v.split()[0])*1024
    sw=(m['SwapTotal']-m['SwapFree'])/m['SwapTotal']*100 if m['SwapTotal'] else 0.0
    return dict(mem_available_bytes=m['MemAvailable'],swap_used_pct=round(sw,3),ok=bool(m['MemAvailable']>800e6 and sw<25.0),loadavg=open('/proc/loadavg').read().split()[:3])
def sha_file(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()
def load_protocol(p,sha):
    got=sha_file(p)
    if got!=sha: print('PROTOCOL_SHA_MISMATCH',got); sys.exit(4)
    return json.load(open(p))
def pulse_x(P,n):
    r=P['radar']; return -r['aperture_m']/2+(n+0.5)*r['pulse_spacing_m']
def grid_xy(P,i):
    g=P['image_grid']; iy,ix=divmod(i,g['nx']); return g['x0']+ix*g['dx'], g['y0']+iy*g['dx']
def cut_points(P):
    """Deterministic list of (cut_name, axis, [(x,y),...])"""
    T={t['name']:t for t in P['targets']}; st=P['fine_cuts']['step_m']; hs=P['fine_cuts']['irf_halfspan_m']
    n=int(round(2*hs/st))+1; cuts=[]
    for nm in P['fine_cuts']['irf_targets']:
        t=T[nm]
        cuts.append((nm+'_az','az',[(t['x']-hs+i*st,t['y']) for i in range(n)]))
        cuts.append((nm+'_rg','rg',[(t['x'],t['y']-hs+i*st) for i in range(n)]))
    for p in P['pairs']:
        a,b=T[p['a']],T[p['b']]
        if p['axis']=='az':
            x0=a['x']-3.0; m=int(round((b['x']+3.0-x0)/st))+1; cuts.append((p['name'],'az',[(x0+i*st,a['y']) for i in range(m)]))
        else:
            y0=a['y']-3.0; m=int(round((b['y']+3.0-y0)/st))+1; cuts.append((p['name'],'rg',[(a['x'],y0+i*st) for i in range(m)]))
    o=T['O1']; m=int(round(12/st))+1; cuts.append(('O1_rg','rg',[(o['x'],1036.0+i*st) for i in range(m)]))
    return cuts
def rus():
    r=resource.getrusage(resource.RUSAGE_SELF); return dict(utime_s=r.ru_utime,stime_s=r.ru_stime,maxrss_bytes=r.ru_maxrss*1024)

def produce(P,psha,seat,half,out):
    import numpy as np
    t_all=time.monotonic(); R=P['radar']; c=R['c']; K4=4*math.pi/R['lambda_m']; B=R['bandwidth_hz']; N=R['n_pulses']
    r0=R['range_window_m'][0]; dr=R['range_bin_m']; NB=R['n_range_bins']
    rec=dict(seat=seat,half=half,python=sys.version,numpy=np.__version__,machine=platform.machine(),executable=sys.executable,protocol_sha256=psha,timings={})
    T=P['targets']; tx=np.array([t['x'] for t in T]); ty=np.array([t['y'] for t in T]); ta=np.array([t['amp']*complex(math.cos(t['phase']),math.sin(t['phase'])) for t in T])
    xn=np.array([pulse_x(P,n) for n in range(N)])
    # 1 phase history
    t0=time.monotonic(); r=r0+np.arange(NB)*dr; ph=np.empty((N,NB),complex)
    for n in range(N):
        Rk=np.sqrt((tx-xn[n])**2+ty**2)
        ph[n]=(np.sinc((2*B/c)*(r[:,None]-Rk[None,:]))*(ta*np.exp(-1j*K4*Rk))[None,:]).sum(1)
    ph.tofile(os.path.join(out,'phase_history.c128')); rec['timings']['phase_history_s']=time.monotonic()-t0
    # pixels: grid + cuts
    g=P['image_grid']; gx=g['x0']+np.arange(g['nx'])*g['dx']; gy=g['y0']+np.arange(g['ny'])*g['dx']
    GX,GY=np.meshgrid(gx,gy); X=GX.ravel(); Y=GY.ravel(); NG=X.size
    cuts=cut_points(P); cx=np.array([q[0] for cc in cuts for q in cc[2]]); cy=np.array([q[1] for cc in cuts for q in cc[2]])
    AX=np.concatenate([X,cx]); AY=np.concatenate([Y,cy])
    def bp(pulses,AX,AY,dt=complex):
        acc=np.zeros(AX.size,dt); Y2=AY*AY
        for n in pulses:
            Rp=np.sqrt((AX-xn[n])**2+Y2); f=(Rp-r0)/dr; i0=np.floor(f); fr=f-i0; i0=i0.astype(np.int64)
            v=(i0>=0)&(i0<=NB-2); i0c=np.where(v,i0,0); d=ph[n]
            acc+=np.where(v,d[i0c]*(1-fr)+d[i0c+1]*fr,0)*np.exp(1j*K4*Rp)
        return acc
    lo,hi=(0,N//2) if half==0 else (N//2,N)
    t0=time.monotonic(); part=bp(range(lo,hi),AX,AY); el=time.monotonic()-t0
    part[:NG].tofile(os.path.join(out,'partial_grid.c128')); part[NG:].tofile(os.path.join(out,'partial_cuts.c128'))
    rec['timings']['partial_bp_s']=el; rec['throughput_numpy_pixel_pulse_per_s']=AX.size*(hi-lo)/el; rec['partial']=dict(pulses=[lo,hi],n_pixels=int(AX.size))
    # decimation full images (M=1 is this node's full single-node image)
    rec['decimation']={}
    for M in P['decimation']['M']:
        t0=time.monotonic(); im=bp(range(0,N,M),AX if M==1 else X,AY if M==1 else Y)*M; e=time.monotonic()-t0
        fn=f'full_M{M}_grid.c128'; im[:NG].tofile(os.path.join(out,fn))
        if M==1: im[NG:].tofile(os.path.join(out,'full_M1_cuts.c128'))
        rec['decimation'][str(M)]=dict(file=fn,wall_s=e,pulses=len(range(0,N,M)))
    rec['timings']['decimation_s']=sum(v['wall_s'] for v in rec['decimation'].values())
    # detection table (integer outputs) from M=1 full grid
    full=np.fromfile(os.path.join(out,'full_M1_grid.c128'),complex).reshape(g['ny'],g['nx']); A=np.abs(full)
    det=[]
    for t in T:
        ix=int(round((t['x']-g['x0'])/g['dx'])); iy=int(round((t['y']-g['y0'])/g['dx']))
        if 0<=ix<g['nx'] and 0<=iy<g['ny']:
            a0,a1,b0,b1=max(iy-4,0),min(iy+5,g['ny']),max(ix-4,0),min(ix+5,g['nx']); w=A[a0:a1,b0:b1]; j=np.unravel_index(np.argmax(w),w.shape)
            det.append([t['name'],int(a0+j[0]),int(b0+j[1])])
    json.dump(det,open(os.path.join(out,'detections.json'),'w'),separators=(',',':'))
    # precision sweep
    t0=time.monotonic(); rec['precision']=precision(P,np); rec['timings']['precision_s']=time.monotonic()-t0
    rec['timings']['total_s']=time.monotonic()-t_all; rec['rusage']=rus(); rec['gate_post']=gate()
    rec['outputs']={f:sha_file(os.path.join(out,f)) for f in sorted(os.listdir(out)) if f.endswith(('.c128','.json')) and f!='RESULT.json'}
    json.dump(rec,open(os.path.join(out,'RESULT.json'),'w'),indent=1)
    print('PRODUCE_OK',seat,round(rec['timings']['total_s'],2),'s')

def cut_metrics(u,p):
    """u: positions (m); p: power. returns irw, pslr, peak pos (parabolic)."""
    import numpy as np
    i=int(np.argmax(p)); pk=p[i]
    if 0<i<len(p)-1:
        a,b,cc=np.log(p[i-1]),np.log(p[i]),np.log(p[i+1]); den=a-2*b+cc; off=0.5*(a-cc)/den if den!=0 else 0.0
    else: off=0.0
    st=u[1]-u[0]; upk=u[i]+off*st; h=pk/2
    def cross(direction):
        j=i
        while 0<j<len(p)-1 and p[j]>h: j+=direction
        if p[j]>h: return None
        j0=j-direction; f=(p[j0]-h)/(p[j0]-p[j]); return u[j0]+direction*f*st
    l,rr=cross(-1),cross(1); irw=(rr-l) if (l is not None and rr is not None) else None
    def null(direction):
        j=i
        while 0<j<len(p)-1 and p[j+direction]<p[j]: j+=direction
        return j
    jl,jr=null(-1),null(1); side=max(p[:jl+1].max() if jl>0 else 0,p[jr:].max() if jr<len(p)-1 else 0)
    pslr=10*math.log10(side/pk) if side>0 else None
    return dict(irw_m=irw,pslr_db=pslr,peak_m=float(upk),peak_power=float(pk))

def precision(P,np):
    R=P['radar']; c=R['c']; K4=4*math.pi/R['lambda_m']; B=R['bandwidth_hz']; d=P['precision']['pulse_spacing_m']; out=[]
    f32=np.float32; K432=f32(K4)
    for R0 in P['precision']['R0_sweep_m']:
        N=int(256*R0/1e3); L=N*d; xn=-L/2+(np.arange(N)+0.5)*d; xt,yt=0.0,R0
        Rt=np.sqrt((xt-xn)**2+yt**2); dat=np.exp(-1j*K4*Rt)  # physical data phase (f64 truth); envelope evaluated at pixel range
        st=1/16; px=np.arange(-64,65)*st; res={}; phs={}
        Rref=np.sqrt(xn**2+R0**2); rot=np.exp(1j*np.mod(K4*Rref,2*np.pi)).astype(np.complex64)
        for mode in ('f64','f32_naive','f32_refdiff'):
            t0=time.monotonic(); vals=np.empty(px.size,complex)
            for j,x in enumerate(px):
                if mode=='f64':
                    Rp=np.sqrt((x-xn)**2+R0**2); env=np.sinc((2*B/c)*(Rp-Rt)); vals[j]=np.sum(env*dat*np.exp(1j*K4*Rp))
                    if j==64: phs[mode]=K4*Rp
                elif mode=='f32_naive':
                    dx=f32(x)-xn.astype(f32); Rp=np.sqrt(dx*dx+f32(R0)*f32(R0)); env=np.sinc((2*B/c)*(Rp.astype(float)-Rt))
                    phi=K432*Rp; term=(env*dat).astype(np.complex64)*np.exp(1j*phi).astype(np.complex64)
                    vals[j]=complex(np.cumsum(term)[-1])
                    if j==64: phs[mode]=phi.astype(float)
                else:
                    dxp=f32(x); dyp=f32(0.0); ax=(-xn).astype(f32); ay=f32(R0); Rr=Rref.astype(f32)
                    num=f32(2)*(ax*dxp+ay*dyp)+dxp*dxp+dyp*dyp; den=f32(2)*Rr+num/(f32(2)*Rr); dR=num/den
                    env=np.sinc((2*B/c)*((Rref+dR.astype(float))-Rt)); phi=K432*dR
                    term=(env*dat).astype(np.complex64)*rot*np.exp(1j*phi).astype(np.complex64)
                    vals[j]=complex(np.cumsum(term)[-1])
                    if j==64: phs[mode]=np.mod(K4*Rref,2*np.pi).astype(np.float32).astype(float)+phi.astype(float)
            m=cut_metrics(px,np.abs(vals)**2); m['wall_s']=time.monotonic()-t0; m['peak_abs']=float(abs(vals[64])); res[mode]=m
            res[mode]['cut_sha256']=hashlib.sha256(vals.astype(np.complex128).tobytes()).hexdigest()
            res[mode]['cut']=[[float(v.real),float(v.imag)] for v in vals]
        for mode in ('f32_naive','f32_refdiff'):
            e=np.angle(np.exp(1j*(phs[mode]-phs['f64']))); res[mode]['phase_rms_rad']=float(np.sqrt(np.mean(e*e)))
            res[mode]['gain_loss_db']=float(20*math.log10(max(res[mode]['peak_abs'],1e-300)/res['f64']['peak_abs']))
        out.append(dict(R0_m=R0,N=N,aperture_m=L,modes=res))
    return out

def witness(P,psha,seat,own_p,own_h,peer_p,peer_h,out):
    """stdlib only: regenerate needed range bins from protocol targets; re-backproject."""
    import array, cmath, random
    t_all=time.monotonic(); R=P['radar']; c=R['c']; K4=4*math.pi/R['lambda_m']; B=R['bandwidth_hz']; N=R['n_pulses']
    r0=R['range_window_m'][0]; dr=R['range_bin_m']; NB=R['n_range_bins']; T=P['targets']
    ta=[t['amp']*complex(math.cos(t['phase']),math.sin(t['phase'])) for t in T]
    cache={}
    def tg(n):
        if n not in cache:
            xn=pulse_x(P,n); cache[n]=[(math.sqrt((t['x']-xn)**2+t['y']**2),a) for t,a in zip(T,ta)]
            cache[n]=[(Rk,a*cmath.exp(-1j*K4*Rk)) for Rk,a in cache[n]]
        return cache[n]
    def sinc(x):
        if x==0.0: return 1.0
        y=math.pi*x; return math.sin(y)/y
    k2=2*B/c
    def binv(n,i):
        ri=r0+i*dr; return sum(sinc(k2*(ri-Rk))*ph for Rk,ph in tg(n))
    def pix(x,y,pulses):
        acc=0j; y2=y*y
        for n in pulses:
            xn=pulse_x(P,n); Rp=math.sqrt((x-xn)**2+y2); f=(Rp-r0)/dr; i0=math.floor(f); fr=f-i0
            if 0<=i0<=NB-2: acc+=(binv(n,i0)*(1-fr)+binv(n,i0+1)*fr)*cmath.exp(1j*K4*Rp)
        return acc
    def load(p):
        a=array.array('d'); a.frombytes(open(p,'rb').read())
        if sys.byteorder!='little': a.byteswap()
        return a
    rec=dict(seat=seat,python=sys.version,executable=sys.executable,numpy_used=False,protocol_sha256=psha)
    ng=P['image_grid']['nx']*P['image_grid']['ny']; half=lambda h:range(0,N//2) if h==0 else range(N//2,N)
    psha_peer=sha_file(peer_p); seed=int(psha_peer[:16],16); idx=random.Random(seed).sample(range(ng),P['cross_witness']['K'])
    peer=load(peer_p); t0=time.monotonic(); worst=0.0; rows=[]
    for i in idx:
        x,y=grid_xy(P,i); v=pix(x,y,half(peer_h)); g=complex(peer[2*i],peer[2*i+1]); e=abs(v-g); worst=max(worst,e); rows.append([i,e])
    el=time.monotonic()-t0
    rec['cross_witness']=dict(peer_file_sha256=psha_peer,seed=seed,K=len(idx),indices_sha256=hashlib.sha256(json.dumps(idx).encode()).hexdigest(),max_abs_err=worst,
        tol=P['cross_witness']['abs_tol'],passed=worst<=P['cross_witness']['abs_tol'],wall_s=el,stdlib_pixel_pulse_per_s=len(idx)*len(half(peer_h))/el,errors=rows)
    own=load(own_p); sub=[iy*P['image_grid']['nx']+ix for iy in range(0,P['image_grid']['ny'],16) for ix in range(0,P['image_grid']['nx'],16)]
    t0=time.monotonic(); w2=0.0
    for i in sub:
        x,y=grid_xy(P,i); v=pix(x,y,half(own_h)); w2=max(w2,abs(v-complex(own[2*i],own[2*i+1])))
    el=time.monotonic()-t0
    rec['self_stdlib_reference']=dict(own_file_sha256=sha_file(own_p),n_pixels=len(sub),max_abs_err_vs_numpy=w2,wall_s=el,stdlib_pixel_pulse_per_s=len(sub)*len(half(own_h))/el,
        note='stdlib throughput includes analytic regeneration of 2 range bins per pixel-pulse (33 targets each)')
    rec['rusage']=rus(); rec['total_s']=time.monotonic()-t_all; rec['gate_post']=gate()
    json.dump(rec,open(os.path.join(out,'WITNESS.json'),'w'),indent=1)
    print('WITNESS',seat,'passed' if rec['cross_witness']['passed'] else 'FAILED',worst,w2)

if __name__=='__main__':
    m=sys.argv[1]
    g=gate(); 
    if not g['ok']: print('HOLD_PREFLIGHT',g); sys.exit(3)
    resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,512*1024*1024))
    os.environ['OPENBLAS_NUM_THREADS']='1'
    P=load_protocol(sys.argv[2],sys.argv[3])
    outdir=sys.argv[-1]; os.makedirs(outdir,exist_ok=True); json.dump(dict(mode=m,gate_pre=g,argv=sys.argv,start_unix=time.time()),open(os.path.join(outdir,f'PREFLIGHT-{m}.json'),'w'),indent=1)
    if m=='produce': produce(P,sys.argv[3],sys.argv[4],int(sys.argv[5]),outdir)
    elif m=='witness': witness(P,sys.argv[3],sys.argv[4],sys.argv[5],int(sys.argv[6]),sys.argv[7],int(sys.argv[8]),outdir)
