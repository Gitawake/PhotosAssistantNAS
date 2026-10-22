from pathlib import Path
from types import SimpleNamespace
from unittest import mock
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/photos_assistant'))
import hardware
from worker import Decoder

class HardwareTests(unittest.TestCase):
    def hdr_command(self,stream,mapper='tonemapx',valid_tags=True):
        d=Decoder('/runtime');d.hardware={'backend':'vaapi','device':'/dev/dri/renderD128'};d.tone_mapper=mapper
        output={'format':{'duration':'5'},'streams':[{'color_range':'tv','color_space':'bt709','color_transfer':'bt709','color_primaries':'bt709'}]}
        if not valid_tags:output['streams'][0]['color_transfer']='arib-std-b67'
        with tempfile.TemporaryDirectory() as td,mock.patch.object(d,'run',return_value=json.dumps(output)) as run,mock.patch.object(d,'compatible_video',return_value=True),mock.patch('builtins.print'):
            d._transcode_once('source',Path(td),{'format':{'duration':'5'},'streams':[stream]},True)
        return run.call_args_list[0].args[2]

    def test_hdr_cpu_work_is_bounded_after_gpu_rotation_scale_and_frame_reduction(self):
        stream={'codec_name':'hevc','pix_fmt':'yuv420p10le','color_transfer':'arib-std-b67','color_range':'tv','avg_frame_rate':'120/1','side_data_list':[{'rotation':-90}]}
        args=self.hdr_command(stream);vf=args[args.index('-vf')+1]
        order=['fps=30','transpose_vaapi=dir=clock','scale_vaapi=','hwdownload','tonemapx=']
        self.assertEqual(sorted(order,key=vf.index),order)
        self.assertIn('-noautorotate',args);self.assertIn('apply_dovi=0',vf)
        self.assertIn(':format=p010:reset_sar=1',vf);self.assertIn('hwupload',vf)
        self.assertEqual(args[args.index('-color_trc')+1],'bt709')

    def test_full_range_hdr_and_non_quarter_rotation_do_not_enter_vpp_prefilter(self):
        for fields in ({'color_range':'pc'},{'side_data_list':[{'rotation':37}]}):
            stream={'codec_name':'hevc','pix_fmt':'yuv420p10le','color_transfer':'smpte2084','avg_frame_rate':'24000/1001',**fields}
            args=self.hdr_command(stream);vf=args[args.index('-vf')+1]
            self.assertNotIn('scale_vaapi',vf);self.assertNotIn('transpose_vaapi',vf)
            self.assertNotIn('fps=30',vf);self.assertLess(vf.index('scale='),vf.index('tonemapx='))

    def test_hdr_legacy_filter_still_receives_bounded_resolution(self):
        args=self.hdr_command({'codec_name':'hevc','pix_fmt':'yuv420p10le','color_transfer':'smpte2084'},mapper='legacy')
        vf=args[args.index('-vf')+1]
        self.assertLess(vf.index('scale_vaapi='),vf.index('zscale='));self.assertNotIn('tonemapx=',vf)

    def test_hdr_output_with_incorrect_transfer_tags_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'color tags'):
            self.hdr_command({'codec_name':'hevc','pix_fmt':'yuv420p10le','color_transfer':'smpte2084'},valid_tags=False)

    def test_tonemapx_failure_removes_partial_and_tries_legacy_before_software(self):
        d=Decoder('/runtime');d.hardware={'backend':'vaapi','driver':'iHD'};attempts=[]
        def metadata(name,exe,args,work,**kwargs):
            if '-filters' in args:return b' .S tonemapx V->V SIMD mapper\n'
            return json.dumps({'format':{'duration':'5'},'streams':[{'color_transfer':'arib-std-b67'}]}).encode()
        def encode(source,work,probe,accelerated):
            attempts.append((accelerated,d.tone_mapper))
            dest=work/'compatible.mp4'
            if d.tone_mapper=='tonemapx':dest.write_bytes(b'partial');raise subprocess.CalledProcessError(1,'ffmpeg')
            self.assertFalse(dest.exists());return dest
        with tempfile.TemporaryDirectory() as td,mock.patch.object(d,'run',side_effect=metadata),mock.patch.object(d,'_transcode_once',side_effect=encode),mock.patch('worker.require_space'),mock.patch('builtins.print'):
            d.transcode('source',Path(td))
        self.assertEqual(attempts,[(True,'tonemapx'),(True,'legacy')])

    def test_software_and_missing_compiled_encoder_never_select_device(self):
        self.assertIsNone(hardware.device_for('/unused','software'))
        self.assertIsNone(hardware.device_for('/unused','nvenc',available=set()))
    def test_intel_and_amd_require_driver_and_render_node(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);dev=root/'dev';dev.mkdir();(dev/'renderD128').touch()
            vendor=root/'sys/renderD128/device';vendor.mkdir(parents=True)
            libraries=root/'runtime/videodriver/lib';libraries.mkdir(parents=True)
            fake=SimpleNamespace(st_mode=stat.S_IFCHR|0o660,st_uid=0,st_gid=44,st_rdev=0)
            real_stat=Path.stat
            def safe_stat(p,*args,**kwargs):
                x=real_stat(p,*args,**kwargs)
                return SimpleNamespace(st_uid=0,st_mode=x.st_mode)
            with mock.patch.object(Path,'lstat',return_value=fake),mock.patch.object(Path,'stat',safe_stat),mock.patch.object(hardware.os,'major',return_value=226):
                for pci,driver in [('0x8086','iHD'),('0x1002','radeonsi')]:
                    (vendor/'vendor').write_text(pci)
                    self.assertIsNone(hardware.device_for(root/'runtime','vaapi',dev,root/'sys',{'h264_vaapi'}))
                    (libraries/(driver+'_drv_video.so')).touch()
                    selected=hardware.device_for(root/'runtime','vaapi',dev,root/'sys',{'h264_vaapi'})
                    self.assertEqual(selected['driver'],driver);self.assertEqual(selected['groups'],[44])
                    (libraries/(driver+'_drv_video.so')).unlink()
    def test_hardware_failure_removes_partial_before_software_retry(self):
        with tempfile.TemporaryDirectory() as td:
            work=Path(td);dest=work/'compatible.mp4';decoder=Decoder('/runtime')
            decoder.hardware={'backend':'vaapi','device':'/dev/dri/renderD128','driver':'iHD'}
            calls=[]
            def encode(source,folder,probe,accelerated):
                calls.append(accelerated)
                if accelerated:
                    dest.write_bytes(b'incomplete');raise subprocess.CalledProcessError(1,'ffmpeg')
                self.assertFalse(dest.exists());dest.write_bytes(b'validated');return dest
            with mock.patch.object(decoder,'run',return_value=json.dumps({'format':{'duration':'5'}})),mock.patch.object(decoder,'_transcode_once',side_effect=encode),mock.patch('worker.require_space'),mock.patch('builtins.print') as output:
                self.assertEqual(decoder.transcode('source',work),dest)
                self.assertIn(mock.call('HARDWARE_FALLBACK=software',flush=True),output.call_args_list)
            self.assertEqual(calls,[True,False])
    def test_backend_commands_use_corresponding_encoder(self):
        with tempfile.TemporaryDirectory() as td:
            work=Path(td);probe={'format':{'duration':'5'},'streams':[{'codec_name':'hevc','pix_fmt':'yuv420p10le'}]}
            for backend,encoder in [('vaapi','h264_vaapi'),('qsv','h264_qsv'),('nvenc','h264_nvenc')]:
                d=Decoder('/runtime');d.hardware={'backend':backend,'device':'0' if backend=='nvenc' else '/dev/dri/renderD128'}
                with mock.patch.object(d,'run',return_value=json.dumps({'format':{'duration':'5'}})) as run,mock.patch.object(d,'compatible_video',return_value=True):
                    d._transcode_once('source',work,probe,True)
                command=run.call_args_list[0].args[2]
                self.assertEqual(command[command.index('-c:v')+1],encoder)
                filters=command[command.index('-vf')+1]
                self.assertIn('hwdownload' if backend=='nvenc' else ('scale_vaapi' if backend=='vaapi' else 'scale_qsv'),filters)

    def test_full_range_pixels_use_cpu_range_conversion_before_hardware_encoding(self):
        d=Decoder('/runtime');d.hardware={'backend':'vaapi','device':'/dev/dri/renderD128'}
        probe={'format':{'duration':'5'},'streams':[{'codec_name':'h264','pix_fmt':'yuvj420p','color_range':'pc'}]}
        with tempfile.TemporaryDirectory() as td, mock.patch.object(d,'run',return_value=json.dumps({'format':{'duration':'5'}})) as run,mock.patch.object(d,'compatible_video',return_value=True):
            d._transcode_once('source',Path(td),probe,True)
        args=run.call_args_list[0].args[2];filters=args[args.index('-vf')+1]
        self.assertIn('in_range=auto:out_range=tv',filters)
        self.assertIn('hwdownload',filters);self.assertNotIn('scale_vaapi',filters)

    def test_legacy_intel_driver_is_tried_before_software(self):
        d=Decoder('/runtime');d.hardware={'backend':'vaapi','driver':'iHD','driver_fallbacks':['i965']}
        attempts=[]
        def attempt(source,work,probe,accelerated):
            attempts.append(d.hardware['driver'])
            if d.hardware['driver']=='iHD':raise subprocess.CalledProcessError(1,'ffmpeg')
            return work/'compatible.mp4'
        with tempfile.TemporaryDirectory() as td,mock.patch.object(d,'run',return_value=json.dumps({'format':{'duration':'5'}})),mock.patch.object(d,'_transcode_once',side_effect=attempt),mock.patch('worker.require_space'),mock.patch('builtins.print'):
            d.transcode('source',Path(td))
        self.assertEqual(attempts,['iHD','i965'])

if __name__=='__main__':unittest.main()
