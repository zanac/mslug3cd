/* Neo Geo CD probe: vector table and cartridge-style header (copied from the layout of real discs:
   the BIOS owns the exception vectors, the game owns the two interrupts and the four entry jumps). */
	.section .vectors, "ax"
	.long 0x10f300
	.long 0xc00402, 0xc00408, 0xc0040e, 0xc00414
	.long 0xc0041a, 0xc0041a, 0xc0041a, 0xc0041a
	.long 0xc00420, 0xc00426, 0xc00426, 0xc00426
	.long 0xc00426, 0xc00426, 0xc0042c
	.long 0xc00522, 0xc00528, 0xc0052e, 0xc00534
	.long 0xc0053a, 0xc004f2, 0xc004ec, 0xc004e6
	.long 0xc004e0
	.long irq1_handler             /* level 1: acknowledged and ignored (as the real discs do) */
	.long irq2_handler             /* level 2: the vertical blank on the CD: the BIOS's work */

	.section .header, "ax"
	.ascii "NEO-GEO"
	.byte 0
	.word 0x0999                   /* NGH number: not a real game */
	.long 0x00080000
	.org 0x22
	jmp user_entry                 /* USER */
	jmp 0xc00444                   /* PLAYER_START: SYSTEM_RETURN */
	jmp 0xc00444                   /* DEMO_END */
	jmp 0xc00444                   /* COIN_SOUND */

	.text
irq1_handler:
	move.w #2, 0x3c000c            /* REG_IRQACK */
	rte
irq2_handler:
	jmp 0xc00438                   /* SYSTEM_INT1: the BIOS's vertical blank work, it acknowledges by itself */

/* USER: the BIOS calls it with BIOS_USER_REQUEST (0x10fdae) = 0 init, 1 eye catcher, 2 and 3 the game.
   Like the real discs: init and the eye catcher return to the BIOS, the game requests never return. */
user_entry:
	and.w #0xf8ff, %sr             /* interrupts on: the BIOS enters USER with them masked */
	moveq #0, %d0
	move.b 0x10fdae, %d0
	and.w #3, %d0
	cmp.w #2, %d0
	bcc.s run_game
	jmp 0xc00444                   /* SYSTEM_RETURN */
run_game:
	jsr user_main
forever:
	bra.s forever                  /* the vertical blank (BIOS) keeps the screen and the watchdog alive */
