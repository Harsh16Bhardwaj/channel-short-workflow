"""Config-driven local shorts renderer. One video encode; cropped sky effects.

Input assets and reviews are real run files. This does not generate artwork,
perform an audio audition, or imply owner approval.
"""
from pathlib import Path
import argparse,hashlib,json,math,re,subprocess,textwrap,time
from PIL import Image,ImageChops,ImageDraw,ImageFilter,ImageOps
import numpy as np
import imageio_ffmpeg

ROOT=Path(__file__).resolve().parents[2]
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def project(p):
    p=(ROOT/p).resolve();p.relative_to(ROOT);return p
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def clock(t,ass=False):
    if ass:
        n=round(t*100);return f'{n//360000}:{n//6000%60:02}:{n//100%60:02}.{n%100:02}'
    n=round(t*1000);return f'{n//3600000:02}:{n//60000%60:02}:{n//1000%60:02},{n%1000:03}'

def subtitles(board,lines,out,font='Nirmala UI'):
    cues=[]
    for s in board['shots']:
        parts=[]
        for lid in s['narration_line_ids']:
            line=next(l for l in lines if l['id']==lid)
            for sentence in re.split(r'(?<=[।!?])\s+',line['text']):
                words=sentence.split();n=max(1,math.ceil(len(sentence)/85))
                for k in range(n):
                    part=words[round(k*len(words)/n):round((k+1)*len(words)/n)]
                    if part:parts.append((' '.join(part),lid))
        span=(s['end_ms']-s['start_ms'])/1000;t=s['start_ms']/1000
        minimum=min(2.,span/len(parts));extra=span-minimum*len(parts)
        words=sum(len(p.split()) for p,_ in parts)
        for k,(text,lid) in enumerate(parts):
            end=s['end_ms']/1000 if k==len(parts)-1 else t+minimum+extra*len(text.split())/words
            cues.append(dict(start=t,end=end,text=text,line_id=lid,shot_id=s['id']));t=end
    assert ' '.join(c['text'] for c in cues).split()==' '.join(l['text'] for l in lines).split()
    assert min(c['end']-c['start'] for c in cues)>=2,'Caption allocation too short; adjust planned timing'
    write(out/'caption-cues.json',cues)
    (out/'subtitles-hi.srt').write_text('\n\n'.join(f"{i+1}\n{clock(c['start'])} --> {clock(c['end'])}\n{c['text']}" for i,c in enumerate(cues))+'\n',encoding='utf-8-sig')
    ass='''[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280
WrapStyle: 0
[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Main,Nirmala UI,34,&H00FFFFFF,&H00FFFFFF,&H00212A2A,&HA0000000,0,0,0,0,100,100,0,0,3,1,0,2,34,34,80,1
Style: Symbol,Nirmala UI,22,&H00D7E8EE,&H00D7E8EE,&H00202A2C,&H90000000,0,0,0,0,100,100,0,0,3,1,0,8,25,25,38,1
[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
'''
    ass=ass.replace('Nirmala UI',font)
    for c in cues:
        text='\\N'.join(textwrap.wrap(c['text'],36,break_long_words=False,break_on_hyphens=False))
        ass+=f"Dialogue: 1,{clock(c['start'],True)},{clock(c['end'],True)},Main,,0,0,0,,{text}\n"
    for s in board['shots']:
        if s.get('symbol_label'):
            ass+=f"Dialogue: 2,{clock(s['start_ms']/1000,True)},{clock(s['end_ms']/1000,True)},Symbol,,0,0,0,,{s['symbol_label']}\n"
    (out/'subtitles.ass').write_text(ass,encoding='utf-8-sig')
    return cues

def mask(cfg,size):
    w,h=size;m=Image.new('L',size);d=ImageDraw.Draw(m)
    for box in cfg['effect_zones']:d.rectangle(tuple(round(v*(w if j%2==0 else h)) for j,v in enumerate(box)),fill=255)
    for x0,y0,x1,y1 in cfg['protected_boxes']:
        pad=max(2,round(8*w/720));d.rectangle((round(x0*w)-pad,round(y0*h)-pad,round(x1*w)+pad,round(y1*h)+pad),fill=0)
    d.rectangle((0,round(h*.79),w,h),fill=0)
    return m

class Scene:
    def __init__(self,shot,cfg,file):
        self.s=shot;self.cfg=cfg;self.w,self.h=720,1280
        self.base=ImageOps.fit(Image.open(file).convert('RGB'),(self.w,self.h),method=Image.Resampling.LANCZOS)
        self.full=mask(cfg,(self.w,self.h));self.low=np.asarray(mask(cfg,(270,480)),dtype=np.uint16)
        self.bbox=self.full.getbbox();self.cropped_mask=self.full.crop(self.bbox) if self.bbox else None
    def raw(self,t):
        result=self.base.copy()
        if not self.bbox:return result
        fw,fh=270,480;im=Image.new('RGBA',(fw,fh));d=ImageDraw.Draw(im)
        color=(245,222,167)
        for j in range(9):
            x=((j*.173+t*.031)%1)*fw;y=((j*.217+t*.055)%1)*fh*.79
            r=1.6+(j%3)*.6;a=t*.9+j;dx=math.cos(a)*r;dy=math.sin(a)*r*.65
            d.polygon([(x-dx,y-dy),(x+dy,y-dx),(x+dx,y+dy),(x-dy,y+dx)],fill=(*color,100 if j%2 else 145))
            d.line([(x-dx*.6,y-dy*.6),(x+dx*.6,y+dy*.6)],fill=(255,238,201,110),width=1)
        for j in range(3):
            d.line([(k*fw/25,fh*(.1+j*.12)+5*math.sin(k*.2+t*.7+j)) for k in range(26)],fill=(*color,22),width=1)
        glow=Image.new('RGBA',(fw,fh));g=ImageDraw.Draw(glow);cx=fw*(.77+.025*math.sin(t*.3));cy=fh*.14
        g.ellipse((cx-35,cy-26,cx+35,cy+26),fill=(*color,24));im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(12)))
        alpha=np.asarray(im.getchannel('A'),dtype=np.uint16);im.putalpha(Image.fromarray((alpha*self.low//255).astype('uint8')))
        # Resize/composite only the reviewed sky region, not a full720x1280 plate.
        x0,y0,x1,y1=self.bbox
        plate=im.transform((x1-x0,y1-y0),Image.Transform.EXTENT,(x0*fw/720,y0*fh/1280,x1*fw/720,y1*fh/1280),resample=Image.Resampling.BILINEAR)
        plate.putalpha(ImageChops.multiply(plate.getchannel('A'),self.cropped_mask))
        result.paste(plate,(x0,y0),plate)
        return result
    def frame(self,t):
        c=self.s.get('camera',{});p=max(0,min(1,t/((self.s['end_ms']-self.s['start_ms'])/1000)));p=p*p*(3-2*p)
        interp=lambda key,default:c.get(key,[default,default])[0]*(1-p)+c.get(key,[default,default])[1]*p
        z=interp('zoom',1.025);xx=interp('x',.5);yy=interp('y',.4)
        raw=self.raw(t)
        if z==1:return raw
        cw,ch=720/z,1280/z;x=(720-cw)*xx;y=(1280-ch)*yy
        return raw.resize((720,1280),Image.Resampling.BICUBIC,box=(x,y,x+cw,y+ch))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('job');parser.add_argument('--sheets',action='store_true');args=parser.parse_args()
    jobpath=project(args.job);job=read(jobpath);out=project(job['output_dir']);out.mkdir(parents=True,exist_ok=True)
    b=read(project(job['board_file']));script=read(project(job['script_file']))
    lines=script['lines'] if 'lines'in script else next(v for v in script['variants'] if v['id']==job.get('variant','A'))['lines']
    cfg=read(project(job['masks_file']));scenes=[]
    for s in b['shots']:
        file=project(job['images'][s['id']]);assert cfg['shots'][s['id']]['image_hash']==sha(file)
        actual=dict(s)
        if s['id'] in job.get('camera_overrides',{}):actual['camera']=job['camera_overrides'][s['id']]
        scenes.append(Scene(actual,cfg['shots'][s['id']],file))
    sheet=Image.new('RGB',(960,math.ceil(len(scenes)/4)*460),'#eee5d3');debug=sheet.copy()
    for i,sc in enumerate(scenes):
        x,y=i%4*240,i//4*460;im=sc.base.resize((240,427));sheet.paste(im,(x,y))
        over=Image.new('RGBA',(240,427),(30,230,80));over.putalpha(mask(sc.cfg,(240,427)).point(lambda a:round(a*.38)))
        im=im.convert('RGBA');im.alpha_composite(over);debug.paste(im.convert('RGB'),(x,y))
        for page in [sheet,debug]:ImageDraw.Draw(page).text((x+7,y+433),sc.s['id'],fill='#183b3f')
    sheet.save(out/'composition-sheet.jpg');debug.save(out/'motion-zones.jpg')
    cues=subtitles(b,lines,out,job.get('subtitle_font','Nirmala UI'))
    if args.sheets:return
    reviews=read(project(job['image_review']));assert reviews['verdict']=='PASS'
    assert reviews.get('reviewer') and reviews.get('performed_checks'),'Actual review evidence required'
    assert reviews.get('mask_hash')==sha(project(job['masks_file'])),'Mask review is stale'
    assert reviews['image_hashes']=={s['id']:sha(project(job['images'][s['id']])) for s in b['shots']}
    checks=[]
    for sc in scenes:
        protect=np.zeros((1280,720),bool)
        for x0,y0,x1,y1 in sc.cfg['protected_boxes']:protect[round(y0*1280):round(y1*1280)+1,round(x0*720):round(x1*720)+1]=True
        for t in [0,(sc.s['end_ms']-sc.s['start_ms'])/2000]:assert not np.any(np.asarray(sc.raw(t))[protect]!=np.asarray(sc.base)[protect])
        checks.append(dict(id=sc.s['id'],protected_effect_pixels_changed=0))
    write(out/'preencode-check.json',dict(scope='Producer mask check before common camera; not independent viewing',checks=checks))
    ff=imageio_ffmpeg.get_ffmpeg_exe();duration=b['duration_ms']/1000;fps=24;audio=job['audio']
    quiet_start,quiet_end=audio.get('quiet',[duration,duration])
    quiet=f"if(lt(t,{quiet_start-2}),1,if(lt(t,{quiet_start}),1-0.9*(t-({quiet_start-2}))/2,if(lt(t,{quiet_end}),0.1,if(lt(t,{quiet_end+2}),0.1+0.9*(t-{quiet_end})/2,1))))"
    movie=out/job.get('movie_name','short.mp4')
    command=[ff,'-y','-hide_banner','-loglevel','error','-f','rawvideo','-vcodec','rawvideo','-pix_fmt','rgb24','-s','720x1280','-r','24','-i','pipe:0']
    tracks=[(key,audio.get(key),gain) for key,gain in [('music',audio.get('music_gain',1.8)),('wind',audio.get('wind_gain',.18))]]
    tracks=[track for track in tracks if track[1]]
    filters=[]
    for index,(key,file,gain) in enumerate(tracks,1):
        command+=['-stream_loop','-1','-i',str(project(file))]
        filters.append(f'[{index}:a]atrim=0:{duration},asetpts=PTS-STARTPTS,volume={gain},afade=t=in:d=2,afade=t=out:st={max(0,duration-5)}:d=5[t{index}]')
    if tracks:
        labels=''.join(f'[t{i}]' for i in range(1,len(tracks)+1))
        mix=f'{labels}amix=inputs={len(tracks)}:normalize=0' if len(tracks)>1 else '[t1]anull'
        filters.append(f"{mix},volume='{quiet}':eval=frame[a]")
        command+=['-filter_complex',';'.join(filters)]
    command+=['-vf','ass=subtitles.ass','-map','0:v:0']
    command+=['-map','[a]','-c:a','aac','-b:a','192k','-ar','48000'] if tracks else ['-an']
    command+=['-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-t',str(duration),'-movflags','+faststart',str(movie)]
    start=time.monotonic()
    with (out/'encode-log.txt').open('w',encoding='utf-8') as log:
        proc=subprocess.Popen(command,cwd=out,stdin=subprocess.PIPE,stderr=log)
        try:
            for n in range(round(duration*fps)):
                t=n/fps;sc=next(sc for sc in scenes if sc.s['start_ms']/1000<=t<sc.s['end_ms']/1000)
                proc.stdin.write(sc.frame(t-sc.s['start_ms']/1000).tobytes())
                if n%240==0:print(f'Rendered{n}/{round(duration*fps)} frames',flush=True)
        finally:proc.stdin.close()
        assert proc.wait()==0,'Encoding failed; see encode-log.txt'
    frames,seconds=imageio_ffmpeg.count_frames_and_secs(str(movie));assert frames==round(duration*fps) and abs(seconds-duration)<.05
    (out/'review-frames').mkdir(exist_ok=True)
    for s in b['shots']:
        subprocess.run([ff,'-y','-hide_banner','-loglevel','error','-ss',str((s['start_ms']+s['end_ms'])/2000),'-i',str(movie),'-frames:v','1',str(out/'review-frames'/f"{s['id']}.jpg")],check=True)
    peak=mean=None
    if tracks:
        meter=subprocess.run([ff,'-hide_banner','-i',str(movie),'-vn','-af','volumedetect','-f','null','-'],capture_output=True,text=True,check=True)
        (out/'audio-meter.txt').write_text(meter.stderr,encoding='utf-8')
        peak=float(re.search(r'max_volume:\s*([-\d.]+) dB',meter.stderr).group(1));assert peak<0
        mean=float(re.search(r'mean_volume:\s*([-\d.]+) dB',meter.stderr).group(1))
    write(out/'export.json',dict(frames=frames,duration_seconds=seconds,size=[720,1280],fps=24,sha256=sha(movie),bytes=movie.stat().st_size,render_wall_seconds=round(time.monotonic()-start,2),renderer_hash=sha(__file__),job_hash=sha(jobpath),timing_basis='EST',actual_narration=False,audio_listening='NOT_PERFORMED',integration_calls=0,measured_peak_dbfs=peak,measured_mean_dbfs=mean,caption_cues=len(cues),minimum_caption_seconds=min(c['end']-c['start'] for c in cues)))
    print('Single-pass export and full decode complete.',flush=True)

if __name__=='__main__':main()
