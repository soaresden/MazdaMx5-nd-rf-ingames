# MX-5 RF for NFS Underground 1 and 2 (Xbox USA, Switch): opens the page that makes the SD card folder.
# Python: the PC's own if it has numpy and Pillow, otherwise an official portable copy (python.org)
# in outils\python (nothing is installed in Windows). The page runs on this PC only (127.0.0.1).
# Start it with FABRIQUER.cmd (double-click), or right-click this file > Run with PowerShell.
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$Host.UI.RawUI.WindowTitle = 'MX-5 RF - NFS Underground'

function Test-Python($exe) {
    try {
        & $exe -c "import sys, numpy, PIL; sys.exit(0 if sys.version_info >= (3, 9) else 1)" 2>$null | Out-Null
        return $LASTEXITCODE -eq 0
    } catch { return $false }
}

$py = Join-Path $PSScriptRoot 'outils\python\python.exe'
if (-not (Test-Path $py)) {
    $py = $null
    foreach ($c in 'py', 'python') {
        if ((Get-Command $c -ErrorAction SilentlyContinue) -and (Test-Python $c)) { $py = $c; break }
    }
}
if (-not $py) {
    Write-Host ''
    Write-Host 'Python est absent (ou sans numpy / Pillow) : je telecharge une copie portable depuis python.org'
    Write-Host 'dans outils\python (environ 30 Mo, une seule fois).'
    Write-Host 'Python is missing (or has no numpy / Pillow): downloading a portable copy from python.org'
    Write-Host 'into outils\python (about 30 MB, only once).'
    Write-Host ''
    try {
        $ver = '3.12.10'
        $d = Join-Path $PSScriptRoot 'outils\python'
        New-Item -ItemType Directory -Force $d | Out-Null
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest "https://www.python.org/ftp/python/$ver/python-$ver-embed-amd64.zip" -OutFile "$d\py.zip" -UseBasicParsing
        Expand-Archive "$d\py.zip" $d -Force
        Remove-Item "$d\py.zip"
        $pth = Get-ChildItem $d -Filter 'python*._pth' | Select-Object -First 1
        (Get-Content $pth.FullName) -replace '^#\s*import site', 'import site' | Set-Content $pth.FullName
        Invoke-WebRequest 'https://bootstrap.pypa.io/get-pip.py' -OutFile "$d\get-pip.py" -UseBasicParsing
        & "$d\python.exe" "$d\get-pip.py" --no-warn-script-location -q
        if ($LASTEXITCODE -ne 0) { throw 'get-pip' }
        & "$d\python.exe" -m pip install --no-warn-script-location -q numpy pillow
        if ($LASTEXITCODE -ne 0) { throw 'pip install' }
        $py = "$d\python.exe"
    } catch {
        Write-Host ''
        Write-Host "Echec du telechargement de Python ($_). Installe Python 3 depuis python.org, puis :"
        Write-Host '  py -m pip install numpy pillow    et relance FABRIQUER.'
        Write-Host "Python download failed ($_). Install Python 3 from python.org, then:"
        Write-Host '  py -m pip install numpy pillow    and start FABRIQUER again.'
        Read-Host 'Entree / Enter'
        exit 1
    }
}

Write-Host 'La page s''ouvre dans ton navigateur. Laisse cette fenetre ouverte tant que tu t''en sers.'
Write-Host 'The page opens in your browser. Keep this window open while you use it.'
& $py (Join-Path $PSScriptRoot 'outils\games\nfs-underground-xbox\ui_server.py') --dossier $PSScriptRoot
