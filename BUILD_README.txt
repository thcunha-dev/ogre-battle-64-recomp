BUILD v68

O build/mod.elf esta compilado e validado deterministicamente.
Para gerar o NRM no Windows, execute GERAR_MOD_PTBR.bat.

Toolchain usada para o ELF:
clang --target=mips-unknown-elf -march=mips2 -mabi=32 -EB -O2 -ffreestanding -fno-pic -mno-abicalls -G0 -Iinclude
ld.lld -m elf32btsmip -T mod.ld --emit-relocs -e 0

SHA-256 ELF:
3f7294f4fcada2fdeff3fce2e8cb3835dc46b59aea40524bd0ddb813b4fe6c35

SHA-256 OBJETO:
b31ca7c126e99f88193053e3ec57603cac1fbece0930c0f97aadc39df3a8e3b3

Build A/B recompilada independentemente e comparada byte a byte: identica.
QA v68: 22 spans LZ + 6 patches estaticos; 27/27 includes historicos preservados; 4569/4569 dialogos preservados.

v1.1 COMPLETE
-------------
A release v1.1 integra também MEMORIES_INDEX, PEOPLE_PROFILES, RECOLLECTIONS e HISTORY_LORE.
ROM de referencia: USA Rev 1, SHA-256 3bfbaf0af968795102f6d136713665e347c22723b4ca75bd5494fdc97df5919e.
A ROM nao e distribuida no pacote.
