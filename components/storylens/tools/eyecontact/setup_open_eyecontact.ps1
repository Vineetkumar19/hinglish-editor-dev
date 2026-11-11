$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$taskStore='C:\Ai Models\eyecontact'
$taskRuntime='C:\Ai Models\runtimes\eyecontact'
$taskPython=Join-Path $taskRoot '.venv\Scripts\python.exe'
$taskEyePython=Join-Path $taskRuntime 'Scripts\python.exe'
$env:PIP_CACHE_DIR='C:\Ai Models\runtimes\pip-cache'
$env:TEMP='C:\Ai Models\runtimes\tmp\eyecontact'
$env:TMP=$env:TEMP
New-Item -ItemType Directory -Path $env:TEMP,$taskStore -Force | Out-Null
$env:MPLCONFIGDIR=Join-Path $taskRuntime 'matplotlib-cache'
$taskOnnx=Join-Path $taskStore 'hsu-onnx'
New-Item -ItemType Directory -Path $taskOnnx -Force | Out-Null
$taskWeights=@{
    L='f39ee44e76c4efbd0bace9295baab7a8c823ac18a4ff7f5b725ddbfbf2bd50e1'
    R='f64f721e805c8bcbf2d0b96b889fe957f480e5e328014a9ee6e93d68f0aa2d47'
}
foreach ($taskSide in @('L','R')) {
    $taskUrl='https://raw.githubusercontent.com/KypMon/coreml-eye-contact/e9d5ae505c62f87851756e966d3e8d1d39b1bcfe/neural/gaze_'+$taskSide+'.onnx'
    & $taskPython -E -X utf8 tools\ranged_download.py $taskUrl --output (Join-Path $taskOnnx ('gaze_'+$taskSide+'.onnx')) --sha256 $taskWeights[$taskSide]
    if ($LASTEXITCODE -ne 0) {throw 'Gaze weights download failed'}
}
& $taskPython -E -X utf8 tools\ranged_download.py 'https://raw.githubusercontent.com/chihfanhsu/gaze_correction/7cc76e4ccaf76c950730c593ffa22bed30c807a4/LICENSES' --output (Join-Path $taskOnnx 'LICENSES') --sha256 '6aa3c846221fc8606faad0394595a45f5a0cb97787ccfd0ba884ffab0b9c4d19'
if ($LASTEXITCODE -ne 0) {throw 'Gaze model license download failed'}
if (!(Test-Path -LiteralPath $taskEyePython)) {
    & $taskPython -E -m venv $taskRuntime
    if ($LASTEXITCODE -ne 0) {throw 'Could not create isolated Eye Contact runtime'}
}
# Reuse the working editor libraries without changing its Python environment.
(Join-Path $taskRoot '.venv\Lib\site-packages') | Set-Content -LiteralPath (Join-Path $taskRuntime 'Lib\site-packages\storylens-editor-libraries.pth') -Encoding utf8
$taskWheel=Join-Path $taskStore 'mediapipe-0.10.32-py3-none-win_amd64.whl'
& $taskPython -E -X utf8 tools\ranged_download.py 'https://files.pythonhosted.org/packages/fe/63/c9172142521fc334fa891be9ef6259a3790502041b395127d63755cb3f0b/mediapipe-0.10.32-py3-none-win_amd64.whl' --output $taskWheel --sha256 '438d98977a4e1b0f88070ad16537a328912f847ce9debf236da047b0b483cbfd'
if ($LASTEXITCODE -ne 0) {throw 'MediaPipe package download failed'}
& $taskEyePython -E -X utf8 -m pip install --no-deps $taskWheel 'absl-py==2.3.1' 'sounddevice==0.5.3'
if ($LASTEXITCODE -ne 0) {throw 'Eye Contact dependencies failed'}
& $taskEyePython -E -X utf8 -m pip install 'matplotlib>=3.10,<3.11'
if ($LASTEXITCODE -ne 0) {throw 'Eye Contact drawing dependencies failed'}
& $taskPython -E -X utf8 tools\ranged_download.py 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task' --output (Join-Path $taskStore 'face_landmarker.task')
if ($LASTEXITCODE -ne 0) {throw 'Face landmark model download failed'}
& $taskEyePython -E -X utf8 -c "import mediapipe,onnxruntime,cv2; print('OPEN_EYECONTACT_RUNTIME_READY',mediapipe.__version__,onnxruntime.__version__)"
if ($LASTEXITCODE -ne 0) {throw 'Eye Contact runtime import check failed'}
@{backend='hsu_onnx';runtime_python=$taskEyePython;model_dir=(Join-Path $taskStore 'hsu-onnx');landmark_model=(Join-Path $taskStore 'face_landmarker.task')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskRoot 'config.eyecontact.open.local.json') -Encoding utf8
Write-Output 'OPEN_EYECONTACT_SETUP_READY'
