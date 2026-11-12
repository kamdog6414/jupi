#!/usr/bin/env python3
"""Cross-node comparison per RUN-README: exact ints/strings, floats abs 1e-7 px, IoU 1e-10. Also miss diagnosis."""
import json,sys,hashlib
a_dir,b_dir,outp=sys.argv[1],sys.argv[2],sys.argv[3]
def L(d,f):return json.load(open(f'{d}/{f}'))
A=L(a_dir,'RESULTS.json');B=L(b_dir,'RESULTS.json')
dis=[]
def walk(x,y,path):
 if type(x)!=type(y) and not (isinstance(x,(int,float)) and isinstance(y,(int,float)) and not isinstance(x,bool)):dis.append({'path':path,'a':x,'b':y,'kind':'TYPE'});return
 if isinstance(x,dict):
  if set(x)!=set(y):dis.append({'path':path,'kind':'KEYS','a':sorted(x),'b':sorted(y)})
  for k in sorted(set(x)&set(y)):walk(x[k],y[k],path+'/'+k)
 elif isinstance(x,list):
  if len(x)!=len(y):dis.append({'path':path,'kind':'LEN','a':len(x),'b':len(y)});return
  for i,(u,v) in enumerate(zip(x,y)):walk(u,v,path+f'[{i}]')
 elif isinstance(x,float) or isinstance(y,float):
  tol=1e-10 if 'iou' in path.lower() else 1e-7
  if abs(x-y)>tol:dis.append({'path':path,'kind':'FLOAT','a':x,'b':y,'tol':tol})
 elif x!=y:dis.append({'path':path,'kind':'EXACT','a':x,'b':y})
walk(A,B,'')
H=A['geometry_height_units']
rows=[]
for e,s in zip(A['variants'],A['summary']):
 ys=[r[0] for r in e['all_measured_rows_y_l_r']];r={'variant':e['variant'],'fit_n':e['fit_n'],'test_n':e['test_n'],'measured_y_min':min(ys),'measured_y_max':max(ys)}
 for m in('ghosting','cylinder'):
  M=e['models'][m];f=M['fit'];top=f['base_y_px']-f['scale_px_per_unit']*H
  miss=[p[0] for p in M['test_predictions_y_l_r'] if p[1] is None]
  r[m]={'test_width_mae_px':M['test_width_mae_px'],'test_mean_row_iou':M['test_mean_row_iou'],'outside_model_rows':M['outside_model_rows'],'scale':f['scale_px_per_unit'],'base_y':f['base_y_px'],'model_top_y':top,'centerline_a':f['centerline_a_px'],'centerline_b':f['centerline_b'],'fit_width_mae_px':f['fit_width_mae_px'],'miss_rows_above_model_top':sum(1 for y in miss if y<top),'miss_rows_below_model_base':sum(1 for y in miss if y>f['base_y_px']),'miss_y_list':miss}
 r.update({k:s[k] for k in('width_delta_G_minus_C_px','iou_delta_G_minus_C','span_status','width_winner','iou_winner')})
 rows.append(r)
eligA=[s['span_status'] for s in A['summary']];eligB=[s['span_status'] for s in B['summary']]
out={'a':a_dir,'b':b_dir,'results_sha256_a':hashlib.sha256(open(f'{a_dir}/RESULTS.json','rb').read()).hexdigest(),'results_sha256_b':hashlib.sha256(open(f'{b_dir}/RESULTS.json','rb').read()).hexdigest(),'split_identical':L(a_dir,'FROZEN-SPLIT.json')==L(b_dir,'FROZEN-SPLIT.json'),'disagreements_beyond_tolerance':dis,'n_disagreements':len(dis),'rank_eligibility_identical':eligA==eligB,'n_variants_hold_unsupported':sum(1 for x in eligA if x!='COMPLETE'),'n_variants_complete':sum(1 for x in eligA if x=='COMPLETE'),'variant_table':rows}
for k in('inputs','challenge_manifest_sha256','code_sha256'):
 ra,rb=L(a_dir,'RECEIPT.json'),L(b_dir,'RECEIPT.json');out['receipt_'+k+'_identical']=ra.get(k)==rb.get(k)
json.dump(out,open(outp,'w'),indent=1)
print('disagreements',len(dis),'elig_identical',eligA==eligB,'hold',out['n_variants_hold_unsupported'],'complete',out['n_variants_complete'])
