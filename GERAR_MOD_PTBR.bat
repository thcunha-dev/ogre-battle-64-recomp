@echo off
cd /d "%~dp0"
echo === Ogre Battle 64 PT-BR v1.1 COMPLETE - gerando NRM ===
RecompModTool.exe mod.toml build > build_log.txt 2>&1
set RC=%ERRORLEVEL%
type build_log.txt
echo.
if not "%RC%"=="0" (
  echo FALHOU com codigo %RC%.
  echo Envie build_log.txt ao ChatGPT para eu corrigir o projeto.
  pause
  exit /b %RC%
)
echo Procurando NRM...
dir /b build\*.nrm 2>nul
if errorlevel 1 (
  echo O tool terminou sem erro mas nenhum NRM apareceu. Envie build_log.txt.
  pause
  exit /b 2
)
echo.
echo SUCESSO. Copie o arquivo .nrm acima para a pasta mods do Ogre Battle 64 Recomp.
pause
