# NOTE: work in progress - MAME (neocd, bios "top") still stays in the CD player with discs made by this script.
"""Build a Neo Geo CD test disc: IPL.TXT + program file -> ISO -> BIN/CUE -> CHD."""
import sys, io, pycdlib, subprocess, struct
prg = open(sys.argv[1],'rb').read()
iso = pycdlib.PyCdlib(); iso.new(interchange_level=1, sys_ident='', vol_ident='NEOGEOCD', abstract_file='/ABS.TXT;1', bibli_file='/BIB.TXT;1', copyright_file='/CPY.TXT;1')
ipl = b"T.PRG,0,0\r\n\x1a"
iso.add_fp(io.BytesIO(ipl), len(ipl), '/IPL.TXT;1')
for name,txt in (('ABS','Abstracted by SNK corporation'),('BIB','Bibliographiced by SNK corporation'),('CPY','Copyright by SNK corporation')):
    b=(txt+'\r\n\x1a').encode(); iso.add_fp(io.BytesIO(b), len(b), '/%s.TXT;1'%name)
iso.add_fp(io.BytesIO(prg), len(prg), '/T.PRG;1')
iso.write('t.iso'); iso.close()
data = bytearray(open('t.iso','rb').read())
for off,name in ((702,'CPY.TXT'),(739,'ABS.TXT'),(776,'BIB.TXT')):   # the BIOS wants plain names in the PVD
    data[16*2048+off:16*2048+off+37] = name.encode().ljust(37)
# 2048-byte ISO -> raw MODE1 2352 sectors (sync, header, data, zeroed EDC/ECC: MAME's chd reader does not check them)
out = bytearray()
for i in range(len(data)//2048):
    m,s,f = divmod(i+150, 75*60)[0], divmod(divmod(i+150,75)[0],60)[1], (i+150)%75
    out += b'\x00'+b'\xff'*10+b'\x00' + bytes([int('%02d'%m,16),int('%02d'%s,16),int('%02d'%f,16),1]) + data[i*2048:(i+1)*2048] + bytes(280)
open('t.bin','wb').write(out)
open('a.bin','wb').write(bytes(2352*75*3))   # 3 s of audio silence as track 2: game discs always have CD-DA tracks
nsec = len(out)//2352; msf = '%02d:%02d:%02d' % (nsec//4500, nsec//75%60, nsec%75)
open('t.cue','w').write('FILE "t.bin" BINARY\n  TRACK 01 MODE1/2352\n    INDEX 01 00:00:00\nFILE "a.bin" BINARY\n  TRACK 02 AUDIO\n    PREGAP 00:02:00\n    INDEX 01 00:00:00\n')
subprocess.run(['rm','-f','t.chd']); subprocess.check_call(['chdman','createcd','-i','t.cue','-o','t.chd'])
