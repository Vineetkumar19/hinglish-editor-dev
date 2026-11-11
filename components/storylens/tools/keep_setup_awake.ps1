# A process-scoped request: allow the screen to turn off but keep this setup
# computing. Does not change saved power settings or override critical battery
# hibernation. Windows clears the request when this helper exits.
$ErrorActionPreference='Stop'
Add-Type -TypeDefinition @'
using System.Runtime.InteropServices;
public static class StorylensSetupPower {
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern uint SetThreadExecutionState(uint state);
}
'@
$taskDeadline=(Get-Date).AddHours(3)
$taskReceipt='C:\Ai Models\logs\model-upgrade-completion.json'
try {
    if ([StorylensSetupPower]::SetThreadExecutionState([uint32]2147483649) -eq 0) { throw 'Windows did not accept the setup wake request.' }
    Write-Output 'Setup wake request active; display sleep and critical-battery protection remain available.'
    while ((Get-Date) -lt $taskDeadline) {
        if (Test-Path -LiteralPath $taskReceipt) {
            $taskState=Get-Content -LiteralPath $taskReceipt -Raw | ConvertFrom-Json
            if ($taskState.status -eq 'complete') { break }
        }
        Start-Sleep -Seconds 30
    }
}
finally {
    [StorylensSetupPower]::SetThreadExecutionState([uint32]2147483648) | Out-Null
    Write-Output 'Setup wake request released.'
}
