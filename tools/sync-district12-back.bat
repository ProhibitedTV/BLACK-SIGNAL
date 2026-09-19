@echo off
setlocal

set "REPO=%~dp0.."
set "MAPBANK=%USERPROFILE%\Documents\GameGuruApps\GameGuruMAX\Files\mapbank"
set "SRC_FPM=%MAPBANK%\BLACK SIGNAL - District 12.fpm"
set "SRC_LST=%MAPBANK%\BLACK SIGNAL - District 12.lst"
set "DST_DIR=%REPO%\gameguru\maps"
set "DST_FPM=%DST_DIR%\BLACK SIGNAL - District 12.fpm"
set "DST_LST=%DST_DIR%\BLACK SIGNAL - District 12.lst"

if not exist "%SRC_FPM%" (
  echo ERROR: GameGuru production map was not found:
  echo   %SRC_FPM%
  exit /b 1
)

if not exist "%DST_DIR%" mkdir "%DST_DIR%"

copy /Y "%SRC_FPM%" "%DST_FPM%" >nul
if errorlevel 1 (
  echo ERROR: Failed to copy the District 12 .fpm back into the repository.
  exit /b 1
)

if exist "%SRC_LST%" (
  copy /Y "%SRC_LST%" "%DST_LST%" >nul
)

echo.
echo District 12 synced back from GameGuru MAX.
echo.

git -C "%REPO%" add "gameguru/maps/BLACK SIGNAL - District 12.fpm"
if exist "%DST_LST%" git -C "%REPO%" add "gameguru/maps/BLACK SIGNAL - District 12.lst"

echo Staged changes:
git -C "%REPO%" status --short -- "gameguru/maps/BLACK SIGNAL - District 12.fpm" "gameguru/maps/BLACK SIGNAL - District 12.lst"
echo.
echo Review the staged map before committing.
echo Suggested commit:
echo   git commit -m "Dress District 12 Arrival Boulevard for Shot 001"
echo   git push

endlocal
