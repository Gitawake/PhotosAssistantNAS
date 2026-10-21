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
import sys

FREE_HEADROOM=4*1024**3
MAX_OUTPUT_BYTES=16*1024**3

def require_space(work, needed=0):
    if shutil.disk_usage(work).free < FREE_HEADROOM+needed:
        raise RuntimeError('Insufficient free space')

def video_budget(duration):
    if not math.isfinite(duration) or duration<=0 or duration>21600:
        raise ValueError('Unsupported video duration')
    # Decoder output, publication staging and Photos final copy, plus scratch.
    return 3*math.ceil(duration*3000000/8)+1024**3

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
        if name=='ffmpeg':
            env['LD_LIBRARY_PATH']+=':'+str(self.runtime/'videodriver/lib')
            if getattr(self,'hardware',None):
                if self.hardware.get('driver'):
                    driver_path=self.hardware.get('driver_path') or str(self.runtime/'videodriver/lib')
                    env.update(LIBVA_DRIVERS_PATH=driver_path,LIBVA_DRIVER_NAME=self.hardware['driver'])
                    env['LD_LIBRARY_PATH']+=':'+driver_path+':'+str(Path(driver_path).parent)
        else:
            env.update(MAGICK_HOME=str(base),MAGICK_CONFIGURE_PATH=str(base/'etc/ImageMagick-7'),
                MAGICK_CODER_MODULE_PATH=str(base/'lib/ImageMagick-7.1.2/modules-Q16HDRI/coders'),
                MAGICK_TEMPORARY_PATH=str(work),MAGICK_THREAD_LIMIT='2',MAGICK_MEMORY_LIMIT='256MiB',MAGICK_MAP_LIMIT='512MiB')
        return env
    def run(self, name, executable, args, work, timeout=180):
        if name=='heic':
            command=[sys.executable,'-I',str(Path(__file__).with_name('heic_fd.py')),*map(str,args)]
            env=self.env('imagemagick',work)
            # MagickWand's pinned jemalloc needs startup TLS, before Python dlopen.
            # This private allocator is preloaded only in this isolated helper.
            env['LD_PRELOAD']=str(self.runtime/'imagemagick/lib/libjemalloc.so.2')
        else:
            command=[str(self.runtime/name/'bin'/executable),*map(str,args)]
            env=self.env(name,work)
        process=subprocess.Popen(command,
            env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            pass_fds=((self.source_fd,) if name in ('ffmpeg','heic') and hasattr(self,'source_fd') else ()),
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
        if process.returncode: raise subprocess.CalledProcessError(process.returncode,executable)
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
        if ext in ('.heic','.heif','.hif'):
            if source!='fd:' or not hasattr(self,'source_fd'):
                raise ValueError('HEIF requires a read-only original descriptor')
            self.run('heic','heic_fd',[self.source_fd,work,*getattr(self,'expected_size',(0,0))],work)
            return {label:work/(label+'.jpg') for label in ('SM','M','XL')}
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

    def compatible_video(self, source, work, source_ext=None):
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
                and (source_ext or Path(source).suffix).lower() in ('.mp4','.m4v')
                and 'mp4' in probe.get('format',{}).get('format_name','').split(','))

    def transcode(self, source, work):
        probe=json.loads(self.run('ffmpeg','ffprobe',['-v','error','-select_streams','v:0',
            '-show_entries','stream=codec_name,pix_fmt,color_transfer,color_range:stream_side_data=rotation:format=duration','-of','json',*self.input_args(source)],work))
        duration=float(probe.get('format',{}).get('duration',0))
        require_space(work,video_budget(duration))
        if getattr(self,'hardware',None):
            initial=self.hardware
            candidates=[initial]+[dict(initial,driver=name) for name in initial.get('driver_fallbacks',[])]
            for candidate in candidates:
                self.hardware=candidate
                try:
                    result=self._transcode_once(source,work,probe,True)
                    print('VIDEO_BACKEND='+candidate.get('backend','vaapi'),flush=True)
                    if candidate.get('driver'): print('VIDEO_DRIVER='+candidate['driver'],flush=True)
                    return result
                except (subprocess.CalledProcessError,subprocess.TimeoutExpired,ValueError,OSError):
                    partial=work/'compatible.mp4'
                    if partial.exists(): partial.unlink()
            self.hardware=initial
            print('HARDWARE_FALLBACK=software',flush=True)
        result=self._transcode_once(source,work,probe,False)
        print('VIDEO_BACKEND=software',flush=True)
        return result

    def _transcode_once(self,source,work,probe,accelerated):
        duration=float(probe['format']['duration'])
        filters=[]
        gpu_scaling=False
        device_args=[];decode_args=['-hwaccel','none']
        stream=probe.get('streams',[{}])[0]
        if accelerated:
            backend=self.hardware.get('backend','vaapi')
            if backend=='vaapi':
                device_args=['-init_hw_device','vaapi=gpu:'+self.hardware['device'],'-filter_hw_device','gpu']
                decode_device='gpu'
            elif backend=='qsv':
                device_args=['-init_hw_device','vaapi=render:'+self.hardware['device'],'-init_hw_device','qsv=gpu@render','-filter_hw_device','gpu']
                decode_device='render'
            elif backend=='nvenc':
                device_args=['-init_hw_device','cuda=gpu:'+self.hardware['device'],'-filter_hw_device','gpu']
                decode_device='gpu'
            else: raise ValueError('Unsupported acceleration backend')
            if stream.get('codec_name') in ('h264','hevc','vp9','av1','mpeg2video') and stream.get('pix_fmt') in ('yuv420p','yuvj420p','yuv420p10le'):
                accel={'nvenc':'cuda','qsv':'qsv','vaapi':'vaapi'}[backend]
                if backend=='qsv': decode_device='gpu'
                decode_args=['-hwaccel',accel,'-hwaccel_device',decode_device,'-hwaccel_output_format',accel]
                filters=['hwdownload','format='+('p010le' if stream.get('pix_fmt')=='yuv420p10le' else 'nv12')]
                rotated=any(x.get('rotation',0)%360 for x in stream.get('side_data_list',[]))
                gpu_scaling=(backend in ('vaapi','qsv') and not rotated
                    and stream.get('color_transfer') not in ('arib-std-b67','smpte2084')
                    and stream.get('color_range')!='pc' and stream.get('pix_fmt')!='yuvj420p')
        if probe.get('streams',[{}])[0].get('color_transfer') in ('arib-std-b67','smpte2084'):
            filters.append('zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv')
        # Landscape <=1280x720, portrait <=720x1280; never upscale.
        filters+=['scale=w=\'if(gte(iw,ih),min(iw,1280),min(iw,720))\':h=\'if(gte(iw,ih),min(ih,720),min(ih,1280))\':force_original_aspect_ratio=decrease:force_divisible_by=2:in_range=auto:out_range=tv',
                  'setsar=1','format=yuv420p']
        if gpu_scaling:
            if backend=='vaapi':
                scale=filters[-3].replace('scale=','scale_vaapi=',1).replace(':in_range=auto','')
                filters=[scale+':format=nv12:reset_sar=1','setparams=range=limited']
            else:
                factor='if(gte(iw,ih),min(1,min(1280/iw,720/ih)),min(1,min(720/iw,1280/ih)))'
                filters=["scale_qsv=w='max(2,trunc(iw*("+factor+")/2)*2)':h='max(2,trunc(ih*("+factor+")/2)*2)':format=nv12",'setsar=1']
        dest=work/'compatible.mp4'
        encoder_args=['-c:v','libx264','-preset','veryfast','-crf','23','-pix_fmt','yuv420p']
        if accelerated:
            if not gpu_scaling: filters+=['format=nv12','hwupload']
            encoder={'vaapi':'h264_vaapi','qsv':'h264_qsv','nvenc':'h264_nvenc'}[backend]
            encoder_args=['-c:v',encoder,'-b:v','2500k']
        self.run('ffmpeg','ffmpeg',['-nostdin','-v','error','-y',*device_args,
            '-threads','2',*decode_args,*self.input_args(source),'-map','0:v:0','-map','0:a:0?',
            '-map_metadata','-1','-map_chapters','-1','-vf',','.join(filters),
            *encoder_args,'-maxrate','2500k','-bufsize','5000k',
            '-threads','2','-filter_threads','1','-color_range','tv','-fpsmax','30',
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
