#!/usr/bin/python3
"""JUPI monochrome Gothic architecture: deterministic ASCII, PNG, SVG and film."""
import argparse
from datetime import datetime,timezone
import hashlib
import html
import json
import math
import os
from pathlib import Path
import random
import socket
import subprocess
import sys
import uuid

STATE=Path('/var/lib/jupi-agent/artwork')
FONT=Path('/usr/share/fonts/TTF/DejaVuSansMono-Bold.ttf')
FALLBACK_FONT=Path('/usr/share/fonts/Adwaita/AdwaitaMono-Bold.ttf')
SCENES=('facade','nave')
STYLES=('engraving','nocturne','ruins')


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()


def parameters(scene='facade',style='engraving',width=121,height=65,seed=14,paper='black',title='JUPI',video=False):
    if scene not in SCENES or style not in STYLES or paper not in ('black','white'):raise ValueError('Unknown art recipe')
    if type(width) is not int or not 81<=width<=241 or type(height) is not int or not 41<=height<=121:raise ValueError('Canvas bound is 81..241 columns, 41..121 rows')
    if type(seed) is not int or not 0<=seed<2**32:raise ValueError('Seed must be uint32')
    if type(video) is not bool:raise ValueError('Video flag must be boolean')
    if not isinstance(title,str) or not 1<=len(title)<=32 or any(not 32<=ord(c)<=126 for c in title):raise ValueError('Title must contain 1..32 printable ASCII characters')
    return dict(scene=scene,style=style,width=width,height=height,seed=seed,paper=paper,title=title,video=video)


class Canvas:
    def __init__(self,width,height):
        self.w,self.h=width,height
        self.cells=[[' ']*width for _ in range(height)]
        self.level=[[-1]*width for _ in range(height)]

    def put(self,x,y,char,level=5):
        x,y=round(x),round(y)
        if 0<=x<self.w and 0<=y<self.h and level>=self.level[y][x]:
            old=self.cells[y][x]
            if level==self.level[y][x] and {old,char}=={'|','_'}:char='+'
            self.cells[y][x]=char;self.level[y][x]=level

    def line(self,x0,y0,x1,y1,char=None,level=5):
        dx,dy=x1-x0,y1-y0
        if char is None:
            char='|' if abs(dx)<abs(dy)*0.35 else '_' if abs(dy)<abs(dx)*0.35 else '\\' if dx*dy>0 else '/'
        steps=max(1,math.ceil(max(abs(dx),abs(dy))))
        for i in range(steps+1):
            t=i/steps;self.put(x0+dx*t,y0+dy*t,char,level)

    def poly(self,points,char=' ',level=3):
        for y in range(max(0,math.floor(min(p[1] for p in points))),min(self.h-1,math.ceil(max(p[1] for p in points)))+1):
            intersections=[]
            for (x0,y0),(x1,y1) in zip(points,points[1:]+points[:1]):
                if min(y0,y1)<=y+0.1<max(y0,y1):intersections.append(x0+(y+0.1-y0)*(x1-x0)/(y1-y0))
            intersections.sort()
            for left,right in zip(intersections[::2],intersections[1::2]):
                for x in range(math.ceil(left),math.floor(right)+1):self.put(x,y,char,level)

    def rect(self,x0,y0,x1,y1,rng,style):
        density={'engraving':0.10,'nocturne':0.04,'ruins':0.18}[style]
        for y in range(round(y0),round(y1)+1):
            for x in range(round(x0),round(x1)+1):
                char='.' if rng.random()<density else ' '
                if style=='ruins' and y%4==0 and (x+y//4)%9<3:char='_'
                self.put(x,y,char,1)
        for a,b,c,d in [(x0,y0,x1,y0),(x0,y1,x1,y1),(x0,y0,x0,y1),(x1,y0,x1,y1)]:self.line(a,b,c,d)

    def arch(self,cx,top,half,rise,legs=0,tracery=True,level=6):
        left=[]
        for i in range(33):
            t=i/32
            left.append(((1-t)**2*(cx-half)+2*t*(1-t)*(cx-half)+t*t*cx,
                         (1-t)**2*(top+rise)+2*t*(1-t)*(top+rise*0.72)+t*t*top))
        right=[(2*cx-x,y) for x,y in left]
        self.poly([(cx-half,top+rise+legs),*left,*reversed(right),(cx+half,top+rise+legs)],' ',3)
        for side in (left,right):
            for a,b in zip(side,side[1:]):self.line(*a,*b,level=level)
        self.line(cx-half,top+rise,cx-half,top+rise+legs,level=level)
        self.line(cx+half,top+rise,cx+half,top+rise+legs,level=level)
        self.line(cx-half,top+rise+legs,cx+half,top+rise+legs,'_',level)
        self.put(cx,top,'^',level+1)
        if tracery and half>=2:
            self.line(cx,top+rise*0.42,cx,top+rise+legs,':',level)
            self.line(cx-half+1,top+rise*0.8,cx+half-1,top+rise*0.8,'-',level)

    def rose(self,cx,cy,rx,ry,level=7):
        points=[(cx+rx*math.cos(i*math.tau/96),cy+ry*math.sin(i*math.tau/96)) for i in range(96)]
        self.poly(points,' ',level-3)
        for scale,char in [(1,'o'),(0.82,'.'),(0.45,'o')]:
            ring=[(cx+rx*scale*math.cos(i*math.tau/96),cy+ry*scale*math.sin(i*math.tau/96)) for i in range(97)]
            for a,b in zip(ring,ring[1:]):self.line(*a,*b,char,level)
        for i in range(12):
            angle=i*math.tau/12
            self.line(cx+rx*0.15*math.cos(angle),cy+ry*0.15*math.sin(angle),cx+rx*0.8*math.cos(angle),cy+ry*0.8*math.sin(angle),level=level)
        self.put(cx,cy,'@',level+2)

    def text(self,x,y,value):
        for i,c in enumerate(value):self.put(x+i,y,c,10)

    def result(self):return '\n'.join(''.join(row) for row in self.cells)+'\n'


def facade(p):
    w,h=p['width'],p['height'];g=Canvas(w,h);rng=random.Random(p['seed']);cx=(w-1)/2;floor=h-9
    for y in range(1,round(h*0.54)):
        for x in range(2,w-2):
            if rng.random()<0.003:g.put(x,y,'.' if rng.random()<0.7 else '*',0)
    g.text(3,4,'  .- .');g.text(3,5,' (  . )');g.text(3,6,"  '- '")
    bodyhalf=round(w*0.32);bodytop=round(h*0.43)
    g.rect(cx-bodyhalf,bodytop,cx+bodyhalf,floor,rng,p['style'])
    towerhalf=round(w*0.067);offset=round(w*0.25);towertop=round(h*0.27)
    for sign in (-1,1):
        tx=cx+sign*offset
        g.rect(tx-towerhalf,towertop,tx+towerhalf,floor,rng,p['style'])
        for edge in (-1,1):
            ex=tx+edge*towerhalf
            g.line(ex,towertop,ex,towertop-3,'|',6);g.put(ex,towertop-4,'^',8)
        tip=max(3,towertop-round(h*0.22))
        g.poly([(tx-towerhalf,towertop),(tx,tip),(tx+towerhalf,towertop)],' ',2)
        g.line(tx-towerhalf,towertop,tx,tip,level=6);g.line(tx,tip,tx+towerhalf,towertop,level=6)
        g.line(tx,tip+1,tx,towertop,'|',5);g.put(tx,tip,'^',8)
        g.line(tx,tip-3,tx,tip-1,'|',7);g.line(tx-1,tip-2,tx+1,tip-2,'-',7);g.put(tx,tip-2,'+',8)
        for fraction in (0.34,0.51,0.68):
            top=round(h*fraction)
            for side in (-1,1):g.arch(tx+side*max(2,towerhalf//2),top,max(2,towerhalf//3),max(3,round(h*0.055)),max(2,round(h*0.03)))
        for y in (round(h*0.47),round(h*0.64),floor-1):g.line(tx-towerhalf,y,tx+towerhalf,y,'=',6)
        g.line(tx-towerhalf+1,towertop+1,tx-towerhalf+1,floor,'|',5)
        g.line(tx+towerhalf-1,towertop+1,tx+towerhalf-1,floor,'|',5)
    middlehalf=round(w*0.16);gabletop=round(h*0.19);eaves=round(h*0.39)
    g.poly([(cx-middlehalf,eaves),(cx,gabletop),(cx+middlehalf,eaves)],' ',2)
    g.line(cx-middlehalf,eaves,cx,gabletop,level=6);g.line(cx,gabletop,cx+middlehalf,eaves,level=6)
    g.line(cx-middlehalf,eaves+1,cx,gabletop+2,level=5);g.line(cx,gabletop+2,cx+middlehalf,eaves+1,level=5)
    g.put(cx,gabletop,'^',8);g.line(cx,gabletop-3,cx,gabletop-1,'|',6);g.put(cx,gabletop-2,'+',8)
    for sign in (-1,0,1):g.arch(cx+sign*round(w*0.043),round(h*(0.28 if sign else 0.255)),max(2,round(w*0.019)),max(3,round(h*0.06)),1)
    g.rose(cx,round(h*0.48),max(5,round(w*0.085)),max(3,round(h*0.075)))
    g.line(cx-middlehalf,round(h*0.59),cx+middlehalf,round(h*0.59),'=',6)
    for sign in (-1,0,1):
        dx=cx+sign*round(w*0.1);top=round(h*0.66) if sign else round(h*0.63)
        half=max(3,round(w*(0.035 if sign else 0.043)));rise=max(4,round(h*0.1))
        g.arch(dx,top,half+1,rise,max(1,floor-top-rise),False,5)
        g.arch(dx,top+1,half-1,rise-1,max(1,floor-top-rise),True,7)
        g.line(dx,top+rise,dx,floor,'|',7)
        g.put(dx-1,floor-2,'o',8);g.put(dx+1,floor-2,'o',8)
    for sign in (-1,1):
        inner=cx+sign*round(w*0.32);outer=cx+sign*round(w*0.43)
        g.rect(outer-1,floor-round(h*0.23),outer+1,floor,rng,p['style'])
        g.put(outer,floor-round(h*0.23)-2,'^',7)
        for shift in (0,2):
            start=(inner,round(h*0.47)+shift);control=(outer,round(h*0.47)+shift+1);end=(outer,floor-round(h*0.12)+shift)
            previous=start
            for i in range(1,25):
                t=i/24;current=((1-t)**2*start[0]+2*t*(1-t)*control[0]+t*t*end[0],(1-t)**2*start[1]+2*t*(1-t)*control[1]+t*t*end[1]);g.line(*previous,*current,level=5);previous=current
    for i in range(4):
        spread=bodyhalf+3+i*3;y=floor+1+i
        g.line(cx-spread,y,cx+spread,y,'=',5)
        g.put(cx-spread,y,'/',7);g.put(cx+spread,y,'\\',7)
    g.line(cx-7,floor+5,cx-22,h-3,'/',4);g.line(cx+7,floor+5,cx+22,h-3,'\\',4)
    for sign in (-1,1):
        for i in range(3):
            x=round(cx+sign*(bodyhalf+6+i*4));y=floor+2+(i%2)
            g.put(x,y-2,'+',4);g.line(x,y-1,x,y+1,'|',4);g.line(x-1,y+1,x+1,y+1,'_',4)
    title='-=[ '+p['title']+' ]=-';g.text((w-len(title))//2,h-1,title)
    return g.result()


def nave(p):
    w,h=p['width'],p['height'];g=Canvas(w,h);rng=random.Random(p['seed']);cx=(w-1)/2;vanish=round(h*0.58);floor=h-6
    for x in range(w):
        for y in range(h-2):
            if rng.random()<({'engraving':0.012,'nocturne':0.004,'ruins':0.035}[p['style']]):g.put(x,y,'.',0)
    for i in range(6):
        scale=0.68**i;half=(w*0.46)*scale;top=2+(vanish-2)*(1-scale);base=vanish+(floor-vanish)*scale
        rise=(vanish-top)*0.95;legs=base-top-rise
        g.arch(cx,top,half,rise,legs,False,5+i)
        for sign in (-1,1):
            x=cx+sign*half
            g.line(x,top+rise,x,base,'|',7)
            g.line(x+sign*2,top+rise,x+sign*2,base,'|',7)
            g.line(x-sign*2,base,x+sign*3,base,'=',8)
            g.line(x,top+rise,cx,top,level=3)
            if i<5:
                nextx=cx+sign*half*0.68;nextbase=vanish+(floor-vanish)*scale*0.68
                g.line(x,base,nextx,nextbase,level=5)
    for x in range(-w,w*2,max(8,w//9)):g.line(cx,vanish,x,floor,'/' if x<cx else '\\',4)
    for j in range(1,7):
        y=vanish+(floor-vanish)*(j/6)**1.8;g.line(0,y,w-1,y,'_',4)
    g.rose(cx,vanish-3,max(3,round(w*0.025)),max(1,round(h*0.025)),level=12)
    g.line(cx,vanish-2,cx,vanish+2,'|',10);g.line(cx-2,vanish,cx+2,vanish,'-',10)
    g.rect(cx-6,vanish+3,cx+6,vanish+5,rng,p['style'])
    for i in range(3):g.line(cx-8-i*2,vanish+6+i,cx+8+i*2,vanish+6+i,'=',8)
    title='-=[ '+p['title']+' : THE VAULT ]=-';g.text((w-len(title))//2,h-1,title)
    return g.result()


def artwork(p):return facade(p) if p['scene']=='facade' else nave(p)


def exports(text,p,directory):
    from PIL import Image,ImageDraw,ImageFont
    fontpath=FONT if FONT.is_file() else FALLBACK_FONT
    font=ImageFont.truetype(str(fontpath),16)
    cellw=math.ceil(font.getlength('M'));cellh=20;pad=20
    width,height=p['width']*cellw+2*pad,p['height']*cellh+2*pad
    dark=p['paper']=='black';image=Image.new('1',(width,height),0 if dark else 1);draw=ImageDraw.Draw(image)
    for row,line in enumerate(text.splitlines()):draw.text((pad,pad+row*cellh),line,font=font,fill=1 if dark else 0)
    image.save(directory/'cathedral.png')
    (directory/'font.ttf').write_bytes(fontpath.read_bytes())
    license_path=Path('/usr/share/licenses/ttf-dejavu/LICENSE')
    if fontpath==FONT and license_path.is_file():(directory/'font-license.txt').write_bytes(license_path.read_bytes())
    fg,bg=('#ffffff','#000000') if dark else ('#000000','#ffffff')
    lines=['<svg xmlns="http://www.w3.org/2000/svg" width="'+str(width)+'" height="'+str(height)+'" viewBox="0 0 '+str(width)+' '+str(height)+'">',f'<rect width="100%" height="100%" fill="{bg}"/>',f'<g fill="{fg}" font-family="DejaVu Sans Mono, monospace" font-size="16" font-weight="bold" xml:space="preserve">']
    for row,line in enumerate(text.splitlines()):lines.append(f'<text x="{pad}" y="{pad+15+row*cellh}" textLength="{len(line)*cellw}" lengthAdjust="spacingAndGlyphs">{html.escape(line)}</text>')
    lines+=['</g>','</svg>'];(directory/'cathedral.svg').write_text('\n'.join(lines)+'\n')
    return {'font':str(fontpath),'font_sha256':sha(fontpath.read_bytes()),'pixels':[width,height],'png_mode':'1','foreground':fg,'background':bg}


def render(p,directory,job_id=None,expected_source=None):
    source=Path(__file__).read_bytes();source_hash=sha(source)
    if expected_source and source_hash!=expected_source:raise ValueError('Queued art renderer changed; submit a new explicit request')
    directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    fd=os.open(directory/'attempt.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as f:f.write(canonical({'parameters':p,'job_id':job_id,'renderer_sha256':source_hash})+b'\n');f.flush();os.fsync(f.fileno())
    text=artwork(p)
    if len(text.splitlines())!=p['height'] or any(len(line)!=p['width'] for line in text.splitlines()) or not text.isascii():raise ValueError('ASCII canvas contract failed')
    (directory/'cathedral.txt').write_text(text,encoding='ascii')
    (directory/'cathedral-windows.txt').write_bytes(text.replace('\n','\r\n').encode('ascii'))
    meta=exports(text,p,directory)
    if p['video']:
        command=['/usr/bin/ffmpeg','-nostdin','-v','error','-n','-threads','2','-framerate','12','-loop','1','-i',str(directory/'cathedral.png'),'-t','4','-an','-sn','-dn','-filter_threads','2','-vf','format=gray,fade=t=in:st=0:d=1,fade=t=out:st=3:d=1,format=yuv420p','-c:v','libx264','-threads','2','-preset','veryfast','-crf','18','-movflags','+faststart',str(directory/'cathedral.mp4')]
        result=subprocess.run(command,capture_output=True,timeout=55)
        if result.returncode:raise RuntimeError('FFmpeg export failed: '+result.stderr.decode(errors='replace')[-300:])
        meta['video']=json.loads(subprocess.check_output(['/usr/bin/ffprobe','-v','error','-show_entries','stream=codec_name,pix_fmt,width,height,duration,nb_frames','-of','json',str(directory/'cathedral.mp4')],text=True,timeout=10))
    (directory/'renderer.py').write_bytes(source)
    receipt={'schema':'jupi.art.receipt.v1','utc':datetime.now(timezone.utc).isoformat(),'job_id':job_id,'parameters':p,'renderer_sha256':source_hash,'exports':meta,'classification':'procedural artwork; not a sensor observation','artifacts':{f.name:sha(f.read_bytes()) for f in directory.iterdir() if f.is_file() and f.name!='receipt.json'}}
    with (directory/'receipt.json').open('x') as f:f.write(json.dumps(receipt,indent=2)+'\n');f.flush();os.fsync(f.fileno())
    if directory.parent==STATE:
        STATE.mkdir(mode=0o700,parents=True,exist_ok=True)
        temporary=STATE/('.latest-'+str(uuid.uuid4())+'.json');temporary.write_bytes(canonical({'directory':str(directory),'request_id':directory.name,'job_id':job_id,'receipt_sha256':sha((directory/'receipt.json').read_bytes()),'scene':p['scene'],'style':p['style'],'width':p['width'],'height':p['height'],'seed':p['seed'],'classification':'procedural artwork'})+b'\n');os.replace(temporary,STATE/'latest.json')
    return {'directory':str(directory),'text':str(directory/'cathedral.txt'),'png':str(directory/'cathedral.png'),'svg':str(directory/'cathedral.svg'),'video':str(directory/'cathedral.mp4') if p['video'] else None,'receipt_sha256':sha((directory/'receipt.json').read_bytes())}


def agent(request):
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as c:
        c.settimeout(20);c.connect('/run/jupi-agent/control.sock');c.sendall(canonical(request)+b'\n')
        with c.makefile('rb') as f:r=json.loads(f.readline(131072))
    if not r.get('ok'):raise ValueError(r.get('error','Agent request failed'))
    return r['result']


def main():
    os.umask(0o077);parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('cathedral','preview','verify'))
    parser.add_argument('--scene',choices=SCENES,default='facade');parser.add_argument('--style',choices=STYLES,default='engraving')
    parser.add_argument('--width',type=int,default=121);parser.add_argument('--height',type=int,default=65);parser.add_argument('--seed',type=int,default=14)
    parser.add_argument('--paper',choices=('black','white'),default='black');parser.add_argument('--title',default='JUPI');parser.add_argument('--video',action='store_true')
    parser.add_argument('--output');parser.add_argument('--enqueue',action='store_true');parser.add_argument('--request-id');parser.add_argument('--job-id');parser.add_argument('--expected-source')
    args=parser.parse_args()
    if args.command=='preview':
        if args.output:directory=Path(args.output)
        else:directory=Path(json.loads((STATE/'latest.json').read_text())['directory'])
        print((directory/'cathedral.txt').read_text(),end='');return 0
    if args.command=='verify':
        directory=Path(args.output) if args.output else Path(json.loads((STATE/'latest.json').read_text())['directory'])
        receipt=json.loads((directory/'receipt.json').read_text())
        for name,digest in receipt['artifacts'].items():
            if Path(name).name!=name or (directory/name).is_symlink() or sha((directory/name).read_bytes())!=digest:raise ValueError('Art artifact hash differs')
        print(json.dumps({'directory':str(directory),'artifacts_verified':len(receipt['artifacts'])}));return 0
    p=parameters(args.scene,args.style,args.width,args.height,args.seed,args.paper,args.title,args.video)
    if args.enqueue:
        identifier=args.request_id or str(uuid.uuid4())
        try:result=agent({'action':'art','request_id':identifier,**p})
        except Exception as error:
            print(json.dumps({'request_id':identifier,'state':'enqueue_unconfirmed','error_class':type(error).__name__,'parameters':p,'reconcile':'Repeat the same recipe with --enqueue --request-id '+identifier},indent=2));return 1
        print(json.dumps(result,indent=2));return 0
    directory=Path(args.output).resolve() if args.output else STATE/str(uuid.uuid4())
    result=render(p,directory,args.job_id,args.expected_source);print(json.dumps(result,indent=2));return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'error_class':type(error).__name__,'error':str(error)[:300]}),file=sys.stderr);raise SystemExit(1)
