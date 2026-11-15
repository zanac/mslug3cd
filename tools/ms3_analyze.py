#!/usr/bin/env python3
"""Reads a TRACE file of tools/ms3_run.c and prints the working set of the sprite tiles.

usage: ms3_analyze.py TRACE [first_frame last_frame]
A 16x16 tile is 128 bytes: 32768 tiles fill the 4 MB of sprite RAM of the Neo Geo CD."""
import struct
import sys
from collections import Counter

TILE_BYTES = 128
SPRITE_RAM_TILES = 4 * 1024 * 1024 // TILE_BYTES


def read_trace(path):
    """returns (windows [(frame, set of tiles)], samples [(frame, start, end)], banks [(frame, pc, bank)],
    pages [(frame, set of 256-byte pages of the program ROM touched)])"""
    data = open(path, 'rb').read()
    windows, samples, banks, pages, window_pairs, position = [], [], [], [], [], 0
    while position < len(data):
        kind, frame = struct.unpack_from('<II', data, position)
        position += 8
        if kind == ord('T'):
            count, = struct.unpack_from('<I', data, position)
            position += 4
            windows.append((frame, set(struct.unpack_from('<%dI' % count, data, position))))
            position += 4 * count
        elif kind == ord('P'):
            count, = struct.unpack_from('<I', data, position)
            position += 4
            pages.append((frame, set(struct.unpack_from('<%dI' % count, data, position))))
            position += 4 * count
        elif kind == ord('W'):
            count, = struct.unpack_from('<I', data, position)
            position += 4
            values = struct.unpack_from('<%dI' % (2 * count), data, position)
            window_pairs.append((frame, set(zip(values[0::2], values[1::2]))))
            position += 8 * count
        elif kind == ord('A'):
            samples.append((frame,) + struct.unpack_from('<II', data, position))
            position += 8
        elif kind == ord('B'):
            value, = struct.unpack_from('<I', data, position)
            banks.append((frame, value & 0xffffff, value >> 24))
            position += 4
        else:
            raise SystemExit('bad record %x at %d' % (kind, position))
    read_trace.window_pairs = window_pairs
    return windows, samples, banks, pages


if __name__ == '__main__':
    windows, samples, banks, pages = read_trace(sys.argv[1])
    first = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    last = int(sys.argv[3]) if len(sys.argv) > 3 else 1 << 30
    chosen = [(frame, tiles) for frame, tiles in windows if first <= frame <= last]
    union = set()
    print('frame  tiles-in-window  new  cumulative')
    for frame, tiles in chosen:
        new = len(tiles - union)
        union |= tiles
        if new or frame % 600 == 29:
            print('%6d %6d %6d %8d' % (frame, len(tiles), new, len(union)))
    print('distinct tiles', len(union), '= %.1f MB (sprite RAM %d tiles)' % (len(union) * TILE_BYTES / 2**20, SPRITE_RAM_TILES))
    print('ADPCM-A samples', len({(s, e) for f, s, e in samples if first <= f <= last}))
    print('bank switches', Counter(b for f, pc, b in banks if first <= f <= last))
    touched = set()
    for frame, page_set in pages:
        if first <= frame <= last:
            touched |= page_set
    print('program ROM touched: %d pages of 256 bytes = %.2f MB' % (len(touched), len(touched) * 256 / 2**20))
