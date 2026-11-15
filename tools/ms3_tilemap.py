#!/usr/bin/env python3
"""Renumbers the sprite tiles of Metal Slug 3 so that the ones a part of the game uses fit the 32768
tiles of the Neo Geo CD's sprite RAM.

A tile number is 20 bits (the attribute word's bits 4-7 are bits 16-19), the CD keeps 15.  The used
tiles form runs; a run keeps its order and its number modulo 8 (the hardware's auto-animation
replaces the low 2 or 3 bits of the tile number), so it only has to move.

build_map(tiles)   -> runs [(old_start, count, new_start)], inverse table (list of 32768 old numbers)
table_bytes(runs)  -> the lookup data the 68000 stub reads: top index (by tile >> 8) and the run records
"""
import struct


def build_runs(tiles, merge_gap=2):
    """sorted tile numbers -> runs (start, count); gaps up to merge_gap tiles are filled in"""
    tiles = sorted(set(tiles))
    runs = []
    start = previous = tiles[0]
    for tile in tiles[1:]:
        if tile - previous - 1 > merge_gap:
            runs.append((start, previous - start + 1))
            start = tile
        previous = tile
    runs.append((start, previous - start + 1))
    return runs


def build_map(tiles, limit=0x8000, merge_gap=2):
    runs = []
    position = 0
    for start, count in build_runs(tiles, merge_gap):
        position += (start - position) % 8              # keep the number modulo 8
        runs.append((start, count, position))
        position += count
    if position > limit:
        raise SystemExit('the tiles need %d slots, the sprite RAM has %d' % (position, limit))
    inverse = [0] * limit
    for start, count, new in runs:
        for k in range(count):
            inverse[new + k] = start + k
    return runs, inverse, position


def table_bytes(runs):
    """top: u16 per 256-tile page = byte offset of the first run that ends in or after it (0xFFFF: none);
    runs: u32 old_start, u16 count, u16 new_start (8 bytes), ending with an old_start of 0xFFFFFFFF"""
    pages = (max(s + c for s, c, _ in runs) + 255) >> 8
    top = []
    for page in range(pages):
        first = 0xFFFF
        for index, (start, count, _) in enumerate(runs):
            if start + count > page << 8:
                first = index * 8
                break
        top.append(first)
    body = b''.join(struct.pack('>IHH', s, c, n) for s, c, n in runs) + struct.pack('>IHH', 0xFFFFFFFF, 0, 0)
    return struct.pack('>%dH' % len(top), *top), body
