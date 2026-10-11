# PowerShell build script for UsisAIn Windows Desktop Launcher
[CmdletBinding()]
param(
    [switch]$SkipZip = $false
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RepoRoot = Split-Path -Parent $ScriptDir

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "         Building UsisAIn Desktop Bundle (Windows)       " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Resolve Python executable
$PythonExe = Join-Path $RepoRoot "venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    $PythonExe = "python"
}
Write-Host "[1/5] Using Python: $PythonExe" -ForegroundColor Yellow

# 2. Generate icons if missing
$IcoFile = Join-Path $ScriptDir "assets\icon.ico"
if (-not (Test-Path $IcoFile)) {
    Write-Host "[2/5] Generating icon assets..." -ForegroundColor Yellow
    & $PythonExe (Join-Path $ScriptDir "tools\make_icons.py")
} else {
    Write-Host "[2/5] Icon assets already generated." -ForegroundColor Green
}

# 3. Build & validate browser extensions
Write-Host "[3/5] Building & validating browser extensions..." -ForegroundColor Yellow
$env:PYTHONPATH = "$ScriptDir;$env:PYTHONPATH"
& $PythonExe (Join-Path $ScriptDir "tools\build_extension.py")
if ($LASTEXITCODE -ne 0) {
    Write-Error "Extension build failed!"
    exit 1
}

# 4. PyInstaller bundle
Write-Host "[4/5] Running PyInstaller to build standalone desktop bundle..." -ForegroundColor Yellow
$DistDir = Join-Path $ScriptDir "dist"
$WorkDir = Join-Path $ScriptDir "build\pyinstaller"

& $PythonExe -m PyInstaller `
    --distpath $DistDir `
    --workpath $WorkDir `
    --noconfirm `
    --clean `
    (Join-Path $ScriptDir "usisain.spec")

if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller build failed!"
    exit 1
}

$ExePath = Join-Path $DistDir "UsisAIn\UsisAIn.exe"
if (-not (Test-Path $ExePath)) {
    Write-Error "Build output missing: $ExePath"
    exit 1
}

Write-Host "[OK] Desktop app built successfully: $ExePath" -ForegroundColor Green

# 5. Create ZIP package
if (-not $SkipZip) {
    Write-Host "[5/5] Creating release zip archive..." -ForegroundColor Yellow
    $ZipBase = Join-Path $DistDir "UsisAIn-windows-x64"
    $ZipPath = "$ZipBase.zip"
    if (Test-Path $ZipPath) {
        Remove-Item -Force $ZipPath
    }
    & $PythonExe -c "import shutil; shutil.make_archive(r'$ZipBase', 'zip', r'$DistDir', 'UsisAIn')"
    $ZipSizeMB = [math]::Round((Get-Item $ZipPath).Length / 1MB, 2)
    Write-Host "[OK] Created release archive: $ZipPath ($ZipSizeMB MB)" -ForegroundColor Green
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Build Complete! Run: $ExePath" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
