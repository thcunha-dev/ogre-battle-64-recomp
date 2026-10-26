/* Relocatable link script for Knight of Danika gameplay smoke test. */
RAMBASE = 0x81000000;

MEMORY {
    extram(ARWX) : ORIGIN = RAMBASE, LENGTH = 64M
}

SECTIONS {
    /DISCARD/ : {
        *(.got)
        *(.MIPS.abiflags)
        *(.reginfo)
        *(.pdr)
        *(.comment)
        *(.note)
    }
}
