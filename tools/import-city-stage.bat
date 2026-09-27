@echo off
setlocal EnableExtensions

set "REPO=%~dp0.."
set "GGFILES=%USERPROFILE%\Documents\GameGuruApps\GameGuruMAX\Files"
set "RUNTIME_REPO=%REPO%\Files\mapbank\BLACK SIGNAL - District 12.fpm"
set "RUNTIME_REPO_LST=%REPO%\Files\mapbank\BLACK SIGNAL - District 12.lst"
set "RUNTIME_USER=%GGFILES%\mapbank\BLACK SIGNAL - District 12.fpm"
set "RUNTIME_USER_LST=%GGFILES%\mapbank\BLACK SIGNAL - District 12.lst"
set "BOOTSTRAP=%GGFILES%\mapbank\CyberCity.fpm"
set "BOOTSTRAP_LST=%GGFILES%\mapbank\CyberCity.lst"
set "DESTDIR=%REPO%\gameguru\maps"
set "DEST=%DESTDIR%\BLACK SIGNAL - District 12.fpm"
set "DESTLST=%DESTDIR%\BLACK SIGNAL - District 12.lst"

rem Prefer the actually edited District 12 runtime map. The repository-root
rem Files\mapbank mirror is first because this repo is commonly used directly as
rem a GameGuru MAX Separate Project Folder. The user-profile mapbank is second.
rem CyberCity is only an initial bootstrap fallback; it must never silently replace
rem a manually edited District 12 reference when one exists.
set "SRC="
set "SRCLST="
set "MODE="

if exist "%RUNTIME_REPO%" (
    set "SRC=%RUNTIME_REPO%"
    set "SRCLST=%RUNTIME_REPO_LST%"
    set "MODE=repo-runtime District 12"
) else if exist "%RUNTIME_USER%" (
    set "SRC=%RUNTIME_USER%"
    set "SRCLST=%RUNTIME_USER_LST%"
    set "MODE=user-mapbank District 12"
) else if exist "%BOOTSTRAP%" (
    set "SRC=%BOOTSTRAP%"
    set "SRCLST=%BOOTSTRAP_LST%"
    set "MODE=CyberCity bootstrap"
) else (
    echo ERROR: No editable District 12 map or CyberCity bootstrap map was found.
    echo Checked:
    echo   "%RUNTIME_REPO%"
    echo   "%RUNTIME_USER%"
    echo   "%BOOTSTRAP%"
    exit /b 1
)

echo BLACK SIGNAL - District 12 canonical stage capture
echo.
echo Mode:        %MODE%
echo Source:      "%SRC%"
echo Destination: "%DEST%"
echo.

if /I "%MODE%"=="CyberCity bootstrap" (
    echo WARNING: No edited District 12 runtime map exists, so this is bootstrapping from CyberCity.
    echo WARNING: Do not use this mode to capture a manual District 12 correction.
    echo.
)

if not exist "%DESTDIR%" mkdir "%DESTDIR%"

copy /Y "%SRC%" "%DEST%" >nul
if errorlevel 1 (
    echo ERROR: Failed to copy the stage FPM.
    exit /b 1
)

echo Captured current stage map.

rem The canonical .lst is a curated dependency superset used by repository and
rem packaging validation. A GameGuru save can emit a much smaller runtime list,
rem so replacing the canonical list during every manual transform capture can
rem silently delete required kit dependencies. Seed it only when missing.
if exist "%DESTLST%" (
    echo Preserved curated canonical companion list.
) else if exist "%SRCLST%" (
    copy /Y "%SRCLST%" "%DESTLST%" >nul
    if errorlevel 1 (
        echo WARNING: Could not seed companion .lst file.
    ) else (
        echo Seeded canonical companion list from runtime source.
    )
) else (
    echo NOTE: Matching .lst was not found; continuing with the FPM only.
)

pushd "%REPO%"

where git >nul 2>&1
if errorlevel 1 (
    echo WARNING: Git is not on PATH. The map was copied but not staged.
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
echo District 12 canonical source is captured and staged for Git LFS.
echo Review only the staged stage files with:
echo     git status --short
echo     git lfs status
echo.
echo Then commit and push:
echo     git commit -m "Capture manual District 12 reference"
echo     git push

echo.
echo NOTE: Files\mapbank\BLACK SIGNAL - District 12.fpm is intentionally ignored.
echo       gameguru\maps\BLACK SIGNAL - District 12.fpm is the canonical tracked copy.
echo       The canonical .lst is curated and is not replaced by a reduced runtime save list.

popd
endlocal
