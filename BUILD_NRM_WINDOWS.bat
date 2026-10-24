@echo off
cd /d "%~dp0"
RecompModTool.exe mod.toml build
if errorlevel 1 exit /b %errorlevel%
echo Build concluido. Procure: build\ogre_ptbr_v68_language_closure.nrm
