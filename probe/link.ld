OUTPUT_FORMAT(binary)
SECTIONS {
  . = 0;
  .vectors : { *(.vectors) }
  . = 0x100;
  .header : { *(.header) }
  . = 0x200;
  .text : { *(.text .text.*) }
  .rodata : { *(.rodata .rodata.*) }
  .data : { *(.data .data.*) }
  .bss : { *(.bss .bss.*) }
}
