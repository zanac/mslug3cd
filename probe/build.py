#!/usr/bin/env python3
"""Builds the probe disc: python3 probe/build.py <output base name>  (needs m68k-linux-gnu-gcc and Pillow)."""
import os, subprocess, sys
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, '..', 'tools'))
import ngcd_disc as nd

def build_prg():
    o = os.path.join(here, 'build'); os.makedirs(o, exist_ok=True)
    cc = 'm68k-linux-gnu-gcc'
    flags = ['-m68000', '-Os', '-ffreestanding', '-fno-pic', '-fno-builtin', '-nostdlib', '-fno-asynchronous-unwind-tables', '-Wall']
    subprocess.check_call([cc] + flags + ['-c', os.path.join(here, 'start.S'), '-o', o + '/start.o'])
    subprocess.check_call([cc] + flags + ['-c', os.path.join(here, 'probe.c'), '-o', o + '/probe.o'])
    subprocess.check_call(['m68k-linux-gnu-ld', '--build-id=none', '-T', os.path.join(here, 'link.ld'), '-o', o + '/probe.bin', o + '/start.o', o + '/probe.o'])
    return open(o + '/probe.bin', 'rb').read()

def srom_tile(px):
    out = bytearray()
    for xa, xb in ((4, 5), (6, 7), (0, 1), (2, 3)):
        for y in range(8):
            out.append(px[y][xa] | px[y][xb] << 4)
    return bytes(out)

FONT_5X7 = {
 '0':'01110 10001 10011 10101 11001 10001 01110','1':'00100 01100 00100 00100 00100 00100 01110',
 '2':'01110 10001 00001 00010 00100 01000 11111','3':'11110 00001 00001 01110 00001 00001 11110',
 '4':'00010 00110 01010 10010 11111 00010 00010','5':'11111 10000 11110 00001 00001 10001 01110',
 '6':'00110 01000 10000 11110 10001 10001 01110','7':'11111 00001 00010 00100 01000 01000 01000',
 '8':'01110 10001 10001 01110 10001 10001 01110','9':'01110 10001 10001 01111 00001 00010 01100',
 'A':'01110 10001 10001 11111 10001 10001 10001','B':'11110 10001 10001 11110 10001 10001 11110',
 'C':'01110 10001 10000 10000 10000 10001 01110','D':'11100 10010 10001 10001 10001 10010 11100',
 'E':'11111 10000 10000 11110 10000 10000 11111','F':'11111 10000 10000 11110 10000 10000 10000',
 'G':'01110 10001 10000 10111 10001 10001 01111','H':'10001 10001 10001 11111 10001 10001 10001',
 'I':'01110 00100 00100 00100 00100 00100 01110','J':'00111 00010 00010 00010 00010 10010 01100',
 'K':'10001 10010 10100 11000 10100 10010 10001','L':'10000 10000 10000 10000 10000 10000 11111',
 'M':'10001 11011 10101 10101 10001 10001 10001','N':'10001 11001 10101 10011 10001 10001 10001',
 'O':'01110 10001 10001 10001 10001 10001 01110','P':'11110 10001 10001 11110 10000 10000 10000',
 'Q':'01110 10001 10001 10001 10101 10010 01101','R':'11110 10001 10001 11110 10100 10010 10001',
 'S':'01111 10000 10000 01110 00001 00001 11110','T':'11111 00100 00100 00100 00100 00100 00100',
 'U':'10001 10001 10001 10001 10001 10001 01110','V':'10001 10001 10001 10001 10001 01010 00100',
 'W':'10001 10001 10001 10101 10101 11011 10001','X':'10001 10001 01010 00100 01010 10001 10001',
 'Y':'10001 10001 01010 00100 00100 00100 00100','Z':'11111 00001 00010 00100 01000 10000 11111',
 '-':'00000 00000 00000 11111 00000 00000 00000','.':'00000 00000 00000 00000 00000 01100 01100',
 ':':'00000 01100 01100 00000 01100 01100 00000','=':'00000 00000 11111 00000 11111 00000 00000',
 '/':'00001 00001 00010 00100 01000 10000 10000','?':'01110 10001 00001 00010 00100 00000 00100',
}

def build_fix():
    """a 128 KB fix file: tile = ASCII code (lower case shows as upper case), a 5 x 7 font in 8 x 8 cells.
    Pen 1 = the glyph, pen 0 = transparent (the font is this project's own)"""
    fix = bytearray(0x20000)
    for c in range(32, 127):
        glyph = FONT_5X7.get(chr(c).upper())
        px = [[0] * 8 for _ in range(8)]
        if glyph:
            for y, row in enumerate(glyph.split()):
                for x, bit in enumerate(row):
                    px[y][x + 1] = int(bit)
        fix[c * 32:c * 32 + 32] = srom_tile(px)
    return bytes(fix)

if __name__ == '__main__':
    base = sys.argv[1]
    files = dict(nd.SNK_TEXT)
    files['PROBE.PRG'] = build_prg()
    files['PROBE.FIX'] = build_fix()
    files['IPL.TXT'] = nd.ipl_text([('PROBE.FIX', 0, 0), ('PROBE.PRG', 0, 0)])
    print(nd.write_disc(base, files, volume='NGCDPROBE'))
