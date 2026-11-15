# Metal Slug 3 on Neo Geo CD: study of Mission 1

All figures come from a scripted run of the arcade game (set `mslug3`, mame2003-plus with the
tracing patch `tools/ms3_trace_core.patch`, driver `tools/ms3_run.c`, analysis
`tools/ms3_analyze.py`). The bot plays Mission 1 from the start (beach, jungle, truck, boss) in
about 4.6 minutes of game time; the run is deterministic. Nothing from the ROMs is stored here.

## Neo Geo CD limits

| | Neo Geo CD | Source |
|---|---|---|
| 68000 program RAM | 2 MB | neogeodev wiki, DRAM |
| Sprite (C) RAM | 4 MB = 32768 tiles of 16x16 | same |
| PCM (ADPCM) RAM | 1 MB | same |
| Z80 RAM | 64 KB | same |
| Drive | x1 150 kB/s (x2 300 kB/s on the CDZ); each load 4.5 s + 0.65 s per file, seek up to 4 s | neogeodev wiki, Loading time |

## What Mission 1 uses

| | Measured in Mission 1 | Limit | Verdict |
|---|---|---|---|
| Sprite tiles | 20,665 distinct = 2.5 MB; a soldier adds 0.05-0.1 MB | 4 MB | fits in one load |
| ADPCM-A samples | 159 distinct, 2.4 MB (ADPCM-B not measured yet) | 1 MB | does NOT fit: needs a cut |
| Program ROM touched | 0.46 MB in 256-byte pages (0.2 MB fixed + 0.26 MB banked) | 2 MB | fits if the banking is solved |
| Program bank switches | about 2,100 a second (36 a frame), 36 different banks | one 1 MB window | the real problem |

## The bank window

The arcade board has a bank-switched 1 MB window at `0x200000`; the game switches it
constantly (the register at `0x2fffe4`, from a few generic routines). The Neo Geo CD has no
bank register: the window is plain RAM. In Mission 1 only 451 pages of 256 bytes (0.11 MB) of the
window are used; 204 of them are used by one bank only, but 247, all in the first 128 KB of the
window, hold different content in different banks (up to 6). They cannot just be merged into a
single image: either those entry areas are moved to unique addresses (patching the tables
and calls that point to them) or the bank switch is replaced by a cheap software switch. A copy
at each switch would cost far too much (36 switches a frame).

## Next steps for the proof of concept

1. Find how the games enters the banks (the generic routines at `0x1b81c`, `0x1b980`,
   `0x1bab8`, `0x1bad4`, `0xde68`, `0xf69c`, `0x11078`, `0x1289c`) and what is in the 247
   conflicting pages.
2. Build a flat program image of Mission 1 for the CD (fixed part + relocated banked parts).
3. Sprite RAM: one load of the 2.5-3 MB of Mission 1 tiles; renumber the tiles in the tables.
4. Sound: music as CD audio tracks recorded from the emulator; the 2.4 MB of samples cut to 1 MB.
5. ISO and CD loader, test on the emulator and on a real machine.

## Where tile numbers are written (Mission 1 bot run)

Instrumented the video-RAM data port (tile words, VRAM < 0x7000): 271 distinct
68000 addresses write them, 1.18 M writes in 12,000 frames, **all inside the fixed
ROM region (< 0x100000)**, none in the banked window. 181 sites cover 99 % of the
writes; the hottest routines sit at 0xe0b0-0xe0ca, 0x112c2-0x112da, 0x768e,
0xe364-0xe372 and 0x11576-0x11580.

Consequence: tile renumbering (needed because the 32768-tile DRAM is smaller than
the 0x62000-tile address space) cannot be done in the banked data alone, but it can
be done in a small number of fixed-region routines. Two options remain open:
patch the ~270 write sites to go through a lookup table, or renumber the static
tile references in the data. The first is mechanical and verifiable with the
frame-by-frame oracle.

## Neo Geo CD boot test bench (work in progress)

With the user's NGCD BIOS (top-loading `top-sp1.bin`, the universe one is `uni-bioscd33`)
MAME's `neocd` driver runs headless: `mame neocd -rompath <dir> -cdrom disc.chd -bios top
-video none`, and `-debug -debugscript` with a `trace` command gives a full 68000 trace.
Findings from the BIOS code (byte-swapped dump, disassembled with m68k objdump):

* the disc check (state 3 of the BIOS state machine at 0xc1dc/0xe8a6) compares the
  ISO PVD (`CD001`), then reads the files named `CPY.TXT`, `BIB.TXT`, `ABS.TXT` and
  expects their text to start with `Copyright` / `Bibliographiced` / `Abstracted`,
  followed by ` by SNK corporation`; the PVD copyright/abstract/bibliographic fields
  must hold the plain names (`tools/ngcd_mkdisc.py` writes them);
* with a disc built that way the BIOS still polls the drive status (byte 0x10f7fa
  stays 0, so the check never starts): the drive is not reported as holding a disc.
  Not solved yet; a known-good NGCD image is needed to compare the format.
