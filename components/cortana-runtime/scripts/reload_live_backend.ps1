# Reload Cortana's own Python backend after source edits, preserving the desktop.
$ErrorActionPreference = 'Stop'
$allProcesses = @(Get-CimInstance Win32_Process)
$desktop = @($allProcesses | Where-Object {
    $_.ExecutablePath -eq 'D:\Cortana\desktop\node_modules\electron\dist\electron.exe' -and
    $_.CommandLine -like '*"D:\Cortana\desktop"*' -and $_.CommandLine -notlike '*--type=*'
})
if ($desktop.Count -ne 1) { throw 'Expected one Cortana desktop; nothing stopped.' }
$launcher = @($allProcesses | Where-Object {
    $_.ParentProcessId -eq $desktop[0].ProcessId -and $_.Name -eq 'python.exe' -and
    $_.CommandLine -like '*D:\Cortana\agent\.venv\Scripts\python.exe*-m uvicorn main:app*'
})
if ($launcher.Count -ne 1) { throw 'Expected one Cortana backend launcher; nothing stopped.' }
$backend = @($allProcesses | Where-Object {
    $_.ParentProcessId -eq $launcher[0].ProcessId -and
    $_.ExecutablePath -eq 'D:\Cortana\.runtime\python\python.exe' -and
    $_.CommandLine -like '*-m uvicorn main:app*'
})
if ($backend.Count -ne 1) { throw 'Expected one Cortana Python backend; nothing stopped.' }
Stop-Process -Id $backend[0].ProcessId -ErrorAction Stop
'Reload requested for Cortana backend; desktop supervisor will restart it.'
