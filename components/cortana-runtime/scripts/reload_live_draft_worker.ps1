# Reload only Cortana's private draft worker during live development.
# Never stop the backend, desktop, or applications opened for the owner.
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
$workerLauncher = @($allProcesses | Where-Object {
    $_.ParentProcessId -eq $backend[0].ProcessId -and $_.Name -eq 'python.exe' -and
    $_.CommandLine -like '*D:\Cortana\agent\core\desktop_drafts.py*--worker*'
})
if ($workerLauncher.Count -eq 0) { 'No private draft worker is loaded; next request loads current code.'; return }
if ($workerLauncher.Count -ne 1) { throw 'Expected one private draft worker; nothing stopped.' }
$worker = @($allProcesses | Where-Object {
    $_.ParentProcessId -eq $workerLauncher[0].ProcessId -and
    $_.ExecutablePath -eq 'D:\Cortana\.runtime\python\python.exe' -and
    $_.CommandLine -like '*D:\Cortana\agent\core\desktop_drafts.py*--worker*'
})
if ($worker.Count -ne 1) { throw 'Expected one private worker interpreter; nothing stopped.' }
Stop-Process -Id $worker[0].ProcessId -ErrorAction Stop
'Cortana private draft worker refreshed. Desktop and user applications remain open.'
