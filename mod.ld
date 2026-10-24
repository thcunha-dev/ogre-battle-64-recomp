/* Relocatable N64Recomp mod ELF. Keep relocation records in the final ELF so
   RecompModTool can relocate internal pointers when multiple mods are loaded. */
RAMBASE = 0x81000000;
MEMORY { extram(ARWX) : ORIGIN = RAMBASE, LENGTH = 64M }
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
