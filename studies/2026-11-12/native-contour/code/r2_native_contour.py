#!/usr/bin/env python3
"""R2 revision (span-coverage camera support). Derived from v1 source; measurement unchanged. No network, GPU or installs."""
import argparse,hashlib,json,math,os,pathlib,sys,time
START=time.monotonic()
def sha(b):return hashlib.sha256(b).hexdigest()
def compact(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def write(p,x):
 b=compact(x);t=p.with_suffix(p.suffix+'.tmp');t.write_bytes(b);os.replace(t,p);return {'relative_path':p.name,'bytes':len(b),'sha256':sha(b)}
def hold(s):raise ValueError(s)
def local(s):
 p=pathlib.Path(s)
 if not p.is_absolute() or str(p).startswith(('//','\\\\')):hold('ABSOLUTE_LOCAL_PATH_REQUIRED')
 if os.name=='nt' and (':' in str(p)[2:] or str(p).startswith('\\\\')):hold('PATH_NAMESPACE')
 return p
p=argparse.ArgumentParser();p.add_argument('--packet-root',required=True);p.add_argument('--manifest-sha256',required=True);p.add_argument('--protocol',required=True);p.add_argument('--protocol-sha256',required=True);p.add_argument('--out',required=True);p.add_argument('--time-budget-s',type=int,default=600);a=p.parse_args()
try:
 if not 1<=a.time_budget_s<=600:hold('TIME_BUDGET_1_TO_600')
 root=local(a.packet_root);out=local(a.out)
 if out.exists():hold('NEW_OUTPUT_REQUIRED')
 if len(a.manifest_sha256)!=64 or any(c not in '0123456789abcdef' for c in a.manifest_sha256):hold('MANIFEST_HASH')
 mraw=(root/'CHALLENGE-MANIFEST.json').read_bytes()
 if len(mraw)>32768 or sha(mraw)!=a.manifest_sha256:hold('MANIFEST_PIN')
 mf=json.loads(mraw)
 if set(mf)!={'schema','files','protocol'} or mf['schema']!='fullcircle.ghosting.native-contour.challenge.v1':hold('MANIFEST_SCHEMA')
 expected={'native_contour_challenge.py','photo-1-original.jpg','FROZEN-STACK-SCENE.json'}
 if set(mf['files'])!=expected:hold('FIXED_INPUTS')
 blobs={}
 for name,ref in mf['files'].items():
  if set(ref)!={'bytes','sha256'} or type(ref['bytes']) is not int or not 0<ref['bytes']<=8*1024*1024:hold('REF_SCHEMA')
  fp=root/name
  if fp.stat().st_size!=ref['bytes']:hold('INPUT_LENGTH:'+name)
  b=fp.read_bytes()
  if len(b)!=ref['bytes'] or sha(b)!=ref['sha256']:hold('INPUT_PIN:'+name)
  blobs[name]=b
 praw=local(a.protocol).read_bytes()
 if sha(praw)!=a.protocol_sha256:hold('R2_PROTOCOL_PIN')
 proto=json.loads(praw)
 if proto['revision']!='R2' or proto['parent']['challenge_manifest_sha256']!=a.manifest_sha256:hold('R2_PROTOCOL_PARENT')
 for k,v in proto['inputs'].items():
  if sha(blobs[k])!=v:hold('R2_INPUT_PIN:'+k)
 avail=None
 if pathlib.Path('/proc/meminfo').exists():
  for line in pathlib.Path('/proc/meminfo').read_text().splitlines():
   if line.startswith('MemAvailable:'):avail=int(line.split()[1])*1024
 elif os.name=='nt':
  import ctypes
  class MS(ctypes.Structure):_fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(k,ctypes.c_ulonglong) for k in ('total','available','totalpage','availablepage','totalvirtual','availablevirtual','extended')]
  ms=MS();ms.length=ctypes.sizeof(ms)
  if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms)):avail=ms.available
 if avail is None or avail<256*1024*1024:hold('PREFLIGHT_AVAILABLE_RAM_256_MIB')
 if os.name=='posix':
  import resource
  if hasattr(resource,'RLIMIT_AS'):
   old=resource.getrlimit(resource.RLIMIT_AS);lim=256*1024*1024;resource.setrlimit(resource.RLIMIT_AS,(min(lim,old[1]) if old[1]>=0 else lim,old[1]))
 try:from PIL import Image,__version__ as pillow_version
 except ImportError:hold('EXISTING_PILLOW_REQUIRED_NO_INSTALL')
 import io
 image=Image.open(io.BytesIO(blobs['photo-1-original.jpg']))
 if image.size!=(3000,1999):hold('FIXED_NATIVE_DIMENSIONS')
 image.load();gray=image.convert('L');image.close();pixels=gray.load()
 scene=json.loads(blobs['FROZEN-STACK-SCENE.json'])['scene']
 parts=[q for q in scene['parts'] if q.get('rocket') and q['component_id'] in ('booster','upperstage','fairing_left','fairing_right')]
 if not 1<=len(parts)<=256:hold('BOUNDED_PARTS')
 def extent(q,y):
  x,c,z=q['center'];v=q['params'];d=y-c;k=q['kind']
  if k=='frustum':
   h,r0,r1=v[:3]
   if abs(d)>h:return None
   r=r0+(r1-r0)*(d+h)/(2*h);return x-r,x+r
  if k=='half_frustum':
   h,r=v[:2]
   if abs(d)>h:return None
   return (x-r,x) if v[3]<0 else (x,x+r)
  if k=='half_ellipsoid':
   r,h=v[:2]
   if not 0<=d<=h:return None
   r=r*math.sqrt(max(0,1-(d/h)**2));return (x-r,x) if v[3]<0 else (x,x+r)
  if k in ('box','ellipsoid'):
   if abs(d)>v[1]:return None
   return x-v[0],x+v[0]
  hold('UNKNOWN_PART_KIND')
 low=min(q['center'][1]-q['params'][0 if q['kind'] in ('frustum','half_frustum') else 1] for q in parts)
 high=max(q['center'][1]+q['params'][0 if q['kind'] in ('frustum','half_frustum') else 1] for q in parts);height=high-low
 profile=[]
 for i in range(401):
  intervals=[e for e in (extent(q,low+height*i/400) for q in parts) if e]
  profile.append((max(e[1] for e in intervals)-min(e[0] for e in intervals))/2 if intervals else 0)
 rmax=max(profile)
 out.mkdir(parents=True,exist_ok=False)
 split={'schema':'fullcircle.ghosting.native-row-split.v1','r2_protocol_sha256':a.protocol_sha256,'r2_rule':proto['rule'],'frame':'PHOTO1_NATIVE_PIXELS_3000x1999','rule':'floor(native_y/32)%2 == 0 FIT, else TEST','decision':'FROZEN_BEFORE_ANY_VARIANT_FIT','y_range_exclusive':[0,1163],'plume_top_native_from_old_reduced':[1489.5,1162.917],'roi_center_x':1489.5,'roi_halfwidths_px':[80,100,120],'methods':{'peak_contiguous_fraction':[0.35,0.5,0.65],'energy_central_mass':[0.5,0.65,0.8]},'contrast_min_intensity':60,'minimum_width_px':2,'models':'fixed Ghosting 401-bin envelope vs fixed cylinder same height/max radius','camera_family':'same per-model orthographic similarity; centerline x=a+b*y; scale/base fitted FIT only','fit_grid':{'scale_px_per_unit':[8,24,0.5],'base_row':[1163,1483,8],'refine_scale_step':0.1,'refine_base_step':2},'missing_model_rows':'Every miss retained; nominal25px penalty is diagnostic only. Any test-span miss in either rival forces ranking HOLD.', 'uncertainty':'Native pixel quantization, threshold/method/ROI nuisance sensitivity; NOT calibrated physical uncertainty.'}
 split_ref=write(out/'FROZEN-SPLIT.json',split)
 results=[];artifacts=[split_ref];timed_out=False
 def budget():
  if time.monotonic()-START>a.time_budget_s:raise TimeoutError('BOUNDED_TIME_EXCEEDED')
 def model_w(name,h):
  if h<0 or h>height:return None
  return rmax if name=='cylinder' else profile[min(400,int(round(h/height*400)))]
 def score_width(rows,name,s,y0):
  total=0
  for y,l,r in rows:
   w=model_w(name,(y0-y)/s);total+=25 if w is None else abs(s*w-(r-l)/2)
  return total/max(1,len(rows))
 def admissible(name,s,y0,ally):
  return all(model_w(name,(y0-y)/s) is not None for y in ally)
 def fit(rows,name,ally):
  n=len(rows);my=sum(r[0] for r in rows)/n;mx=sum((r[1]+r[2])/2 for r in rows)/n
  b=sum((y-my)*((l+r)/2-mx) for y,l,r in rows)/max(1e-9,sum((y-my)**2 for y,l,r in rows));aa=mx-b*my
  best=(float('inf'),0,0);n_adm=0
  for si in range(16,49):
   budget();s=si/2
   for y0 in range(1163,1484,8):
    if admissible(name,s,y0,ally):n_adm+=1;best=min(best,(score_width(rows,name,s,y0),s,y0))
  if n_adm==0:return None
  _,s0,y00=best
  for ds in range(-5,6):
   budget();s=s0+ds/10
   for dy in range(-8,9,2):
    if admissible(name,s,y00+dy,ally):best=min(best,(score_width(rows,name,s,y00+dy),s,y00+dy))
  return {'fit_width_mae_px':best[0],'scale_px_per_unit':best[1],'base_y_px':best[2],'centerline_a_px':aa,'centerline_b':b,'admissible_coarse_points':n_adm}
 for half in (80,100,120):
  for method,levels in (('peak_contiguous_fraction',(0.35,0.5,0.65)),('energy_central_mass',(0.5,0.65,0.8))):
   for level in levels:
    budget();rows=[];cx=round(1489.5);x0=cx-half;x1=cx+half
    for y in range(1163):
     vals=[pixels[x,y] for x in range(x0,x1+1)];sv=sorted(vals);bg=sv[max(0,len(vals)//10)];peak=max(vals)
     if peak-bg<60:continue
     if method=='peak_contiguous_fraction':
      threshold=bg+level*(peak-bg);mid=vals.index(peak);l=r=mid
      while l>0 and vals[l-1]>=threshold:l-=1
      while r+1<len(vals) and vals[r+1]>=threshold:r+=1
     else:
      weights=[max(0,v-bg) for v in vals];total=sum(weights);tail=(1-level)*total/2;acc=0;l=0;r=len(vals)-1
      for i,v in enumerate(weights):
       acc+=v
       if acc>=tail:l=i;break
      acc=0
      for i in range(len(weights)-1,-1,-1):
       acc+=weights[i]
       if acc>=tail:r=i;break
     if r-l+1>=2:rows.append([y,x0+l-0.5,x0+r+0.5])
    train=[r for r in rows if (r[0]//32)%2==0];test=[r for r in rows if (r[0]//32)%2==1];vid=method+'-'+str(level)+'-roi'+str(half)
    if min(len(train),len(test))<32:results.append({'variant':vid,'status':'HOLD_INSUFFICIENT_ROWS','fit_n':len(train),'test_n':len(test)});continue
    entry={'variant':vid,'method':method,'level':level,'roi_halfwidth_px':half,'fit_n':len(train),'test_n':len(test),'models':{}}
    ally=[r[0] for r in rows];noadm=False
    for name in ('ghosting','cylinder'):
     params=fit(train,name,ally);pred=[];errors=[];ious=[];miss=0
     if params is None:entry['models'][name]={'status':'HOLD_NO_ADMISSIBLE_SUPPORT'};noadm=True;continue
     for y,l,r in test:
      w=model_w(name,(params['base_y_px']-y)/params['scale_px_per_unit'])
      if w is None:miss+=1;pred.append([y,None,None]);errors.append(25);ious.append(0);continue
      center=params['centerline_a_px']+params['centerline_b']*y;hw=w*params['scale_px_per_unit'];pl,pr=center-hw,center+hw
      errors.append(abs(hw-(r-l)/2));inter=max(0,min(pr,r)-max(pl,l));union=max(pr,r)-min(pl,l);ious.append(inter/union if union>0 else 0);pred.append([y,pl,pr])
     entry['models'][name]={'fit':params,'test_width_mae_px':sum(errors)/len(errors),'test_mean_row_iou':sum(ious)/len(ious),'outside_model_rows':miss,'test_predictions_y_l_r':pred}
    entry['status']='HOLD_NO_ADMISSIBLE_SUPPORT' if noadm else 'COMPUTED_RETROSPECTIVE_PIXEL_COMPARISON';entry['all_measured_rows_y_l_r']=rows
    results.append(entry);write(out/'PROGRESS.json',{'done_variants':len(results),'total_variants':18,'elapsed_s':time.monotonic()-START,'status':'RUNNING'})
 summary=[]
 for e in results:
  if 'models' not in e:continue
  if e['status']=='HOLD_NO_ADMISSIBLE_SUPPORT':summary.append({'variant':e['variant'],'span_status':'HOLD_NO_ADMISSIBLE_SUPPORT','width_winner':'HOLD_NO_ADMISSIBLE_SUPPORT','iou_winner':'HOLD_NO_ADMISSIBLE_SUPPORT'});continue
  g=e['models']['ghosting'];c=e['models']['cylinder'];dw=g['test_width_mae_px']-c['test_width_mae_px'];di=g['test_mean_row_iou']-c['test_mean_row_iou']
  summary.append({'variant':e['variant'],'width_delta_G_minus_C_px':dw,'iou_delta_G_minus_C':di,'span_status':'HOLD_UNSUPPORTED_TEST_ROWS' if g['outside_model_rows'] or c['outside_model_rows'] else 'COMPLETE','width_winner':'HOLD_UNSUPPORTED_TEST_ROWS' if g['outside_model_rows'] or c['outside_model_rows'] else ('INDETERMINATE' if abs(dw)<1 else ('GHOSTING' if dw<0 else 'CYLINDER')),'iou_winner':'HOLD_UNSUPPORTED_TEST_ROWS' if g['outside_model_rows'] or c['outside_model_rows'] else ('INDETERMINATE' if abs(di)<0.02 else ('GHOSTING' if di>0 else 'CYLINDER'))})
 n_ok=sum(1 for x in summary if x['span_status']=='COMPLETE')
 data={'r2_protocol_sha256':a.protocol_sha256,'r2_success_criterion':proto['success_criterion'],'r2_variants_complete':n_ok,'r2_local_verdict':'ALL_18_SUPPORTED_ON_THIS_NODE' if n_ok==18 and len(summary)==18 else 'NOT_ALL_SUPPORTED_ON_THIS_NODE','schema':'fullcircle.ghosting.native-contour.results.r2','classification':'RETROSPECTIVE_MEASUREMENT_SENSITIVITY_NOT_FLIGHT_VALIDATION','frozen_split':split_ref,'geometry_height_units':height,'geometry_max_halfwidth_units':rmax,'profile_policy':'Same401-bin envelope and cylinder as prior Groku study; ellipsoid pieces conservatively use box extents, disclosed approximation. No geometry tuning.','variants':results,'rank_margins_predeclared':{'width_px':1,'row_iou':0.02},'summary':summary,'physical_validation':'NOT_RUN','camera_calibration':'UNKNOWN','world_pose_and_timing':'HOLD','statistical_independence':'Neighboring image rows are correlated; no IID confidence or discovery claim.'}
 artifacts.append(write(out/'RESULTS.json',data))
 peak=None
 if os.name=='posix':peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
 receipt={'schema':'fullcircle.ghosting.native-contour.receipt.r2','r2_protocol_sha256':a.protocol_sha256,'status':'COMPUTED_RETROSPECTIVE_SENSITIVITY','inputs':mf['files'],'challenge_manifest_sha256':a.manifest_sha256,'code_sha256':sha(pathlib.Path(__file__).read_bytes()),'runtime':{'python':sys.version,'pillow':pillow_version,'libjpeg':__import__('PIL.features',fromlist=['x']).version('jpg'),'cpu_s':time.process_time(),'wall_s':time.monotonic()-START,'available_ram_preflight_bytes':avail,'posix_peak_rss_bytes':peak,'memory_policy':'POSIX256MiB address-space limit; Windows available-memory preflight only.'},'gpu_used':False,'artifacts':artifacts,'founder_acceptance':False,'identity':'Seat identity must be supplied and authenticated outside this unsigned local receipt.'}
 write(out/'RECEIPT.json',receipt);write(out/'PROGRESS.json',{'done_variants':len(results),'total_variants':18,'status':'COMPLETED','wall_s':time.monotonic()-START});print(json.dumps({'status':receipt['status'],'variants':len(results),'out':str(out)}))
except Exception as e:
 print(json.dumps({'status':'HOLD','reason':type(e).__name__+':'+str(e),'elapsed_s':time.monotonic()-START}));sys.exit(2)
