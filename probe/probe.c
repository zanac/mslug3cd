/* Neo Geo CD hardware probe: shows on the fix layer how the console's 68000 memory really looks,
 * so the Metal Slug 3 port can be designed on facts, not on the documentation.
 *
 * It tests every 64 KB block of 0x000000-0x2FFFFF: is it RAM, and is it the same memory as another
 * block (an alias).  The word it uses is restored, so the BIOS never notices.
 */
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;

#define VRAM_ADDR (*(volatile u16 *)0x3c0000)
#define VRAM_DATA (*(volatile u16 *)0x3c0002)
#define VRAM_MOD  (*(volatile u16 *)0x3c0004)
#define PALETTE   ((volatile u16 *)0x400000)
#define BACKDROP  (*(volatile u16 *)0x401ffe)

#define BLOCKS 48                       /* 0x00-0x2F, 64 KB each */
#define TEST_OFFSET 0x1230              /* the probe word inside a block */

static void put_text(int col, int row, const char *text)
{
    VRAM_MOD = 32;                      /* the fix map is column-major: +32 steps one column right */
    VRAM_ADDR = 0x7000 + col * 32 + row;
    while (*text) VRAM_DATA = (u16)(u8)*text++;
}

static const char hex_digits[] = "0123456789ABCDEF";
static void hex_to_text(char *out, u32 value, int digits)
{
    int i;
    for (i = digits - 1; i >= 0; i--) { out[i] = hex_digits[value & 15]; value >>= 4; }
    out[digits] = 0;
}

static char block_name(int b) { return b < 10 ? '0' + b : b < 36 ? 'A' + b - 10 : 'a' + b - 36; }

/* what a word written at one address shows when read back at another */
static char classify(int b, const u32 tag[], const volatile u32 *probe[])
{
    u32 got = *probe[b];
    int other;
    if (got == tag[b]) return 'R';
    for (other = 0; other < BLOCKS; other++)
        if (other != b && got == tag[other]) return block_name(other);
    return '-';
}

void user_main(void)
{
    u32 tag[BLOCKS], saved[BLOCKS], extra_saved[3];
    const volatile u32 *probe[BLOCKS];
    char map[BLOCKS + 1], text[16], one[2];
    volatile u32 *extra[3];
    int b, n, row;
    u16 old_sr;

    asm volatile ("move.w %%sr, %0\n\tmove.w #0x2700, %%sr" : "=d" (old_sr) :: "memory");   /* nobody interrupts the test */

    PALETTE[0] = 0x8000; PALETTE[1] = 0x7fff;                /* palette 0: transparent, white */
    BACKDROP = 0x0003;                                       /* dark blue */

    for (b = 0; b < BLOCKS; b++) {
        probe[b] = (const volatile u32 *)((u32)b * 0x10000 + TEST_OFFSET);
        tag[b] = 0xA5000000u | ((u32)b << 16) | 0x5AA5;
    }
    /* block 0 holds this program and the vectors; block 0x10 the BIOS's work RAM: neither is touched */
    for (b = 1; b < BLOCKS; b++) if (b != 0x10) saved[b] = *probe[b];
    for (b = 1; b < BLOCKS; b++) if (b != 0x10) *(volatile u32 *)probe[b] = tag[b];
    for (b = 0; b < BLOCKS; b++) map[b] = 'P';
    for (b = 1; b < BLOCKS; b++) if (b != 0x10) map[b] = classify(b, tag, probe);
    map[0x10] = 'W';
    for (b = 1; b < BLOCKS; b++) if (b != 0x10) *(volatile u32 *)probe[b] = saved[b];
    map[BLOCKS] = 0;

    /* the last words of the 1 MB windows: the Metal Slug 3 bank register is at 0x2FFFE4 */
    extra[0] = (volatile u32 *)0x0fffe4; extra[1] = (volatile u32 *)0x1fffe4; extra[2] = (volatile u32 *)0x2fffe4;
    for (n = 0; n < 3; n++) extra_saved[n] = *extra[n];
    for (n = 0; n < 3; n++) *extra[n] = 0x12340000u | n;
    for (n = 0; n < 3; n++) { u32 v = *extra[n]; text[n] = v == (0x12340000u | n) ? 'R' : '-'; }
    text[3] = 0;
    for (n = 0; n < 3; n++) *extra[n] = extra_saved[n];

    put_text(2, 3, "NEO GEO CD PROBE 1");
    put_text(2, 5, "64K BLOCKS 000000-0FFFFF");
    put_text(2, 9, "64K BLOCKS 100000-1FFFFF");
    put_text(2, 13, "64K BLOCKS 200000-2FFFFF");
    for (row = 0; row < 3; row++)
        for (n = 0; n < 16; n++) { one[0] = map[row * 16 + n]; one[1] = 0; put_text(2 + n * 2, 7 + row * 4, one); }
    put_text(2, 17, "P PROGRAM  W BIOS WORK  R RAM");
    put_text(2, 18, "- NO RAM  0-Z ALIAS OF BLOCK");
    put_text(2, 20, "WORD AT 0FFFE4 1FFFE4 2FFFE4:");
    put_text(2, 21, text);
    hex_to_text(text, *(volatile u16 *)0x10fdac, 4);
    put_text(2, 23, "BIOS WORK 10FDAC:");
    put_text(21, 23, text);

    asm volatile ("move.w %0, %%sr" :: "d" (old_sr) : "memory");    /* interrupts back on */
}
