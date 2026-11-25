@echo off
setlocal
pushd "%~dp0" || exit /b 1
python -m PyInstaller --noconfirm --onedir --windowed --name EDLstamps --icon "%CD%\assets\app-logo.ico" --add-data "%CD%\assets\app-logo.png:assets" --workpath build\qt --specpath build\qt --distpath dist\qt "%CD%\edlstamps.py"
set "BUILD_RESULT=%ERRORLEVEL%"
popd
exit /b %BUILD_RESULT%
