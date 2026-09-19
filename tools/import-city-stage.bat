@echo off
setlocal EnableExtensions

set "REPO=%~dp0.."
set "GGFILES=%USERPROFILE%\Documents\GameGuruApps\GameGuruMAX\Files"
set "SRC=%GGFILES%\mapbank\CyberCity.fpm"
set "SRCLST=%GGFILES%\mapbank\CyberCity.lst"
set "DESTDIR=%REPO%\gameguru\maps"
set "DEST=%DESTDIR%\BLACK SIGNAL - District 12.fpm"
set "DESTLST=%DESTDIR%\BLACK SIGNAL - District 12.lst"

echo BLACK SIGNAL - District 12 stage importer
echo.
echo Source:      "%SRC%"
echo Destination: "%DEST%"
echo.

if not exist "%SRC%" (
    echo ERROR: CyberCity.fpm was not found.
    echo Expected: "%SRC%"
    exit /b 1
)

if not exist "%DESTDIR%" mkdir "%DESTDIR%"

copy /Y "%SRC%" "%DEST%" >nul
if errorlevel 1 (
    echo ERROR: Failed to copy CyberCity.fpm.
    exit /b 1
)

echo Copied city stage map.

if exist "%SRCLST%" (
    copy /Y "%SRCLST%" "%DESTLST%" >nul
    if errorlevel 1 (
        echo WARNING: Could not copy CyberCity.lst.
    ) else (
        echo Copied companion list file.
    )
) else (
    echo NOTE: CyberCity.lst was not found; continuing with the FPM only.
)

pushd "%REPO%"

where git >nul 2>&1
if errorlevel 1 (
    echo WARNING: Git is not on PATH. The files were copied but not staged.
    popd
    exit /b 0
)

where git-lfs >nul 2>&1
if errorlevel 1 (
    echo WARNING: Git LFS is not on PATH.
    echo Install Git LFS before committing the .fpm file.
    popd
    exit /b 0
)

git lfs install >nul
git lfs track "*.fpm"

git add .gitattributes
git add "gameguru/maps/BLACK SIGNAL - District 12.fpm"
if exist "gameguru\maps\BLACK SIGNAL - District 12.lst" git add "gameguru/maps/BLACK SIGNAL - District 12.lst"

echo.
echo District 12 is copied and staged for Git.
echo Review with:
echo     git status
echo.
echo Then commit and push:
echo     git commit -m "Add District 12 city production stage"
echo     git push

popd
endlocal
