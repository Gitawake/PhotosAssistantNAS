"""Private media decoder and shared helpers. No HTTP login or session storage."""
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import math
import shutil
import time

FREE_HEADROOM=4*1024**3
MAX_OUTPUT_BYTES=16*1024**3

def require_space(work, needed=0):
    if shutil.disk_usage(work).free < FREE_HEADROOM+needed:
        raise RuntimeError('Insufficient free space')

def video_budget(duration):
    if not math.isfinite(duration) or duration<=0 or duration>21600:
        raise ValueError('Unsupported video duration')
    # Two output copies during publication, bitrate allowance plus scratch.
    return 2*math.ceil(duration*3000000/8)+1024**3

class ApiError(Exception):
    def __init__(self, code):
        self.code=code
        super().__init__('Photos API error %s' % code)

class Decoder:
    def __init__(self, runtime): self.runtime=Path(runtime)
    def env(self, name, work):
        base=self.runtime/name
        env={'PATH':'/usr/bin:/bin','LANG':'C','HOME':str(work),'TMPDIR':str(work),
             'LD_LIBRARY_PATH':str(base/'lib'),'OMP_NUM_THREADS':'2'}
        if name=='ffmpeg': env['LD_LIBRARY_PATH']+=':'+str(self.runtime/'videodriver/lib')
        else:
            env.update(MAGICK_HOME=str(base),MAGICK_CONFIGURE_PATH=str(base/'etc/ImageMagick-7'),
                MAGICK_CODER_MODULE_PATH=str(base/'lib/ImageMagick-7.1.2/modules-Q16HDRI/coders'),
                MAGICK_TEMPORARY_PATH=str(work),MAGICK_THREAD_LIMIT='2',MAGICK_MEMORY_LIMIT='256MiB',MAGICK_MAP_LIMIT='512MiB')
        return env
    def run(self, name, executable, args, work, timeout=180):
        process=subprocess.Popen([str(self.runtime/name/'bin'/executable),*map(str,args)],
            env=self.env(name,work),stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            pass_fds=((self.source_fd,) if name=='ffmpeg' and hasattr(self,'source_fd') else ()),
            start_new_session=not getattr(self,'nested',False))
        try:
            deadline=time.monotonic()+timeout
            while True:
                require_space(work)
                remaining=deadline-time.monotonic()
                if remaining<=0: raise subprocess.TimeoutExpired(executable,timeout)
                try:
                    out,err=process.communicate(timeout=min(5,remaining))
                    break
                except subprocess.TimeoutExpired:
                    if time.monotonic()>=deadline: raise
            require_space(work)
        except BaseException:
            (process.kill() if getattr(self,'nested',False) else os.killpg(process.pid,signal.SIGKILL));process.wait();raise
        if process.returncode: raise RuntimeError('%s failed (%s)' % (executable,process.returncode))
        return out
    def audit(self, work):
        for name,exe in [('imagemagick','magick'),('ffmpeg','ffmpeg'),('ffmpeg','ffprobe')]:
            env=self.env(name,work)
            result=subprocess.run(['/lib64/ld-linux-x86-64.so.2','--library-path',env['LD_LIBRARY_PATH'],
                '--list',str(self.runtime/name/'bin'/exe)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
            if result.returncode: raise RuntimeError('Private runtime dependency missing: '+exe)
            for line in result.stdout.decode(errors='replace').splitlines():
                if '/var/packages/' in line and str(self.runtime) not in line:
                    raise RuntimeError('Runtime resolves another package library')
    def input_args(self, source):
        if source=='fd:':
            os.lseek(self.source_fd,0,os.SEEK_SET)
            return ['-fd',str(self.source_fd),'-protocol_whitelist','fd','-i','fd:']
        return ['-protocol_whitelist','file,pipe','-i',source]

    def generate(self, source, ext, work):
        input_path=str(source)+'[0]'
        if ext in ('.mov','.mp4','.m4v','.3g2','.3gp','.asf','.avi','.divx','.mpeg','.mpg','.mts','.m2t','.m2ts','.qt','.wmv','.xvid'):
            probe=json.loads(self.run('ffmpeg','ffprobe',['-v','error','-select_streams','v:0',
                '-show_entries','stream=codec_name,color_transfer','-of','json',*self.input_args(source)],work))
            streams=probe.get('streams',[])
            if not streams: raise ValueError('No video stream')
            frame=work/'frame.jpg'
            args=['-nostdin','-threads','2','-v','error','-y','-hwaccel','none','-ss','0',*self.input_args(source),'-frames:v','1']
            if streams[0].get('color_transfer') in ('arib-std-b67','smpte2084'):
                args+=['-vf','zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p']
            self.run('ffmpeg','ffmpeg',args+[frame],work);input_path=str(frame)
        outputs={}
        for label,size in [('SM',240),('M',320),('XL',1280)]:
            dest=work/(label+'.jpg')
            self.run('imagemagick','convert',[input_path,'-auto-orient','-thumbnail',f'{size}x{size}^>',
                '-quality','85',dest],work)
            outputs[label]=dest
        return outputs

    def compatible_video(self, source, work):
        """Conservative cross-device SDR MP4 baseline; container alone is insufficient."""
        probe=json.loads(self.run('ffmpeg','ffprobe',['-v','error','-show_streams',
            '-show_format','-of','json',*self.input_args(source)],work))
        videos=[s for s in probe.get('streams',[]) if s.get('codec_type')=='video'
                and not s.get('disposition',{}).get('attached_pic')]
        audio=[s for s in probe.get('streams',[]) if s.get('codec_type')=='audio']
        if not videos: raise ValueError('No video stream')
        v=videos[0]
        return (v.get('codec_name')=='h264' and v.get('pix_fmt')=='yuv420p'
                and v.get('color_transfer') not in ('arib-std-b67','smpte2084')
                and int(v.get('level',999))<=51
                and max(int(v.get('width',0)),int(v.get('height',0)))<=1920
                and all(a.get('codec_name')=='aac' and a.get('profile')=='LC'
                        and int(a.get('channels',99))<=2 for a in audio)
                and Path(source).suffix.lower() in ('.mp4','.m4v'))

    def transcode(self, source, work):
        probe=json.loads(self.run('ffmpeg','ffprobe',['-v','error','-select_streams','v:0',
            '-show_entries','stream=color_transfer:format=duration','-of','json',*self.input_args(source)],work))
        duration=float(probe.get('format',{}).get('duration',0))
        require_space(work,video_budget(duration))
        filters=[]
        if probe.get('streams',[{}])[0].get('color_transfer') in ('arib-std-b67','smpte2084'):
            filters.append('zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv')
        # Landscape <=1280x720, portrait <=720x1280; never upscale.
        filters+=['scale=w=\'if(gte(iw,ih),min(iw,1280),min(iw,720))\':h=\'if(gte(iw,ih),min(ih,720),min(ih,1280))\':force_original_aspect_ratio=decrease:force_divisible_by=2',
                  'setsar=1','format=yuv420p']
        dest=work/'compatible.mp4'
        self.run('ffmpeg','ffmpeg',['-nostdin','-v','error','-y','-hwaccel','none',
            '-threads','2',*self.input_args(source),'-map','0:v:0','-map','0:a:0?',
            '-map_metadata','-1','-map_chapters','-1','-vf',','.join(filters),
            '-c:v','libx264','-preset','veryfast','-crf','23','-maxrate','2500k','-bufsize','5000k',
            '-threads','2','-filter_threads','1','-pix_fmt','yuv420p','-fpsmax','30',
            '-c:a','aac','-b:a','128k','-ac','2','-movflags','+faststart',dest],work,timeout=21600)
        if not self.compatible_video(dest,work): raise ValueError('Generated video failed compatibility check')
        result=json.loads(self.run('ffmpeg','ffprobe',['-v','error','-show_entries','format=duration','-of','json',dest],work))
        actual=float(result.get('format',{}).get('duration',0))
        if abs(actual-duration)>max(2,duration*0.02): raise ValueError('Incomplete transcoded video')
        return dest

def atomic_json(path, data):
    path=Path(path);path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(prefix='.state-',dir=str(path.parent))
    try:
        with os.fdopen(fd,'w') as f: json.dump(data,f)
        os.chmod(temp,0o600);os.replace(temp,path)
    finally:
        if os.path.exists(temp): os.unlink(temp)

def assert_photos_version():
    metadata=Path('/var/packages/SynologyPhotos/INFO').read_text()
    if 'version="1.9.1-10928"' not in metadata.splitlines():
        raise RuntimeError('Photos version changed; validate before resuming')
