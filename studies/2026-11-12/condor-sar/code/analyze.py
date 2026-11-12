#!/usr/bin/env python3
"""Box-side gather + scoring against the frozen protocol. Writes compare/*.json."""
import json, hashlib, math, sys, os
import numpy as np
sys.path.insert(0,os.path.dirname(__file__)); import condor_sar as cs
W=sys.argv[1]; P=json.load(open(f'{W}/protocol/PROTOCOL.json')); PS=open(f'{W}/protocol/PROTOCOL.json.sha256').read().split()[0]
assert cs.sha_file(f'{W}/protocol/PROTOCOL.json')==PS
g=P['image_grid']; NX,NY=g['nx'],g['ny']; T={t['name']:t for t in P['targets']}; th=P['theory']
ld=lambda p:np.fromfile(p,complex)
J={n:f'{W}/{n}/produce' for n in ('JUPI','JUPI2')}
out={'protocol_sha256':PS,'code_sha256':cs.sha_file(f'{W}/code/condor_sar.py')}
# inputs agreement
phA,phB=ld(J['JUPI']+'/phase_history.c128'),ld(J['JUPI2']+'/phase_history.c128')
out['phase_history']=dict(sha_JUPI=cs.sha_file(J['JUPI']+'/phase_history.c128'),sha_JUPI2=cs.sha_file(J['JUPI2']+'/phase_history.c128'),max_abs_diff=float(np.abs(phA-phB).max()),bit_identical=bool(np.array_equal(phA,phB)))
# gather
pa,pb=ld(J['JUPI']+'/partial_grid.c128'),ld(J['JUPI2']+'/partial_grid.c128'); S=(pa+pb)
ca,cb=ld(J['JUPI']+'/partial_cuts.c128'),ld(J['JUPI2']+'/partial_cuts.c128'); SC=ca+cb
S.tofile(f'{W}/compare/summed_grid.c128'); SC.tofile(f'{W}/compare/summed_cuts.c128')
fA,fB=ld(J['JUPI']+'/full_M1_grid.c128'),ld(J['JUPI2']+'/full_M1_grid.c128')
iT0=int(round((0-g['x0'])/g['dx']))+NX*int(round((1000-g['y0'])/g['dx'])); pk=abs(S[iT0])
tol=1e-9*pk
cmp=lambda a,b:dict(max_abs=float(np.abs(a-b).max()),rel_to_T0_peak=float(np.abs(a-b).max()/pk),bit_identical=bool(np.array_equal(a,b)),pass_=bool(np.abs(a-b).max()<=tol))
out['determinism']=dict(T0_peak_abs=float(pk),tol_abs=tol,summed_vs_JUPI2_full=cmp(S,fB),summed_vs_JUPI_full=cmp(S,fA),JUPI_full_vs_JUPI2_full=cmp(fA,fB),
  partial_sha=dict(JUPI=cs.sha_file(J['JUPI']+'/partial_grid.c128'),JUPI2=cs.sha_file(J['JUPI2']+'/partial_grid.c128')),
  summed_sha=cs.sha_file(f'{W}/compare/summed_grid.c128'),
  cuts_summed_vs_JUPI2_full=cmp(SC,ld(J['JUPI2']+'/full_M1_cuts.c128')))
# detection table (integer) recomputed from summed
A=np.abs(S).reshape(NY,NX); det=[]
for t in P['targets']:
    ix=int(round((t['x']-g['x0'])/g['dx'])); iy=int(round((t['y']-g['y0'])/g['dx']))
    if 0<=ix<NX and 0<=iy<NY:
        a0,a1,b0,b1=max(iy-4,0),min(iy+5,NY),max(ix-4,0),min(ix+5,NX); w=A[a0:a1,b0:b1]; j=np.unravel_index(np.argmax(w),w.shape); det.append([t['name'],int(a0+j[0]),int(b0+j[1])])
ds=json.dumps(det,separators=(',',':')).encode(); open(f'{W}/compare/detections_summed.json','wb').write(ds)
h=lambda b:hashlib.sha256(b).hexdigest()
dh=dict(summed=h(ds),JUPI=h(open(J['JUPI']+'/detections.json','rb').read()),JUPI2=h(open(J['JUPI2']+'/detections.json','rb').read()))
out['integer_detection_table']=dict(sha256=dh,exact_match=len(set(dh.values()))==1,n=len(det))
# cuts
cuts=cs.cut_points(P); seg={}; o=0
for nm,ax,pts in cuts: seg[nm]=(ax,pts,SC[o:o+len(pts)]); o+=len(pts)
irf={}; okirw=okpsl=True
for nm in P['fine_cuts']['irf_targets']:
    for ax in ('az','rg'):
        a,pts,v=seg[f'{nm}_{ax}']; u=np.array([q[0] if ax=='az' else q[1] for q in pts]); m=cs.cut_metrics(u,np.abs(v)**2)
        exp=th['irw3db_az_m'] if ax=='az' else th['irw3db_range_m']; tp=T[nm]['x'] if ax=='az' else T[nm]['y']
        m['irw_theory_m']=exp; m['irw_err_pct']=None if m['irw_m'] is None else 100*(m['irw_m']-exp)/exp; m['peak_offset_m']=m['peak_m']-tp
        m['peak_db_rel_T0']=10*math.log10(m['peak_power']/pk**2) if m['peak_power']>0 else None
        if nm!='E':
            m['irw_pass']=m['irw_m'] is not None and abs(m['irw_err_pct'])<=10; m['pslr_pass']=m['pslr_db'] is not None and -14.0<=m['pslr_db']<=-12.5
            okirw&=m['irw_pass']; okpsl&=m['pslr_pass']
        m['cut_db']=[float(10*math.log10(max(abs(z)**2,1e-30)/pk**2)) for z in v]; m['u']=[float(x) for x in u]
        irf[f'{nm}_{ax}']=m
out['irf']=irf; out['irw_pass']=okirw; out['pslr_pass']=okpsl
# position on main grid (parabolic both axes)
pos={}; okpos=True
for nm in ('T0','T1','T2'):
    t=T[nm]; ix=int(round((t['x']-g['x0'])/g['dx'])); iy=int(round((t['y']-g['y0'])/g['dx'])); w=A[iy-3:iy+4,ix-3:ix+4]**2; j=np.unravel_index(np.argmax(w),w.shape); jy,jx=iy-3+j[0],ix-3+j[1]
    def par(a,b,c): a,b,c=np.log(a),np.log(b),np.log(c); return 0.5*(a-c)/(a-2*b+c)
    ox=par(A[jy,jx-1]**2,A[jy,jx]**2,A[jy,jx+1]**2); oy=par(A[jy-1,jx]**2,A[jy,jx]**2,A[jy+1,jx]**2)
    ex=(jx+ox)-(t['x']-g['x0'])/g['dx']; ey=(jy+oy)-(t['y']-g['y0'])/g['dx']; pos[nm]=dict(err_x_px=float(ex),err_y_px=float(ey),err_px=float(math.hypot(ex,ey)),pass_=bool(math.hypot(ex,ey)<0.5)); okpos&=pos[nm]['pass_']
out['position']=pos; out['position_pass']=okpos
# pairs
pr=[]
for p in P['pairs']:
    ax,pts,v=seg[p['name']]; u=np.array([q[0] if ax=='az' else q[1] for q in pts]); a,b=T[p['a']],T[p['b']]
    ua,ub=(a['x'],b['x']) if ax=='az' else (a['y'],b['y'])
    # reuse protocol dip rule
    pw=np.abs(v)**2; m=(ua+ub)/2; L1=(u>=ua-0.5*(ub-ua)-0.3)&(u<=m); L2=(u>=m)&(u<=ub+0.5*(ub-ua)+0.3)
    i1=np.where(L1)[0][np.argmax(pw[L1])]; i2=np.where(L2)[0][np.argmax(pw[L2])]
    if i2<=i1+1: res=dict(resolved=False,dip_db=0.0)
    else:
        jmin=i1+int(np.argmin(pw[i1:i2+1])); d=10*math.log10(pw[jmin]/min(pw[i1],pw[i2])); res=dict(resolved=bool(i1<jmin<i2 and d<=-3),dip_db=float(d))
    pr.append(dict(name=p['name'],axis=ax,factor=p['factor'],sep_m=p['sep_m'],phi_rel=p['phi_rel_rad_mod2pi'],measured=res,theory=p['theory'],theory_inphase=p['theory_inphase'],agree=res['resolved']==p['theory']['resolved']))
out['pairs']=pr; out['pairs_agree']=sum(q['agree'] for q in pr)
# smallest separation resolved, per axis, for which all larger also resolved
for axn in ('az','rg'):
    q=[x for x in pr if x['axis']==axn]
    out[f'pairs_{axn}_resolved_factors']=[x['factor'] for x in q if x['measured']['resolved']]
# O1 outside
o1=T['O1']; ix=int(round((o1['x']-g['x0'])/g['dx'])); iy=int(round((o1['y']-g['y0'])/g['dx']))
lvl=20*math.log10(A[iy,ix]/pk) if A[iy,ix]>0 else -999.0; o1_exact_zero=bool(A[iy,ix]==0); reg=A[int((1041-952)/0.25):,int((-14+32)/0.25):int((-6+32)/0.25)]
leak=20*math.log10(reg.max()/pk) if reg.max()>0 else 'exactly 0 (no data support)'
a,pts,v=seg['O1_rg']; uu=np.array([q[1] for q in pts]); vv=np.abs(v)
out['O1']=dict(level_at_true_pixel_db=lvl,pass_=bool(lvl<-40),max_beyond_window_region_db=leak,max_on_cut_db=float(20*math.log10(vv.max()/pk)) if vv.max()>0 else None,argmax_cut_y=float(uu[np.argmax(vv)]),
  true_pixel_exactly_zero=o1_exact_zero,note='region x in [-14,-6), y>=1041 (all beyond the 1040 m window edge)')
# E edge
e=irf['E_rg']; out['E_az_cut_at_exact_edge_all_zero']=bool(irf['E_az']['peak_power']==0); out['E']=dict(peak_db_rel_T0=e['peak_db_rel_T0'],peak_range_bias_m=e['peak_offset_m'],irw_rg_m=e['irw_m'],peak_az_db=irf['E_az']['peak_db_rel_T0'])
# decimation
dec={}
excl=[(t['x'],t['y']) for t in P['targets'] if -32<=t['x']<32 and 952<=t['y']<1048]
GX,GY=np.meshgrid(g['x0']+np.arange(NX)*g['dx'],g['y0']+np.arange(NY)*g['dx'])
mask=np.ones((NY,NX),bool)
for x,y in excl: mask&=np.hypot(GX-x,GY-y)>3
mask&=GY<=1034
for M in P['decimation']['M']:
    im={n:ld(f'{J[n]}/full_M{M}_grid.c128') for n in J}; Am=np.abs(im['JUPI2']).reshape(NY,NX); pkM=Am.ravel()[iT0]
    sp=20*math.log10(Am[mask].max()/pkM); jj=np.unravel_index(np.argmax(np.where(mask,Am,0)),Am.shape)
    gh=[]
    for tn,lst in P['theory']['decimation_ghosts'][str(M)].items():
        if tn in ('O2','T0','T1','T2'):
            for q in lst:
                w=(np.hypot(GX-q['x'],GY-q['y'])<1.5); j2=np.unravel_index(np.argmax(np.where(w,Am,0)),Am.shape)
                gh.append(dict(source=tn,order=q['order'],pred_x=q['x'],pred_y=q['y'],meas_x=float(GX[j2]),meas_y=float(GY[j2]),level_db=float(20*math.log10(Am[j2]/pkM))))
    dec[str(M)]=dict(prf_hz=P['radar']['prf_hz']/M,pulse_spacing_m=P['radar']['pulse_spacing_m']*M,T0_peak=float(pkM),T0_peak_vs_M1_db=float(20*math.log10(pkM/pk)),max_spurious_db=float(sp),
       spurious_at=[float(GX[jj]),float(GY[jj])],aliased=bool(sp>=P['decimation']['alias_threshold_db']),ghosts=gh,cross_node=cmp(im['JUPI'],im['JUPI2']))
out['decimation']=dec; out['alias_onset_measured_M']=next((int(M) for M in dec if dec[M]['aliased']),None); out['alias_onset_predicted_M']=P['theory']['predicted_alias_onset_M']
# precision
RA,RB=[json.load(open(f'{J[n]}/RESULT.json')) for n in ('JUPI','JUPI2')]
prec=[]
for a,b,pd in zip(RA['precision'],RB['precision'],P['theory']['precision_prediction']):
    row=dict(R0_m=a['R0_m'],N=a['N'],aperture_m=a['aperture_m'],pred_phase_rms=pd['pred_phase_rms_rad'],pred_gain_db=pd['pred_gain_loss_db'])
    for md in ('f64','f32_naive','f32_refdiff'):
        va=np.array(a['modes'][md]['cut']); vb=np.array(b['modes'][md]['cut']); rel=float(np.abs(va-vb).max()/np.abs(vb).max())
        row[md]=dict(JUPI={k:a['modes'][md].get(k) for k in ('gain_loss_db','phase_rms_rad','irw_m','pslr_db','peak_m')},JUPI2={k:b['modes'][md].get(k) for k in ('gain_loss_db','phase_rms_rad','irw_m','pslr_db','peak_m')},
                     cross_node_rel=rel,cross_node_pass=bool(rel<=(1e-9 if md=='f64' else 1e-4)),bit_identical=a['modes'][md]['cut_sha256']==b['modes'][md]['cut_sha256'])
    prec.append(row)
out['precision']=prec
c1=[r['R0_m'] for r in prec if (r['f32_naive']['JUPI2']['gain_loss_db'] or 0)<-1.0]
out['precision_cliff_measured_R0_m']=c1[0] if c1 else None
pc=[r['R0_m'] for r in prec if r['pred_gain_db']<-1.0]; out['precision_cliff_predicted_R0_m']=pc[0] if pc else None
# witness + resources
WJ={n:json.load(open(f'{W}/{n}/witness/WITNESS.json')) for n in J}
out['witness']={n:{k:WJ[n]['cross_witness'][k] for k in ('peer_file_sha256','seed','K','indices_sha256','max_abs_err','tol','passed','wall_s','stdlib_pixel_pulse_per_s')}|dict(self_ref_max_err=WJ[n]['self_stdlib_reference']['max_abs_err_vs_numpy'],self_ref_stdlib_pps=WJ[n]['self_stdlib_reference']['stdlib_pixel_pulse_per_s'],python=WJ[n]['python'].split()[0],rusage=WJ[n]['rusage'],total_s=WJ[n]['total_s']) for n in J}
out['witness']['JUPI']['witnessed_peer']='JUPI2';out['witness']['JUPI2']['witnessed_peer']='JUPI'
out['witness_peer_sha_matches']=dict(JUPI_saw=WJ['JUPI']['cross_witness']['peer_file_sha256']==out['determinism']['partial_sha']['JUPI2'],JUPI2_saw=WJ['JUPI2']['cross_witness']['peer_file_sha256']==out['determinism']['partial_sha']['JUPI'])
out['nodes']={}
for n,R in (('JUPI',RA),('JUPI2',RB)):
    pre=json.load(open(f'{J[n]}/PREFLIGHT-produce.json'))['gate_pre']; prw=json.load(open(f'{W}/{n}/witness/PREFLIGHT-witness.json'))['gate_pre']
    out['nodes'][n]=dict(python=R['python'].split()[0],numpy=R['numpy'],executable=R['executable'],timings=R['timings'],numpy_pps=R['throughput_numpy_pixel_pulse_per_s'],rusage=R['rusage'],gate_pre_produce=pre,gate_pre_witness=prw,gate_post=R['gate_post'],
        wall_total_s=R['timings']['total_s']+WJ[n]['total_s'],outputs=R['outputs'])
json.dump(out,open(f'{W}/compare/ANALYSIS.json','w'),indent=1,default=float)
print(json.dumps({k:out[k] for k in ('phase_history','integer_detection_table','irw_pass','pslr_pass','position','pairs_agree','pairs_az_resolved_factors','pairs_rg_resolved_factors','O1','E','alias_onset_measured_M','alias_onset_predicted_M','precision_cliff_measured_R0_m','precision_cliff_predicted_R0_m','witness_peer_sha_matches')},indent=0,default=float))
print(json.dumps(out['determinism'],default=float))
for k,v in irf.items(): print(k,round(v['irw_m'] or -1,4),v['irw_err_pct'] and round(v['irw_err_pct'],2),v['pslr_db'] and round(v['pslr_db'],2),round(v['peak_offset_m'],4),v['peak_db_rel_T0'] and round(v['peak_db_rel_T0'],2))
for q in pr: print(q['name'],q['factor'],round(q['phi_rel'],2),q['measured'],q['theory'],q['agree'])
for M,v in dec.items(): print(M,v['prf_hz'],round(v['max_spurious_db'],2),v['spurious_at'],v['aliased'],[(x['source'],round(x['level_db'],1),round(x['meas_x']-x['pred_x'],2),round(x['meas_y']-x['pred_y'],2)) for x in v['ghosts']],v['cross_node']['bit_identical'],v['cross_node']['rel_to_T0_peak'])
for r in prec: print(r['R0_m'],r['N'],round(r['pred_gain_db'],3),{m:(round(r[m]['JUPI2']['gain_loss_db'] or 0,3),round(r[m]['JUPI2']['phase_rms_rad'] or 0,4),r[m]['JUPI2']['pslr_db'] and round(r[m]['JUPI2']['pslr_db'],2),r[m]['cross_node_rel'],r[m]['bit_identical']) for m in ('f32_naive','f32_refdiff')})
