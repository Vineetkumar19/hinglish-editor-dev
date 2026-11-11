param([long]$WindowHandle=0)
$ErrorActionPreference = 'Stop'
$shell = New-Object -ComObject Shell.Application
$selectedPaths = @()
try {
    foreach ($window in $shell.Windows()) {
        if ([IO.Path]::GetFileName([string]$window.FullName) -ine 'explorer.exe') { continue }
        if ($WindowHandle -gt 0 -and [long]$window.HWND -ne $WindowHandle) { continue }
        foreach ($item in $window.Document.SelectedItems()) {
            if ($item.IsFileSystem -and -not $item.IsFolder) { $selectedPaths += [string]$item.Path }
        }
    }
    $selectedPaths = @($selectedPaths | Select-Object -Unique)
    if ($selectedPaths.Count -ne 1) { throw 'Select a single image or video in one Explorer window.' }
    @{paths=$selectedPaths} | ConvertTo-Json -Compress
} finally {
    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($shell)
}
