# PowerShell build script for UsisAIn Windows Desktop Launcher & MSI Installer
[CmdletBinding()]
param(
    [switch]$SkipMsi = $false,
    [switch]$SkipZip = $false
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RepoRoot = Split-Path -Parent $ScriptDir

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "         Building UsisAIn Desktop Bundle & Installer     " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Resolve Python executable & ensure build dependencies
$PythonExe = Join-Path $RepoRoot "venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    $PythonExe = "python"
}
Write-Host "[1/6] Using Python: $PythonExe" -ForegroundColor Yellow

$PyInstallerCheck = & $PythonExe -c "import PyInstaller; print('OK')" 2>$null
if ($PyInstallerCheck -ne "OK") {
    Write-Host "      Installing required build tools (PyInstaller)..." -ForegroundColor Yellow
    $ReqBuild = Join-Path $ScriptDir "requirements-build.txt"
    & $PythonExe -m pip install -r $ReqBuild
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to install build dependencies from $ReqBuild"
        exit 1
    }
}

# 2. Generate icons if missing
$IcoFile = Join-Path $ScriptDir "assets\icon.ico"
if (-not (Test-Path $IcoFile)) {
    Write-Host "[2/6] Generating icon assets..." -ForegroundColor Yellow
    & $PythonExe (Join-Path $ScriptDir "tools\make_icons.py")
} else {
    Write-Host "[2/6] Icon assets already generated." -ForegroundColor Green
}

# 3. Build & validate browser extensions
Write-Host "[3/6] Building & validating browser extensions..." -ForegroundColor Yellow
$env:PYTHONPATH = "$ScriptDir;$env:PYTHONPATH"
& $PythonExe (Join-Path $ScriptDir "tools\build_extension.py")
if ($LASTEXITCODE -ne 0) {
    Write-Error "Extension build failed!"
    exit 1
}

# 4. PyInstaller bundle
Write-Host "[4/6] Running PyInstaller to build standalone desktop bundle..." -ForegroundColor Yellow
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

Write-Host "[OK] Desktop app bundle created: $ExePath" -ForegroundColor Green

# 5. Build Windows Installer (.msi)
if (-not $SkipMsi) {
    Write-Host "[5/6] Building Windows MSI Installer (WiX Toolset)..." -ForegroundColor Yellow
    $MsiPath = Join-Path $DistDir "UsisAIn-Setup.msi"
    $WxsPath = Join-Path $ScriptDir "usisain.wxs"

    $WixCmd = Get-Command "wix" -ErrorAction SilentlyContinue
    if (-not $WixCmd) {
        $DotnetCmd = Get-Command "dotnet" -ErrorAction SilentlyContinue
        if ($DotnetCmd) {
            Write-Host "      Installing WiX v5 toolset via dotnet tool..." -ForegroundColor Yellow
            dotnet tool install --global wix --version 5.0.2
            wix extension add WixToolset.UI.wixext/5.0.2
        } else {
            Write-Warning "WiX toolset not found and dotnet CLI is missing. Skipping .msi generation."
        }
    }

    if (Get-Command "wix" -ErrorAction SilentlyContinue) {
        if (Test-Path $MsiPath) {
            Remove-Item -Force $MsiPath
        }
        wix build -arch x64 -b $ScriptDir -ext WixToolset.UI.wixext $WxsPath -o $MsiPath
        if ($LASTEXITCODE -eq 0 -and (Test-Path $MsiPath)) {
            $MsiSizeMB = [math]::Round((Get-Item $MsiPath).Length / 1MB, 2)
            Write-Host "[OK] MSI installer built successfully: $MsiPath ($MsiSizeMB MB)" -ForegroundColor Green
        } else {
            Write-Warning "MSI generation failed with exit code $LASTEXITCODE."
        }
    }
} else {
    Write-Host "[5/6] Skipping MSI generation (-SkipMsi)." -ForegroundColor Gray
}

# 6. Create ZIP package
if (-not $SkipZip) {
    Write-Host "[6/6] Creating release zip archive..." -ForegroundColor Yellow
    $ZipBase = Join-Path $DistDir "UsisAIn-windows-x64"
    $ZipPath = "$ZipBase.zip"
    if (Test-Path $ZipPath) {
        Remove-Item -Force $ZipPath
    }
    & $PythonExe -c "import shutil; shutil.make_archive(r'$ZipBase', 'zip', r'$DistDir', 'UsisAIn')"
    $ZipSizeMB = [math]::Round((Get-Item $ZipPath).Length / 1MB, 2)
    Write-Host "[OK] Created release archive: $ZipPath ($ZipSizeMB MB)" -ForegroundColor Green
} else {
    Write-Host "[6/6] Skipping zip archive (-SkipZip)." -ForegroundColor Gray
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Build Complete!" -ForegroundColor Cyan
if (Test-Path (Join-Path $DistDir "UsisAIn-Setup.msi")) {
    Write-Host " Double-click to install: $(Join-Path $DistDir "UsisAIn-Setup.msi")" -ForegroundColor Green
}
Write-Host " Standalone executable:   $ExePath" -ForegroundColor White
Write-Host "==========================================================" -ForegroundColor Cyan
