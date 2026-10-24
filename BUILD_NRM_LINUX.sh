#!/usr/bin/env sh
set -eu
if [ ! -x "./RecompModTool" ]; then
  echo "ERRO: coloque o RecompModTool oficial nativo para Linux nesta pasta e rode chmod +x RecompModTool"
  exit 1
fi
./RecompModTool mod.toml build
echo "Build concluido. Procure: build/ogre_ptbr_v1_1_complete.nrm"
