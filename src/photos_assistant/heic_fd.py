#!/usr/bin/env python3
"""Private, unprivileged HEIF reader -> in-memory MagickWand thumbnail bridge.

Uses the pinned libheif 1.20.2 reader-v1 and ImageMagick 7 public C APIs.
No source pathname, source copy, or encoded intermediate image is used.
"""
import array
import ctypes as C
import fcntl
import math
import os
from pathlib import Path
import stat
import sys

MAX_PIXELS = 64 * 1024 * 1024
MAX_PROFILE = 4 * 1024 * 1024
VOID = C.c_void_p
SIZE = C.c_size_t
INT = C.c_int
POS = C.c_int64


class HeifError(C.Structure):
    _fields_ = [('code', INT), ('subcode', INT), ('message', C.c_char_p)]


GET = C.CFUNCTYPE(POS, VOID)
READ = C.CFUNCTYPE(INT, VOID, SIZE, VOID)
SEEK = C.CFUNCTYPE(INT, POS, VOID)
WAIT = C.CFUNCTYPE(INT, POS, VOID)


class Reader(C.Structure):
    _fields_ = [('version', INT), ('position', GET), ('read', READ),
                ('seek', SEEK), ('wait', WAIT), ('range', VOID),
                ('preload', VOID), ('release', VOID), ('release_error', VOID)]


class FdReader:
    def __init__(self, fd):
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_size <= 0 or
                fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE != os.O_RDONLY):
            raise ValueError('A read-only regular original is required')
        self.fd, self.size, self.offset = fd, info.st_size, 0
        self.failed = False
        self.callbacks = (GET(self.position), READ(self.read), SEEK(self.seek), WAIT(self.wait))
        self.reader = Reader(1, *self.callbacks, None, None, None, None)

    def position(self, unused):
        return self.offset

    def read(self, destination, length, unused):
        try:
            if length > self.size - self.offset:
                return 1
            done = 0
            while done < length:
                block = os.pread(self.fd, min(length - done, 1024 * 1024), self.offset + done)
                if not block:
                    return 1
                C.memmove(destination + done, block, len(block))
                done += len(block)
            self.offset += done
            return 0
        except BaseException:
            self.failed = True
            return 1

    def seek(self, position, unused):
        if not 0 <= position <= self.size:
            return 1
        self.offset = position
        return 0

    def wait(self, target, unused):
        return 0 if 0 <= target <= self.size else 2


def bind(library, name, result, *args):
    function = getattr(library, name)
    function.restype, function.argtypes = result, list(args)
    return function


def check(error):
    if error.code:
        # Do not include untrusted metadata, paths or native error strings in logs.
        raise RuntimeError('HEIF operation failed (%s.%s)' % (error.code, error.subcode))


def thumbnail_size(width, height, size):
    scale = min(1.0, max(size / width, size / height))
    return max(1, math.floor(width * scale + 0.5)), max(1, math.floor(height * scale + 0.5))


def generate(fd, work, expected=(0, 0)):
    if os.geteuid() == 0:
        raise RuntimeError('Refusing root media decoding')
    work = Path(work)
    base = Path(__file__).resolve().parent / 'runtime/imagemagick/lib'
    heif = C.CDLL(str(base / 'libheif.so.1'))
    wand = C.CDLL(str(base / 'libMagickWand-7.Q16HDRI.so.10'))
    alloc = bind(heif, 'heif_context_alloc', VOID)
    free = bind(heif, 'heif_context_free', None, VOID)
    load = bind(heif, 'heif_context_read_from_reader', HeifError, VOID, C.POINTER(Reader), VOID, VOID)
    primary = bind(heif, 'heif_context_get_primary_image_handle', HeifError, VOID, C.POINTER(VOID))
    release_handle = bind(heif, 'heif_image_handle_release', None, VOID)
    width_of = bind(heif, 'heif_image_handle_get_width', INT, VOID)
    height_of = bind(heif, 'heif_image_handle_get_height', INT, VOID)
    depth_of = bind(heif, 'heif_image_handle_get_luma_bits_per_pixel', INT, VOID)
    has_alpha = bind(heif, 'heif_image_handle_has_alpha_channel', INT, VOID)
    decode = bind(heif, 'heif_decode_image', HeifError, VOID, C.POINTER(VOID), INT, INT, VOID)
    release_image = bind(heif, 'heif_image_release', None, VOID)
    plane_of = bind(heif, 'heif_image_get_plane_readonly', VOID, VOID, INT, C.POINTER(INT))
    decoded_width = bind(heif, 'heif_image_get_width', INT, VOID, INT)
    decoded_height = bind(heif, 'heif_image_get_height', INT, VOID, INT)
    decoded_depth = bind(heif, 'heif_image_get_bits_per_pixel_range', INT, VOID, INT)
    profile_size = bind(heif, 'heif_image_handle_get_raw_color_profile_size', SIZE, VOID)
    profile_read = bind(heif, 'heif_image_handle_get_raw_color_profile', HeifError, VOID, VOID)
    threads = bind(heif, 'heif_context_set_max_decoding_threads', None, VOID, INT)
    genesis = bind(wand, 'MagickWandGenesis', None)
    terminus = bind(wand, 'MagickWandTerminus', None)
    new = bind(wand, 'NewMagickWand', VOID)
    destroy = bind(wand, 'DestroyMagickWand', VOID, VOID)
    new_pixel = bind(wand, 'NewPixelWand', VOID)
    destroy_pixel = bind(wand, 'DestroyPixelWand', VOID, VOID)
    new_image = bind(wand, 'MagickNewImage', INT, VOID, SIZE, SIZE, VOID)
    import_row = bind(wand, 'MagickImportImagePixels', INT, VOID, C.c_ssize_t, C.c_ssize_t,
                      SIZE, SIZE, C.c_char_p, INT, VOID)
    profile = bind(wand, 'MagickProfileImage', INT, VOID, C.c_char_p, VOID, SIZE)
    clone = bind(wand, 'CloneMagickWand', VOID, VOID)
    thumbnail = bind(wand, 'MagickThumbnailImage', INT, VOID, SIZE, SIZE)
    quality = bind(wand, 'MagickSetImageCompressionQuality', INT, VOID, SIZE)
    set_depth = bind(wand, 'MagickSetImageDepth', INT, VOID, SIZE)
    write = bind(wand, 'MagickWriteImage', INT, VOID, C.c_char_p)
    limit = bind(wand, 'MagickSetResourceLimit', INT, INT, C.c_uint64)

    def ok(value):
        if not value:
            raise RuntimeError('ImageMagick operation failed')
        return value

    reader = FdReader(fd)
    context = alloc()
    if not context:
        raise MemoryError('HEIF context allocation failed')
    handle, image = VOID(), VOID()
    image_wand = pixel = None
    genesis()
    try:
        # Cache must remain in RAM; failure must not silently create disk/map caches.
        for resource, value in ((2, 0), (5, 0), (6, 768 * 1024**2), (7, 2), (9, 180)):
            ok(limit(resource, value))
        threads(context, 2)
        check(load(context, C.byref(reader.reader), None, None))
        check(primary(context, C.byref(handle)))
        width, height = width_of(handle), height_of(handle)
        if min(width, height) <= 0 or max(width, height) > 32768 or width * height > MAX_PIXELS:
            raise ValueError('HEIF dimensions exceed memory processing limit')
        if all(expected) and sorted(expected) != sorted((width, height)):
            raise ValueError('HEIF primary image dimensions differ from Photos')
        depth, alpha = depth_of(handle), bool(has_alpha(handle))
        if not 1 <= depth <= 16:
            raise ValueError('Unsupported HEIF bit depth')
        chroma = (15 if alpha else 14) if depth > 8 else (11 if alpha else 10)
        check(decode(handle, C.byref(image), 1, chroma, None))
        if (decoded_width(image, 10), decoded_height(image, 10)) != (width, height):
            raise ValueError('HEIF decoded image dimensions changed')
        depth = decoded_depth(image, 10)
        if not 1 <= depth <= 16:
            raise ValueError('Unsupported decoded bit depth')
        stride = INT()
        plane = plane_of(image, 10, C.byref(stride))
        channels = 4 if alpha else 3
        row_bytes = width * channels * (2 if depth > 8 else 1)
        if not plane or stride.value < row_bytes:
            raise ValueError('Invalid HEIF pixel plane')
        image_wand, pixel = ok(new()), ok(new_pixel())
        ok(new_image(image_wand, width, height, pixel))
        for y in range(height):
            pointer = plane + y * stride.value
            if depth > 8:
                # Match ImageMagick's HEIC coder: left-align 10/12-bit samples in 16 bits.
                row = array.array('H')
                row.frombytes(C.string_at(pointer, row_bytes))
                if sys.byteorder != 'little':
                    row.byteswap()
                if depth < 16:
                    row = array.array('H', (value << (16 - depth) for value in row))
                pointer = row.buffer_info()[0]
            ok(import_row(image_wand, 0, y, width, 1, b'RGBA' if alpha else b'RGB',
                          7 if depth > 8 else 1, pointer))
        release_image(image); image = VOID()
        length = profile_size(handle)
        if length > min(MAX_PROFILE, reader.size):
            raise ValueError('HEIF color profile exceeds limit')
        if length:
            data = C.create_string_buffer(length)
            check(profile_read(handle, data))
            ok(profile(image_wand, b'icc', data, length))
        for label, size in (('SM', 240), ('M', 320), ('XL', 1280)):
            output = ok(clone(image_wand))
            try:
                ok(thumbnail(output, *thumbnail_size(width, height, size)))
                ok(set_depth(output, 8)); ok(quality(output, 85))
                ok(write(output, os.fsencode(work / (label + '.jpg'))))
            finally:
                destroy(output)
        if reader.failed:
            raise RuntimeError('Original read failed')
    finally:
        if pixel:
            destroy_pixel(pixel)
        if image_wand:
            destroy(image_wand)
        if image:
            release_image(image)
        if handle:
            release_handle(handle)
        free(context)
        terminus()


if __name__ == '__main__':
    generate(int(sys.argv[1]), Path(sys.argv[2]), tuple(map(int, sys.argv[3:5])) or (0, 0))
