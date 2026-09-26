# Eye Contact setup for an NVIDIA RTX laptop (NVIDIA Maxine AR SDK, Gaze Redirection).
# Run it through "Setup Eye Contact (RTX).bat". Safe to run again: finished steps are skipped.
# Your NGC API key is typed by you, used only inside this window and never saved.
param(
    [string]$SdkRoot = '',
    [switch]$Rebuild
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Tools = Join-Path $Root 'tools\maxine'
$Features = @('nvARGazeRedirection', 'nvARLandmarkDetection', 'nvARFaceBoxDetection')
$NgcSdkPage = 'https://catalog.ngc.nvidia.com/orgs/nvidia/teams/maxine/collections/maxine_ar_sdk'
$NgcKeyPage = 'https://org.ngc.nvidia.com/setup/api-key'
$SamplesRepo = 'https://github.com/NVIDIA-Maxine/AR-SDK-Samples'

function Say($text) { Write-Host $text -ForegroundColor Cyan }
function Good($text) { Write-Host "  OK  $text" -ForegroundColor Green }
function Stop-Setup($text) { Write-Host ""; Write-Host $text -ForegroundColor Red; exit 1 }
function Ask-Yes($question) { (Read-Host "$question [Y/n]") -notmatch '^[nN]' }
function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
}
function Has($command) { [bool](Get-Command $command -ErrorAction SilentlyContinue) }

New-Item -ItemType Directory -Force $Tools | Out-Null

# 1. GPU ---------------------------------------------------------------------------------------------
Say '1/6  Checking the GPU'
$line = $null
if (Has 'nvidia-smi') {
    $line = & nvidia-smi --query-gpu=name,compute_cap,driver_version --format=csv,noheader 2>$null | Select-Object -First 1
}
if (-not $line) { Stop-Setup 'No NVIDIA GPU or driver found. Install the latest NVIDIA Studio or Game Ready driver, then run this again.' }
$parts = $line.Split(',') | ForEach-Object { $_.Trim() }
$GpuName = $parts[0]; $Compute = $parts[1]; $Driver = $parts[2]
if ($GpuName -notmatch 'RTX') { Stop-Setup "$GpuName has no Tensor Cores. NVIDIA Eye Contact needs an RTX GPU (RTX 20/30/40/50)." }
$Arch = $Compute -replace '\.', ''
Good "$GpuName  (compute $Compute -> -gpu $Arch, driver $Driver)"

# 2. Build tools ---------------------------------------------------------------------------------------
Say '2/6  Checking Git, Git LFS, CMake and Visual Studio C++'
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
function Find-VS {
    if (-not (Test-Path $vswhere)) { return $null }
    & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
}
$missing = @()
if (-not (Has 'git')) { $missing += @{ name = 'Git'; id = 'Git.Git'; extra = '' } }
if (-not (Has 'git-lfs')) { $missing += @{ name = 'Git LFS'; id = 'GitHub.GitLFS'; extra = '' } }
if (-not (Has 'cmake')) { $missing += @{ name = 'CMake'; id = 'Kitware.CMake'; extra = '' } }
if (-not (Find-VS)) {
    $missing += @{ name = 'Visual Studio 2022 Build Tools (C++)'; id = 'Microsoft.VisualStudio.2022.BuildTools';
                   extra = '--override "--wait --passive --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"' }
}
if ($missing.Count -gt 0) {
    Write-Host ('  Missing: ' + (($missing | ForEach-Object { $_.name }) -join ', ')) -ForegroundColor Yellow
    if (-not (Has 'winget')) { Stop-Setup 'Install the missing tools above (winget is not available), then run this again.' }
    if (-not (Ask-Yes '  Install them now with winget (free, from Microsoft/official sources)?')) {
        Stop-Setup 'Install the missing tools, then run this again.'
    }
    foreach ($tool in $missing) {
        Say "  Installing $($tool.name)..."
        $wingetArgs = "install --id $($tool.id) -e --accept-package-agreements --accept-source-agreements $($tool.extra)"
        Start-Process winget -ArgumentList $wingetArgs -Wait -NoNewWindow
    }
    Refresh-Path
    if (-not (Has 'git') -or -not (Has 'cmake') -or -not (Find-VS)) {
        Stop-Setup 'Some tools are still missing. Close this window, open a new one and run the setup again.'
    }
}
Good 'Git, Git LFS, CMake, Visual Studio C++'

# 3. NVIDIA AR SDK core --------------------------------------------------------------------------------------
Say '3/6  Finding the NVIDIA AR SDK'
function Test-Sdk($path) {
    $path -and (Test-Path (Join-Path $path 'features\install_feature.ps1'))
}
$candidates = @($SdkRoot, (Join-Path $Tools 'ARSDK'), 'C:\Program Files\NVIDIA Corporation\NVIDIA AR SDK')
$candidates += Get-ChildItem $Tools -Directory -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName }
$Sdk = $candidates | Where-Object { Test-Sdk $_ } | Select-Object -First 1
if (-not $Sdk) {
    # a zip extracted one level deeper (ARSDK\<something>\features)
    $Sdk = Get-ChildItem $Tools -Recurse -Filter install_feature.ps1 -ErrorAction SilentlyContinue |
        Select-Object -First 1 | ForEach-Object { Split-Path -Parent $_.DirectoryName }
}
while (-not $Sdk) {
    Write-Host ''
    Write-Host '  The NVIDIA AR SDK (Windows) is not on this laptop yet. You need a free NVIDIA account:' -ForegroundColor Yellow
    Write-Host "   1. The NGC page opens now. Sign in, open 'Getting Started' and download the Windows AR SDK zip."
    Write-Host "   2. Extract the zip into:  $Tools\ARSDK"
    Start-Process $NgcSdkPage
    $answer = Read-Host '  Press Enter when it is extracted (or paste the SDK folder path)'
    if ($answer -and (Test-Sdk $answer.Trim('"'))) { $Sdk = $answer.Trim('"') }
    elseif (Test-Sdk (Join-Path $Tools 'ARSDK')) { $Sdk = Join-Path $Tools 'ARSDK' }
    else {
        $Sdk = Get-ChildItem $Tools -Recurse -Filter install_feature.ps1 -ErrorAction SilentlyContinue |
            Select-Object -First 1 | ForEach-Object { Split-Path -Parent $_.DirectoryName }
        if (-not $Sdk) { Write-Host '  Not found yet (looking for features\install_feature.ps1).' -ForegroundColor Yellow }
    }
}
$Sdk = (Resolve-Path $Sdk).Path
Get-ChildItem $Sdk -Recurse -Include *.ps1, *.dll, *.exe -ErrorAction SilentlyContinue | Unblock-File
Good "AR SDK: $Sdk"

# 4. Features (need an NGC API key) --------------------------------------------------------------------------
Say '4/6  Installing the Eye Contact features for your GPU'
$needed = $Features | Where-Object { -not (Test-Path (Join-Path $Sdk ("features\" + $_.ToLower()))) }
if ($needed) {
    $typedKey = $false
    if (-not $env:NGC_CLI_API_KEY) {
        Write-Host "  NVIDIA needs your personal NGC API key (make one at $NgcKeyPage)." -ForegroundColor Yellow
        Write-Host '  It is used only in this window and never saved.'
        Start-Process $NgcKeyPage
        $secure = Read-Host '  Paste your NGC API key' -AsSecureString
        $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        try { $env:NGC_CLI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
        finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
        $typedKey = $true
    }
    try {
        Push-Location (Join-Path $Sdk 'features')
        foreach ($feature in $needed) {
            Say "  Downloading $feature for -gpu $Arch ..."
            & .\install_feature.ps1 -gpu $Arch -features $feature.ToLower()
            if (-not (Test-Path (Join-Path $Sdk ("features\" + $feature.ToLower())))) {
                Stop-Setup "Could not install $feature. Check the NGC key and your internet, then run this again."
            }
        }
    }
    finally {
        Pop-Location
        if ($typedKey) { Remove-Item Env:\NGC_CLI_API_KEY -ErrorAction SilentlyContinue }
    }
}
Good ('Features: ' + ($Features -join ', '))

# 5. Build NVIDIA's Gaze Redirection app ------------------------------------------------------------------------
Say '5/6  Building the Eye Contact engine (GazeRedirectionApp)'
$Samples = Join-Path $Tools 'AR-SDK-Samples'
$Build = Join-Path $Samples 'build'
& git lfs install | Out-Null
if (-not (Test-Path (Join-Path $Samples '.git'))) {
    & git clone --depth 1 $SamplesRepo $Samples
    if ($LASTEXITCODE -ne 0) { Stop-Setup 'Could not download the NVIDIA sample apps (git clone failed).' }
}
& git -C $Samples lfs pull
$exe = Get-ChildItem $Build -Recurse -Filter GazeRedirectionApp.exe -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match '\\Release\\' } | Select-Object -First 1
if ($Rebuild -or -not $exe) {
    & cmake -S $Samples -B $Build -A x64 "-DARSDK_ROOT=$Sdk"
    if ($LASTEXITCODE -ne 0) { Stop-Setup 'CMake could not configure the NVIDIA samples (see the messages above).' }
    & cmake --build $Build --config Release --target GazeRedirectionApp
    if ($LASTEXITCODE -ne 0) { Stop-Setup 'Building GazeRedirectionApp failed (see the messages above).' }
    $exe = Get-ChildItem $Build -Recurse -Filter GazeRedirectionApp.exe |
        Where-Object { $_.FullName -match '\\Release\\' } | Select-Object -First 1
}
if (-not $exe) { Stop-Setup 'GazeRedirectionApp.exe was not produced by the build.' }
Good "Engine: $($exe.FullName)"

# 6. Save the paths and test ---------------------------------------------------------------------------------
Say '6/6  Saving the setup and testing'
$runBat = Join-Path $exe.DirectoryName 'run_gazeredirectionapp_offline.bat'
$pathDirs = @(); $modelDir = Join-Path $Sdk 'bin\models'
if (Test-Path $runBat) {
    $text = Get-Content $runBat -Raw
    if ($text -match 'SET\s+"?PATH=([^"\r\n]*)') {
        $pathDirs = $Matches[1].Split(';') | Where-Object { $_ -and $_ -notmatch '%PATH%' }
    }
    if ($text -match '--model_path="?([^"\r\n]+?)"?(\s|$)') { $modelDir = $Matches[1] }
}
# fallbacks: the SDK and feature DLLs, NVIDIA's bundled OpenCV and the engine's own folder
$pathDirs += Join-Path $Sdk 'bin'
$pathDirs += Get-ChildItem (Join-Path $Sdk 'features') -Directory | ForEach-Object { Join-Path $_.FullName 'bin' }
$pathDirs += Join-Path $Samples 'external\opencv\x64\bin'
$pathDirs += $exe.DirectoryName
$pathDirs = @($pathDirs | Where-Object { Test-Path $_ } | Select-Object -Unique)
$config = [ordered]@{
    app_exe   = $exe.FullName
    sdk_root  = $Sdk
    model_dir = $modelDir
    path_dirs = @($pathDirs)
    gpu       = $GpuName
    gpu_arch  = $Arch
    driver    = $Driver
    set_up    = (Get-Date -Format 'yyyy-MM-dd HH:mm')
}
$configPath = Join-Path $Root 'config.eyecontact.local.json'
[IO.File]::WriteAllText($configPath, ($config | ConvertTo-Json -Depth 3), (New-Object Text.UTF8Encoding $false))
Good "Saved $configPath"

$sample = Join-Path $exe.DirectoryName 'eyeContact.mp4'
if (Test-Path $sample) {
    Say '  Test run on NVIDIA''s sample clip...'
    $env:Path = (($pathDirs + $env:Path) -join ';')
    $out = Join-Path $env:TEMP 'hinglish-eyecontact-test.avi'
    Remove-Item $out -ErrorAction SilentlyContinue
    Push-Location $exe.DirectoryName
    & $exe.FullName "--model_path=$modelDir" --offline_mode --split_screen_view=false --draw_visualization=false `
        --temporal --landmarks_126 --in=eyeContact.mp4 "--out=$out" --codec=MJPG
    Pop-Location
    if ((Test-Path $out) -and (Get-Item $out).Length -gt 100000) { Good 'NVIDIA Eye Contact works on this GPU' }
    else { Stop-Setup 'The test run did not produce a video. Update the NVIDIA driver and run this again.' }
    Remove-Item $out -ErrorAction SilentlyContinue
}
$python = Join-Path $Root '.venv\Scripts\python.exe'
if (Test-Path $python) { & $python -m hinglish_eyecontact --root $Root --doctor }
Write-Host ''
Write-Host 'Eye Contact is set up. Use the Eye Contact button in the app, Premiere Pro or DaVinci Resolve.' -ForegroundColor Green
