#!/usr/bin/env python3
"""Chooses which ADPCM-A samples of a Mission fit the 1 MB PCM RAM of the Neo Geo CD.

usage: ms3_pcm.py TRACE [budget_bytes]
Greedy by plays per byte.  Prints the kept samples (start end plays) and the share of plays covered;
the dropped samples are the ones the Z80 sample table must alias to a kept one (or silence)."""
import sys
import os
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ms3_analyze


def choose(samples, budget):
    plays = defaultdict(int)
    for _, start, end in samples:
        plays[(start, end)] += 1
    size = lambda k: k[1] - k[0] + 1
    kept, used = [], 0
    for k in sorted(plays, key=lambda k: -plays[k] / size(k)):
        if used + size(k) <= budget:
            kept.append(k)
            used += size(k)
    return sorted(kept), used, plays


if __name__ == '__main__':
    trace = sys.argv[1]
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 1 << 20
    _, samples, _, _ = ms3_analyze.read_trace(trace)
    kept, used, plays = choose(samples, budget)
    covered = sum(plays[k] for k in kept)
    for k in kept:
        print('%08x %08x %d' % (k[0], k[1], plays[k]))
    print('# %d of %d samples, %d bytes, %d of %d plays (%.1f%%)' % (
        len(kept), len(plays), used, covered, len(samples), 100.0 * covered / len(samples)), file=sys.stderr)
