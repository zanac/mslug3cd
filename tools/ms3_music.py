#!/usr/bin/env python3
"""Cuts the music-only recording of a run (raw 16-bit stereo 48 kHz, ADPCM-A muted) into CD-DA audio.

usage: ms3_music.py raw48k.raw out.raw start_seconds end_seconds
Writes raw 16-bit stereo 44.1 kHz padded to whole 2352-byte sectors (what ngcd_disc.write_disc takes as audio)."""
import subprocess
import sys


def cut(source, target, start, end):
    pcm = subprocess.check_output(['ffmpeg', '-v', 'error', '-f', 's16le', '-ar', '48000', '-ac', '2', '-ss', str(start),
                                   '-t', str(end - start), '-i', source, '-f', 's16le', '-ar', '44100', '-ac', '2', '-'])
    pcm += bytes(-len(pcm) % 2352)
    open(target, 'wb').write(pcm)
    return len(pcm) // 2352


if __name__ == '__main__':
    sectors = cut(sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4]))
    print('%d sectors, %.1f s' % (sectors, sectors / 75))
