#!/usr/bin/env python3
"""POST-HOC (written after seeing that the frozen alias metric fires at M=1). Not a frozen criterion.
Probe: max |I| within 1.0 m of the protocol's predicted O2 ghost location for M=4 (-2.881, 1006.785), and of T0's M=8 ghost (31.228, 999.512), for every M, dB rel T0 peak at that M."""
import numpy as np, json, math
P=json.load(open('protocol/PROTOCOL.json')); g=P['image_grid']; NX,NY=g['nx'],g['ny']
GX,GY=np.meshgrid(g['x0']+np.arange(NX)*g['dx'],g['y0']+np.arange(NY)*g['dx'])
probes={'O2_ghost_M4':P['theory']['decimation_ghosts']['4']['O2'][0],'T0_ghost_M8_plus':[q for q in P['theory']['decimation_ghosts']['8']['T0'] if q['order']==1][0]}
iT0=int(round((0-g['x0'])/g['dx']))+NX*int(round((1000-g['y0'])/g['dx'])); out={}
for M in P['decimation']['M']:
    A=np.abs(np.fromfile(f'JUPI2/produce/full_M{M}_grid.c128',complex)).reshape(NY,NX); pk=A.ravel()[iT0]; row={}
    for k,q in probes.items():
        w=np.hypot(GX-q['x'],GY-q['y'])<1.0; row[k]=float(20*math.log10(A[w].max()/pk))
    out[str(M)]=dict(prf_hz=P['radar']['prf_hz']/M,**row)
json.dump(dict(note=__doc__,probes=probes,levels_db=out),open('compare/POSTHOC-alias.json','w'),indent=1); print(json.dumps(out,indent=0))
