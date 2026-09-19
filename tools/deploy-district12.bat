@echo off
setlocal EnableExtensions

set "REPO_MAP=%~dp0..\gameguru\maps\BLACK SIGNAL - District 12.fpm"
set "REPO_LST=%~dp0..\gameguru\maps\BLACK SIGNAL - District 12.lst"
set "GGMAX=%USERPROFILE%\Documents\GameGuruApps\GameGuruMAX\Files\mapbank"
set "DEST_MAP=%GGMAX%\BLACK SIGNAL - District 12.fpm"
set "DEST_LST=%GGMAX%\BLACK SIGNAL - District 12.lst"

if not exist "%REPO_MAP%" (
  echo ERROR: Repo map not found:
  echo   %REPO_MAP%
  exit /b 1
)

if not exist "%GGMAX%" (
  echo ERROR: GameGuru MAX mapbank not found:
  echo   %GGMAX%
  exit /b 1
)

for /f "tokens=1-4 delims=/ " %%a in ('date /t') do set DATESTAMP=%%d-%%b-%%c
for /f "tokens=1-3 delims=:., " %%a in ("%time%") do set TIMESTAMP=%%a%%b%%c
set "BACKUP=%GGMAX%\_black_signal_deploy_backups\%DATESTAMP%_%TIMESTAMP%"

if exist "%DEST_MAP%" (
  mkdir "%BACKUP%" >nul 2>&1
  copy /y "%DEST_MAP%" "%BACKUP%\BLACK SIGNAL - District 12.fpm" >nul
  if exist "%DEST_LST%" copy /y "%DEST_LST%" "%BACKUP%\BLACK SIGNAL - District 12.lst" >nul
  echo Backed up existing District 12 map to:
  echo   %BACKUP%
)

copy /y "%REPO_MAP%" "%DEST_MAP%" >nul
if errorlevel 1 (
  echo ERROR: Failed to deploy FPM.
  exit /b 1
)

if exist "%REPO_LST%" copy /y "%REPO_LST%" "%DEST_LST%" >nul

echo.
echo District 12 deployed to GameGuru MAX:
echo   %DEST_MAP%
echo.
echo Open "BLACK SIGNAL - District 12" in GameGuru MAX.
echo Block Arrival Boulevard using:
echo   gameguru\maps\DISTRICT-12-ARRIVAL-BOULEVARD.md
echo.
exit /b 0
