@echo off
rem MX-5 RF pour NFS Underground 1 et 2 (Xbox USA, Switch) : fabrique le dossier de la carte SD.
rem MX-5 RF for NFS Underground 1 and 2 (Xbox USA, Switch): makes the SD card folder.
rem Python : celui du PC s'il a numpy et Pillow, sinon une copie portable officielle (python.org)
rem dans le dossier outils\python (rien n'est installe dans Windows).
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set "PY=outils\python\python.exe"
if exist "%PY%" goto run

for %%P in (py python) do (
  %%P -c "import sys, numpy, PIL; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1 && (
    set "PY=%%P"
    goto run
  )
)

echo.
echo Python n'est pas installe (ou sans numpy / Pillow) : je telecharge une copie portable
echo depuis python.org dans outils\python (environ 30 Mo, une seule fois).
echo Python is missing (or has no numpy / Pillow): downloading a portable copy from
echo python.org into outils\python (about 30 MB, only once).
echo.
set "PYVER=3.12.10"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop'; $d='outils\python'; New-Item -ItemType Directory -Force $d | Out-Null;" ^
  "Invoke-WebRequest 'https://www.python.org/ftp/python/%PYVER%/python-%PYVER%-embed-amd64.zip' -OutFile \"$d\py.zip\";" ^
  "Expand-Archive \"$d\py.zip\" $d -Force; Remove-Item \"$d\py.zip\";" ^
  "$pth = Get-ChildItem $d -Filter 'python*._pth' | Select-Object -First 1;" ^
  "(Get-Content $pth.FullName) -replace '^#\s*import site','import site' | Set-Content $pth.FullName;" ^
  "Invoke-WebRequest 'https://bootstrap.pypa.io/get-pip.py' -OutFile \"$d\get-pip.py\""
if errorlevel 1 goto fail
"outils\python\python.exe" "outils\python\get-pip.py" --no-warn-script-location -q
if errorlevel 1 goto fail
"outils\python\python.exe" -m pip install --no-warn-script-location -q numpy pillow
if errorlevel 1 goto fail
set "PY=outils\python\python.exe"

:run
"%PY%" "outils\games\nfs-underground-xbox\fabriquer_sd.py" %* --dossier "%~dp0."
echo.
pause
exit /b

:fail
echo.
echo Echec du telechargement de Python. Installe Python 3 depuis python.org (avec numpy et Pillow :
echo   py -m pip install numpy pillow ) puis relance FABRIQUER.bat.
echo Python download failed. Install Python 3 from python.org (with numpy and Pillow:
echo   py -m pip install numpy pillow ) then run FABRIQUER.bat again.
pause
exit /b 1
