"""Neo Geo CD disc builder: files -> ISO 9660 track (laid out like a real SNK disc) -> BIN/CUE (+CHD).

The layout copies a real Japanese disc (League Bowling): PVD in sector 16, path tables in
18/19, the root directory in 20, the files from sector 21 in alphabetical order, names
without ";1", the SNK check files ABS/BIB/CPY.TXT that the BIOS reads, an IPL.TXT last.
Everything is written as raw MODE1/2352 sectors with real EDC/ECC.
"""
import struct, os, sys, subprocess

# ---- raw sector encoding (ECMA-130 mode 1) ---------------------------------------------
def _tables():
    ecc_f = [0] * 256; ecc_b = [0] * 256; edc = [0] * 256
    for i in range(256):
        j = (i << 1) ^ (0x11D if i & 0x80 else 0)
        ecc_f[i] = j & 0xFF; ecc_b[i ^ j & 0xFF] = i
        e = i
        for _ in range(8):
            e = (e >> 1) ^ (0xD8018001 if e & 1 else 0)
        edc[i] = e & 0xFFFFFFFF
    return ecc_f, ecc_b, edc
ECC_F, ECC_B, EDC = _tables()

def edc_calc(data):
    c = 0
    for b in data:
        c = (c >> 8) ^ EDC[(c ^ b) & 0xFF]
    return c

def ecc_block(src, major, minor, major_mult, minor_inc, dest):
    size = major * minor
    for m in range(major):
        index = (m >> 1) * major_mult + (m & 1)
        a = b = 0
        for _ in range(minor):
            t = src[index]
            index += minor_inc
            if index >= size: index -= size
            a ^= t; b ^= t; a = ECC_F[a]
        a = ECC_B[ECC_F[a] ^ b]
        dest[m] = a; dest[m + major] = a ^ b

def raw_sector(lba, data):
    """2048 bytes of user data at address lba (0 = 00:02:00) -> 2352 raw bytes."""
    s = bytearray(2352)
    s[0] = 0; s[1:11] = b'\xff' * 10; s[11] = 0
    f = lba + 150
    bcd = lambda v: ((v // 10) << 4) | (v % 10)
    s[12] = bcd(f // 4500); s[13] = bcd(f // 75 % 60); s[14] = bcd(f % 75); s[15] = 1
    s[16:16 + 2048] = data
    struct.pack_into('<I', s, 2064, edc_calc(s[0:2064]))
    # ECC (mode 1) covers header+data+EDC+8 zero bytes, then P parity for the Q pass
    tmp = bytearray(s[12:2076])
    p = bytearray(172); q = bytearray(104)
    ecc_block(tmp, 86, 24, 2, 86, p)
    ecc_block(bytearray(tmp) + p, 52, 43, 86, 88, q)
    s[2076:2248] = p; s[2248:2352] = q
    return bytes(s)

# ---- ISO 9660 --------------------------------------------------------------------------
def both32(v): return struct.pack('<I', v) + struct.pack('>I', v)
def both16(v): return struct.pack('<H', v) + struct.pack('>H', v)
DATE7 = bytes([94, 8, 7, 21, 11, 8, 0])
def dir_record(name, extent, size, is_dir=False):
    nl = len(name)
    pad = (33 + nl) & 1
    use = b'AA\x0e\x02TEXT    \x01\x00'          # the mastering tool's Apple extension, as on the real disc
    rec = bytes([33 + nl + pad + len(use), 0]) + both32(extent) + both32(size) + DATE7
    rec += bytes([2 if is_dir else 0, 0, 0]) + both16(1) + bytes([nl]) + name + b'\0' * pad + use
    return rec

def build_track(files, volume='MS3CD', pad_sectors=750):
    """files: dict name -> bytes. Returns the track as raw 2352-byte sectors (bytes)."""
    names = sorted(files)
    sectors = {}                                   # lba -> 2048 bytes
    lba = 21; extents = {}
    for n in names:
        extents[n] = lba
        data = files[n]
        for i in range(0, max(len(data), 1), 2048):
            sectors[lba + i // 2048] = data[i:i + 2048].ljust(2048, b'\0')
        lba += (len(data) + 2047) // 2048
    total = lba
    # '.' and '..' have no Apple extension on the real disc
    def plain(ident):
        return bytes([34, 0]) + both32(20) + both32(2048) + DATE7 + bytes([2, 0, 0]) + both16(1) + bytes([1, ident])
    d = plain(0) + plain(1)
    for n in names:
        d += dir_record(n.encode(), extents[n], len(files[n]))
    assert len(d) <= 2048
    sectors[20] = d.ljust(2048, b'\0')
    sectors[18] = (bytes([1, 0]) + struct.pack('<I', 20) + struct.pack('<H', 1) + b'\0\0').ljust(2048, b'\0')
    sectors[19] = (bytes([1, 0]) + struct.pack('>I', 20) + struct.pack('>H', 1) + b'\0\0').ljust(2048, b'\0')
    sectors[17] = (b'\xffCD001\x01').ljust(2048, b'\0')
    pvd = bytearray(2048)
    pvd[0:8] = b'\x01CD001\x01\x00'
    pvd[8:40] = b'APPLE COMPUTER, INC., TYPE: 0002'
    pvd[40:72] = volume.encode().ljust(32)
    pvd[80:88] = both32(total)
    pvd[120:128] = both16(1) + both16(1)
    pvd[128:132] = both16(2048)
    pvd[132:140] = both32(10)
    pvd[140:144] = struct.pack('<I', 18); pvd[148:152] = struct.pack('>I', 19)
    pvd[156:190] = plain(0)[:34]
    for off in (190, 318, 446, 574, 702, 739, 776):
        pvd[off:off + (128 if off < 702 else 37)] = b' ' * (128 if off < 702 else 37)
    for off in (813, 830, 864): pvd[off:off + 17] = b'1994080721110900\0'
    pvd[847:864] = b'0000000000000000\0'
    pvd[881] = 1
    sectors[16] = bytes(pvd)
    out = bytearray()
    for n in range(total + pad_sectors):
        out += raw_sector(n, sectors.get(n, bytes(2048)))
    return bytes(out)

def write_disc(path_base, files, audio=None, volume='MS3CD'):
    """Writes <path_base>.bin/.cue (track 1 data + track 2 silence or the given raw audio) and returns the cue path."""
    track1 = build_track(files, volume)
    name1 = os.path.basename(path_base) + ' (Track 1).bin'
    name2 = os.path.basename(path_base) + ' (Track 2).bin'
    open(path_base + ' (Track 1).bin', 'wb').write(track1)
    open(path_base + ' (Track 2).bin', 'wb').write(audio if audio else bytes(2352 * 75 * 33))   # 3 s pause + 30 s silence
    cue = 'FILE "%s" BINARY\r\n  TRACK 01 MODE1/2352\r\n    FLAGS DCP\r\n    INDEX 01 00:00:00\r\nFILE "%s" BINARY\r\n  TRACK 02 AUDIO\r\n    FLAGS DCP\r\n    INDEX 00 00:00:00\r\n    INDEX 01 00:03:00\r\n' % (name1, name2)
    open(path_base + '.cue', 'w', newline='').write(cue)
    return path_base + '.cue'

SNK_TEXT = {'ABS.TXT': b'Abstracted by SNK corporation\x1a', 'BIB.TXT': b'Bibliographiced by SNK corporation\x1a',
            'CPY.TXT': b'Copyright by SNK corporation\x1a'}
def ipl_text(entries):
    return b''.join(('%s,%d,%d\r\n' % e).encode() for e in entries) + b'\x1a'
