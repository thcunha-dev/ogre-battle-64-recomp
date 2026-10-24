# Ogre Battle 64 PT-BR — v1.1 COMPLETE

Projeto de tradução completa para PT-BR de **Ogre Battle 64: Person of Lordly Caliber**, destinado ao projeto `ogre-battle-64-recomp`.

## Estado

Release do projeto: **v1.1 COMPLETE**.

Cobertura declarada no pacote de engenharia:

- 4.569 diálogos;
- interface, ajuda, sistema, tutorial e localidades;
- descrições, glossário e lore;
- `MEMORIES_INDEX`;
- `PEOPLE_PROFILES`;
- `RECOLLECTIONS`;
- `HISTORY_LORE`.

Os nomes de itens, equipamentos, magias, classes e outros jargões permanecem na variante **ORIGINAL NAMES** definida durante o projeto.

## ROM de referência

A engenharia e validação foram realizadas contra **Ogre Battle 64 USA Rev 1**. O pacote original registra SHA-256:

`3bfbaf0af968795102f6d136713665e347c22723b4ca75bd5494fdc97df5919e`

**Nenhuma ROM é distribuída neste repositório.** Use somente uma cópia obtida legalmente.

## Estrutura

- `src/` — runtime e includes da tradução;
- `tools/` — scripts de extração, tradução, auditoria, reflow e fechamento;
- `story_complete/` — dados e relatórios dos quatro bancos narrativos finais;
- `reference/` — referências de símbolos para empacotamento;
- arquivos `DIALOGUE_*`, `LZ_*`, `UI_*`, `VALIDACAO_*`, `AUDITORIA_*` — memória e QA do desenvolvimento;
- `mod.toml` / `mod.ld` — configuração do mod;
- `LEIA-ME-PRIMEIRO.txt` — instruções originais da release.

## Build

O pacote original foi compilado com Clang/LLD para MIPS e empacotado via RecompModTool. Artefatos gerados (`build/`, `.elf`, `.o`, executáveis e ROMs) não fazem parte do código-fonte versionado nesta branch.

## Observação sobre esta importação

Esta branch foi criada a partir do pacote `Ogre_Battle_64_PTBR_v1.1_COMPLETE`, preservando os fontes, ferramentas, CSVs, auditorias e relatórios úteis. Artefatos de build repetíveis foram deliberadamente excluídos do Git.
