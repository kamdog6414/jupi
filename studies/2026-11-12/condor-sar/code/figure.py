#!/usr/bin/env python3
import json, math, numpy as np, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
plt.rcParams.update({'font.family':'monospace','font.size':8,'axes.edgecolor':'black','axes.labelcolor':'black','xtick.color':'black','ytick.color':'black','text.color':'black','axes.grid':True,'grid.color':'#bbbbbb','grid.linewidth':0.4})
P=json.load(open('protocol/PROTOCOL.json')); A=json.load(open('compare/ANALYSIS.json')); H=json.load(open('compare/POSTHOC-alias.json')); g=P['image_grid']
S=np.fromfile('compare/summed_grid.c128',complex).reshape(g['ny'],g['nx']); pk=A['determinism']['T0_peak_abs']
fig,ax=plt.subplots(2,2,figsize=(11,9),facecolor='white')
a=ax[0,0]; db=20*np.log10(np.abs(S)/pk+1e-12)
a.imshow(db,cmap='gray',vmin=-30,vmax=0,origin='lower',extent=[g['x0'],g['x0']+g['nx']*g['dx'],g['y0'],g['y0']+g['ny']*g['dx']],aspect='equal')
a.axhline(P['radar']['range_window_m'][1],color='white',lw=0.6,ls='--'); a.grid(False)
a.set_title('A  SUMMED IMAGE  JUPI[0,128) + JUPI2[128,256)\n|I| dB rel T0, -30..0; dashed = swath edge',loc='left'); a.set_xlabel('azimuth x (m)'); a.set_ylabel('slant range y (m)')
a=ax[0,1]
for k,ls,lab in (('T0_az','-','azimuth cut'),('T0_rg','--','range cut')):
    m=A['irf'][k]; u=np.array(m['u'])-(0 if k.endswith('az') else 1000); a.plot(u,m['cut_db'],'k',ls=ls,lw=1,label=lab)
u=np.linspace(-8,8,2001); rho=P['theory']['rho_az_nominal_m']; a.plot(u,20*np.log10(np.abs(np.sinc(u/rho))+1e-12),color='#888888',lw=0.8,ls=':',label='theory sinc (az)')
a.axhline(-13.26,color='k',lw=0.5,ls='-.'); a.set_ylim(-50,3); a.set_xlim(-6,6); a.legend(loc='upper right',frameon=False)
t0a,t0r=A['irf']['T0_az'],A['irf']['T0_rg']
a.set_title(f"B  T0 IMPULSE RESPONSE (fine cuts, 1/16 m)\nIRW az {t0a['irw_m']:.3f} m  rg {t0r['irw_m']:.3f} m   PSLR az {t0a['pslr_db']:.2f}  rg {t0r['pslr_db']:.2f} dB",loc='left'); a.set_xlabel('offset from T0 (m)'); a.set_ylabel('dB')
a=ax[1,0]; R=[r['R0_m']/1e3 for r in A['precision']]
for n,mk in (('JUPI','o'),('JUPI2','x')):
    a.plot(R,[r['f32_naive'][n]['gain_loss_db'] for r in A['precision']],'k',marker=mk,lw=1,ms=5,label=f'f32 naive ({n})')
a.plot(R,[r['pred_gain_db'] for r in A['precision']],color='#777777',ls='--',lw=1,label='predicted (ulp model, frozen)')
a.plot(R,[r['f32_refdiff']['JUPI2']['gain_loss_db'] for r in A['precision']],'k',ls=':',marker='s',ms=4,lw=1,label='f32 ref-diff (PPE f64 ref + SPU f32)')
a.axhline(-1,color='k',lw=0.5,ls='-.'); a.set_xscale('log'); a.set_ylim(-40,3); a.legend(loc='lower left',frameon=False)
a.set_title('C  PRECISION CLIFF: float32 vs float64 at target pixel\nN pulses = 256 x R0/1km (aperture 16 m .. 4.1 km)',loc='left'); a.set_xlabel('standoff R0 (km)'); a.set_ylabel('peak gain loss (dB)')
a=ax[1,1]; Ms=[1,2,4,8]; prf=[H['levels_db'][str(M)]['prf_hz'] for M in Ms]
a.plot(prf,[H['levels_db'][str(M)]['O2_ghost_M4'] for M in Ms],'k-o',lw=1,label='ghost of out-of-scene O2 (pred. onset 400 Hz)')
a.plot(prf,[H['levels_db'][str(M)]['T0_ghost_M8_plus'] for M in Ms],'k--x',lw=1,label='grating lobe of T0 (pred. onset 200 Hz)')
a.set_xscale('log',base=2); a.set_xticks(prf); a.set_xticklabels([str(int(p)) for p in prf]); a.invert_xaxis(); a.set_ylim(-50,3); a.legend(loc='center left',frameon=False)
a.set_title('D  PRF DECIMATION: azimuth ambiguity onset\n(post-hoc probe at frozen predicted ghost sites)',loc='left'); a.set_xlabel('PRF (Hz), v = 100 m/s'); a.set_ylabel('dB rel T0')
fig.suptitle('CONDOR-LINEAGE SAR v0 / JUPI + JUPI2 / 2026-11-12 PST / synthetic data only / private',x=0.01,ha='left',fontsize=10,fontweight='bold')
fig.text(0.01,0.005,f"protocol sha256 {A['protocol_sha256'][:16]}..  code {A['code_sha256'][:16]}..  summed vs single-node rel diff {A['determinism']['summed_vs_JUPI2_full']['rel_to_T0_peak']:.1e}  witness K=512 x2 PASS",fontsize=7)
plt.tight_layout(rect=[0,0.02,1,0.97]); plt.savefig('CONDOR-SAR-FIGURE.png',dpi=130,facecolor='white')
