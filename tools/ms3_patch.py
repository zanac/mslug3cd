#!/usr/bin/env python3
"""Builds the patch that makes Metal Slug 3 write renumbered sprite tiles.

usage: ms3_patch.py program_be.bin tiles.txt out_patch out_inverse
  program_be.bin  the decrypted 68000 program, big-endian (the first 1 MB is the fixed region)
  tiles.txt       one used tile number (hex) per line
  out_patch       records [u32 address][u32 length][bytes] (the format tools/ms3_run.c PATCH reads)
  out_inverse     32768 u32: the original number of every renumbered tile (the test core draws with it)

The game draws a sprite column with an unrolled loop of 1024 identical blocks
    move.w (a3)+,d0 ; move.l d0,(a6) ; add.l d2,d0 ; move.l d1,(a6) ; add.l d2,d1
(tile word, then attribute word: palette, tile bits 16-19, flips).  Each block becomes
    jsr stub ; nop ; nop
(same 10 bytes, so the loop's jump tables stay right) and the stub, in the free area at the end of the
fixed region, looks the tile up in the run table and writes the new number with bits 16-19 cleared.
"""
import re
import struct
import subprocess
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ms3_tilemap

BLOCK = bytes.fromhex('301b2c80d0822c81d282')
STUB_ADDRESS = 0xFA400                      # free area of the fixed region (0xFA212-0xFFC82)

STUB = r"""
        .text
        .macro  XLAT                        /* in: d3 = 20-bit tile; out: d0 = renumbered low word; clobbers d3-d5/a0-a1 */
        move.l  %d3, %d4
        lsr.l   #8, %d4                     /* its 256-tile page */
        add.w   %d4, %d4
        move.l  #TOP, %a0
        add.l   %d4, %a0
        move.w  (%a0), %d4                  /* byte offset of the page's first run, 0xFFFF: none */
        cmp.w   #-1, %d4
        beq.s   missing\@
        and.l   #0xFFFF, %d4
        move.l  #RUNS, %a1
        add.l   %d4, %a1
scan\@: move.l  (%a1), %d5                  /* the run's first tile */
        cmp.l   %d3, %d5
        bhi.s   missing\@                    /* it starts after the tile: not mapped */
        moveq   #0, %d4
        move.w  4(%a1), %d4
        add.l   %d5, %d4                    /* one past the run's last tile */
        cmp.l   %d3, %d4
        bhi.s   found\@
        addq.l  #8, %a1
        bra.s   scan\@
found\@: sub.l   %d5, %d3
        add.w   6(%a1), %d3
        move.w  %d3, %d0                    /* the renumbered tile */
        bra.s   done\@
missing\@:
        move.w  #0, %d0                     /* never seen in training: the blank tile */
done\@:
        .endm

stub:   move.w  (%a3)+, %d0                 /* the tile's low 16 bits */
        movem.l %d3-%d5/%a0-%a1, -(%sp)
        moveq   #0, %d3
        move.w  %d1, %d3
        lsr.w   #4, %d3
        and.w   #15, %d3
        swap    %d3
        move.w  %d0, %d3                    /* d3 = the 20-bit tile number */
        XLAT
        move.l  %d1, %d5
        and.w   #0xFF0F, %d5                /* tile bits 16-19 are 0 now */
        move.l  %d0, (%a6)
        add.l   %d2, %d0
        move.l  %d5, (%a6)
        add.l   %d2, %d1
        movem.l (%sp)+, %d3-%d5/%a0-%a1
        rts

/* the column copy at 0x17a92: tile word and attribute word come from the stream (a4), the address is in d7's high half */
stub2:  movem.l %d0/%d3-%d5/%a0-%a1, -(%sp)
        move.w  (%a4)+, %d0
        move.w  (%a4)+, %d4
        move.w  %d4, -(%sp)
        moveq   #0, %d3
        move.w  %d4, %d3
        lsr.w   #4, %d3
        and.w   #15, %d3
        swap    %d3
        move.w  %d0, %d3
        XLAT
        move.w  (%sp)+, %d5
        and.w   #0xFF0F, %d5
        move.w  %d0, %d7
        move.l  %d7, 0x3c0000.l
        add.l   #0x10000, %d7
        move.w  %d5, %d7
        move.l  %d7, 0x3c0000.l
        movem.l (%sp)+, %d0/%d3-%d5/%a0-%a1
        rts
"""


def assemble(source, origin, tmp='/tmp'):
    """returns (binary, address of stub2)"""
    s = os.path.join(tmp, 'ms3stub.s')
    open(s, 'w').write(source)
    subprocess.check_call(['m68k-linux-gnu-as', '-m68000', '-o', s + '.o', s])
    subprocess.check_call(['m68k-linux-gnu-ld', '--build-id=none', '-Ttext=0x%x' % origin, '-o', s + '.elf', s + '.o'], stderr=subprocess.DEVNULL)
    subprocess.check_call(['m68k-linux-gnu-objcopy', '-O', 'binary', s + '.elf', s + '.bin'])
    stub2 = 0
    for line in subprocess.check_output(['m68k-linux-gnu-nm', s + '.elf']).decode().split('\n'):
        if line.endswith(' stub2'):
            stub2 = int(line.split()[0], 16)
    return open(s + '.bin', 'rb').read(), stub2


def main(program, tiles_file, out_patch, out_inverse):
    program = open(program, 'rb').read()[:0x100000]
    tiles = [int(line, 16) for line in open(tiles_file) if line.strip()]
    runs, inverse, slots = ms3_tilemap.build_map(tiles)
    top, body = ms3_tilemap.table_bytes(runs)

    # the stub's size does not depend on the table addresses (absolute 32-bit): assemble twice
    size = len(assemble(STUB.replace('TOP', '0').replace('RUNS', '0'), STUB_ADDRESS)[0])
    top_address = (STUB_ADDRESS + size + 1) & ~1
    runs_address = top_address + len(top)
    stub, stub2 = assemble(STUB.replace('TOP', '0x%x' % top_address).replace('RUNS', '0x%x' % runs_address), STUB_ADDRESS)
    area = stub.ljust(top_address - STUB_ADDRESS, b'\0') + top + body
    assert STUB_ADDRESS + len(area) < 0xFFC00, 'the stub area is full'

    patches = [(STUB_ADDRESS, area)]
    blocks = [m.start() for m in re.finditer(re.escape(BLOCK), program)]
    call = struct.pack('>HI', 0x4EB9, STUB_ADDRESS) + bytes.fromhex('4e714e71')
    for address in blocks:
        patches.append((address, call))
    # the column copy: movew (a4)+,d7 ; movel d7,0x3c0000 ; addil #65536,d7 ; movew (a4)+,d7 ; movel d7,0x3c0000
    copy = bytes.fromhex('3e1c23c7003c00000687000100003e1c23c7003c0000')
    copies = [m.start() for m in re.finditer(re.escape(copy), program)]
    for address in copies:
        patches.append((address, struct.pack('>HI', 0x4EB9, stub2) + bytes.fromhex('4e71') * 8))
    with open(out_patch, 'wb') as f:
        for address, data in patches:
            f.write(struct.pack('<II', address, len(data)) + data)
    with open(out_inverse, 'wb') as f:
        f.write(struct.pack('<%dI' % len(inverse), *inverse))
    print('%d column copies patched, %d blocks patched, %d runs, %d of 32768 tile slots, stub area %d bytes at 0x%x'
          % (len(copies), len(blocks), len(runs), slots, len(area), STUB_ADDRESS))


if __name__ == '__main__':
    main(*sys.argv[1:5])
