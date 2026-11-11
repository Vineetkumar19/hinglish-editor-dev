# AI Images & Video setup: a separate Python environment + the local models (Z-Image Turbo, Wan 2.2 5B).
# Run it through "Setup AI Images (RTX).bat" (-Models image) or "Setup AI Video (RTX).bat" (-Models video): one shared
# environment, each model downloaded once. Safe to run again: finished steps are skipped.
# Everything goes into one folder you choose (default: tools\aigen\install inside the editor folder).
param(
    [string]$Target = '',
    [ValidateSet('all', 'image', 'video')][string]$Models = 'all',
    [switch]$SkipDownload
)
# Not 'Stop': pip and Python print harmless warnings to stderr, which Windows PowerShell would treat as fatal.
# Every step checks its own exit code instead.
$ErrorActionPreference = 'Continue'
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Config = Join-Path $Root 'config.aigen.local.json'

function Say($text) { Write-Host $text -ForegroundColor Cyan }
function Good($text) { Write-Host "  OK  $text" -ForegroundColor Green }
function Stop-Setup($text) { Write-Host ''; Write-Host $text -ForegroundColor Red; exit 1 }
function Has($command) { [bool](Get-Command $command -ErrorAction SilentlyContinue) }

if (-not $Target) {
    if (Test-Path -LiteralPath $Config) {
        try { $Target = (Get-Content -LiteralPath $Config -Raw | ConvertFrom-Json).install } catch { $Target = '' }
    }
    if (-not $Target) { $Target = Join-Path $Root 'tools\aigen\install' }
}
$Target = [IO.Path]::GetFullPath($Target)
New-Item -ItemType Directory -Force $Target | Out-Null
Say "Installing into $Target"

# 1. GPU -------------------------------------------------------------------------------------------------
Say '1/5  Checking the GPU'
$line = $null
if (Has 'nvidia-smi') {
    $line = & nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader,nounits 2>$null | Select-Object -First 1
}
if (-not $line) { Stop-Setup 'No NVIDIA GPU or driver found. Install the latest NVIDIA driver, then run this again.' }
$parts = $line.Split(',') | ForEach-Object { $_.Trim() }
$GpuName = $parts[0]; $VramGb = [math]::Round([double]$parts[1] / 1024, 1); $Driver = $parts[2]
Good "$GpuName  ($VramGb GB video memory, driver $Driver)"
if ($VramGb -lt 8) { Write-Host '  Note: under 8 GB works only in the slow test mode (small pictures, short clips).' -ForegroundColor Yellow }

# 2. Python ------------------------------------------------------------------------------------------------
Say '2/5  Python environment (separate from the editor, so it can never break it)'
function Find-Python {
    $tries = @(@('py', '-3.12'), @('py', '-3.11'), @('py', '-3.13'), @('py', '-3.10'), @('python'), @('python3'))
    foreach ($try in $tries) {
        $command = Get-Command $try[0] -ErrorAction SilentlyContinue
        if (-not $command) { continue }
        $extra = @($try | Select-Object -Skip 1)
        try { $version = & $command.Source @extra -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null } catch { continue }
        if ($LASTEXITCODE -ne 0 -or -not $version) { continue }
        if (@('3.10', '3.11', '3.12', '3.13') -contains $version.Trim()) {
            return @{ exe = $command.Source; args = $extra; version = $version.Trim() }
        }
    }
    return $null
}
$Venv = Join-Path $Target 'venv'
$Py = Join-Path $Venv 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Py)) {
    $python = Find-Python
    if (-not $python) { Stop-Setup 'Install 64-bit Python 3.12 from python.org (tick "Add python.exe to PATH"), then run this again.' }
    & $python.exe @($python.args) -m venv $Venv
    if ($LASTEXITCODE -ne 0) { Stop-Setup 'Could not create the Python environment.' }
}
Good "Python ready: $Py"

# 3. Libraries -----------------------------------------------------------------------------------------------
Say '3/5  AI libraries (PyTorch with CUDA 12.8 for RTX 20-50 series, diffusers)'
$ready = & $Py -c "import torch, diffusers; from diffusers import ZImagePipeline, WanPipeline; print(torch.cuda.is_available())" 2>$null
if ($LASTEXITCODE -ne 0 -or $ready -ne 'True') {
    & $Py -m pip install --upgrade pip | Out-Null
    & $Py -m pip install 'torch==2.9.1' --index-url 'https://download.pytorch.org/whl/cu128'
    if ($LASTEXITCODE -ne 0) { Stop-Setup 'Could not install PyTorch (check the internet connection and run again).' }
    & $Py -m pip install 'transformers>=4.56' 'accelerate>=1.10' safetensors sentencepiece protobuf ftfy 'huggingface_hub>=0.34' imageio imageio-ffmpeg pillow numpy
    if ($LASTEXITCODE -ne 0) { Stop-Setup 'Could not install the AI libraries.' }
    & $Py -m pip install 'diffusers>=0.36'
    $has = & $Py -c "from diffusers import ZImagePipeline, WanPipeline; print('ok')" 2>$null
    if ($has -ne 'ok') {
        if (-not (Has 'git')) { Stop-Setup 'This diffusers release is too old and Git is missing. Install Git from git-scm.com, then run this again.' }
        & $Py -m pip install 'git+https://github.com/huggingface/diffusers'
    }
    $ready = & $Py -c "import torch; from diffusers import ZImagePipeline, WanPipeline; print(torch.cuda.is_available())"
    if ($ready -ne 'True') { Stop-Setup 'PyTorch cannot see the NVIDIA GPU. Update the NVIDIA driver, then run this again.' }
}
Good 'PyTorch + diffusers ready (GPU visible)'

# 4. Models -------------------------------------------------------------------------------------------------------
Say '4/5  Downloading the models (Z-Image Turbo ~21 GB, Wan 2.2 5B ~24 GB; resumes if interrupted)'
$ModelDir = Join-Path $Target 'models'
New-Item -ItemType Directory -Force $ModelDir | Out-Null
$wanted = @()
if ($Models -in @('all', 'image')) { $wanted += 'Tongyi-MAI/Z-Image-Turbo' }
if ($Models -in @('all', 'video')) { $wanted += 'Wan-AI/Wan2.2-TI2V-5B-Diffusers' }
if (-not $SkipDownload) {
    foreach ($repo in $wanted) {
        $folder = Join-Path $ModelDir ($repo -replace '/', '--')
        Write-Host "  $repo"
        & $Py -c "import sys; from huggingface_hub import snapshot_download; snapshot_download(sys.argv[1], local_dir=sys.argv[2])" $repo $folder
        if ($LASTEXITCODE -ne 0) { Stop-Setup "Download of $repo stopped. Run this again: it continues where it stopped." }
        Good $repo
    }
}

# 5. Remember where it is -----------------------------------------------------------------------------------------------
Say '5/5  Saving the location for the editor'
$data = @{ install = $Target; gpu = $GpuName; vram_gb = $VramGb }
if (Test-Path -LiteralPath $Config) {
    try {
        $old = Get-Content -LiteralPath $Config -Raw | ConvertFrom-Json
        if ($old.styles) { $data.styles = $old.styles }
    } catch {}
}
$data | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $Config -Encoding UTF8
Good "Saved in $Config"
Write-Host ''
Write-Host 'Ready. Start the editor and choose "AI Images" or "AI Video".' -ForegroundColor Green
