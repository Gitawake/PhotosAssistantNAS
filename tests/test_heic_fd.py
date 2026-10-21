import ctypes as C
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/photos_assistant'))
from heic_fd import FdReader, thumbnail_size, generate


class HeicReaderTests(unittest.TestCase):
    def test_seekable_reader_handles_chunks_without_changing_fd_offset(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'source';payload=b'abcde'*(1024*1024)
            path.write_bytes(payload)
            fd=os.open(path,os.O_RDONLY)
            try:
                reader=FdReader(fd);buffer=C.create_string_buffer(len(payload))
                self.assertEqual(reader.read(C.addressof(buffer),len(payload),None),0)
                self.assertEqual(buffer.raw,payload)
                self.assertEqual(os.lseek(fd,0,os.SEEK_CUR),0)
                self.assertEqual(reader.seek(3,None),0)
                self.assertEqual(reader.read(C.addressof(buffer),4,None),0)
                self.assertEqual(buffer.raw[:4],b'deab')
                self.assertEqual(reader.position(None),7)
            finally: os.close(fd)

    def test_out_of_range_reads_and_seek_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'source';path.write_bytes(b'1234');fd=os.open(path,os.O_RDONLY)
            try:
                reader=FdReader(fd);buffer=C.create_string_buffer(8)
                self.assertEqual(reader.read(C.addressof(buffer),5,None),1)
                self.assertEqual(reader.seek(-1,None),1)
                self.assertEqual(reader.seek(5,None),1)
                self.assertEqual(reader.wait(4,None),0)
                self.assertEqual(reader.wait(5,None),2)
                self.assertEqual(reader.offset,0)
                with mock.patch('heic_fd.os.pread',side_effect=OSError('failed')):
                    self.assertEqual(reader.reader.read(C.addressof(buffer),1,None),1)
                self.assertTrue(reader.failed)
            finally: os.close(fd)

    def test_writable_empty_and_nonregular_fds_rejected(self):
        with tempfile.TemporaryFile() as source:
            source.write(b'x');source.flush()
            with self.assertRaises(ValueError): FdReader(source.fileno())
        read,write=os.pipe()
        try:
            with self.assertRaises(ValueError): FdReader(read)
        finally: os.close(read);os.close(write)

    def test_thumbnail_geometry_preserves_aspect_and_does_not_upscale(self):
        self.assertEqual(thumbnail_size(4032,3024,320),(427,320))
        self.assertEqual(thumbnail_size(1080,1440,1280),(1080,1440))
        self.assertEqual(thumbnail_size(100,100,240),(100,100))

    def test_root_never_loads_media_libraries(self):
        with mock.patch('heic_fd.os.geteuid',return_value=0),mock.patch('heic_fd.C.CDLL') as load:
            with self.assertRaises(RuntimeError): generate(3,Path('/unused'))
            load.assert_not_called()
