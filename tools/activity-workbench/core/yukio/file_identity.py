"""A persistent Mac file identity, without trusting a boot-local device number.

The legacy device/inode identity still guards an open read against replacement.
On volumes without a usable UUID, callers keep that conservative fallback.
"""
import ctypes
from functools import lru_cache
import math
import struct
import sys


class _AttrList(ctypes.Structure):
    _fields_ = [('bitmapcount', ctypes.c_ushort), ('reserved', ctypes.c_ushort),
                ('commonattr', ctypes.c_uint32), ('volattr', ctypes.c_uint32),
                ('dirattr', ctypes.c_uint32), ('fileattr', ctypes.c_uint32),
                ('forkattr', ctypes.c_uint32)]


@lru_cache(maxsize=1)
def _get_volume_attributes():
    function = ctypes.CDLL(None, use_errno=True).fgetattrlist
    function.argtypes = [ctypes.c_int, ctypes.POINTER(_AttrList), ctypes.c_void_p,
                         ctypes.c_size_t, ctypes.c_ulong]
    function.restype = ctypes.c_int
    return function


def persistent_file_identity(fd, info):
    """Identify the already-open Mac file by volume UUID, inode and birth time.

    fgetattrlist reads the descriptor being ingested, avoiding a path lookup
    race. Its fixed result is a uint32 length followed by the 16-byte UUID.
    Never persist an all-zero/unsupported UUID or invent a replacement identity.
    """
    if sys.platform != 'darwin':
        return None
    birth = getattr(info, 'st_birthtime', None)
    if not isinstance(birth, (int, float)) or not math.isfinite(birth):
        return None
    try:
        # sys/attr.h: ATTR_BIT_MAP_COUNT, ATTR_VOL_INFO | ATTR_VOL_UUID.
        attributes = _AttrList(5, 0, 0, 0x80040000, 0, 0, 0)
        buffer = ctypes.create_string_buffer(20)
        if _get_volume_attributes()(fd, ctypes.byref(attributes), buffer, len(buffer), 0) != 0:
            return None
        if struct.unpack('=I', buffer.raw[:4])[0] != len(buffer) or not any(buffer.raw[4:]):
            return None
        return 'mac-volume-v1:%s:%d:%s' % (buffer.raw[4:].hex(), info.st_ino, float(birth).hex())
    except (AttributeError, OSError):
        return None
