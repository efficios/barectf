MEMORY {
  SDRAM (XRW) : ORIGIN = 0x00000000, LENGTH = 0x08000000
}

/* heap size */
heap_size = 0x10000;

/* define stack base (grows downwards), used in newlib's crt0.S */
__stack = ORIGIN(SDRAM) + LENGTH(SDRAM);

/* libc's entry point */
ENTRY(_mainCRTStartup);

SECTIONS {
  /* QEMU starts executing at 0x10000 */
  . = 0x10000;

  .text : {
    *(.text)
    *(.text.*)
  } > SDRAM

  .data : {
    *(.data)
    *(.data.*)
  } > SDRAM

  .bss : {
    __bss_start__ = .;
    *(.bss)
    *(.bss.*)
    *(COMMON)
    __bss_end__ = .;
  } > SDRAM

  /* "end" symbol needed by newlib's _sbrk */
  end = .;
}
