param([int]$NarrationRate = 0)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskOut = Join-Path $taskRoot 'output\reference-analysis\cricAddict-independent-sample'
$taskPlan = Get-Content -LiteralPath (Join-Path $taskOut 'local-plan.json') -Raw | ConvertFrom-Json
$taskVoiceDir = Join-Path $taskOut 'voice'
New-Item -ItemType Directory -Force -Path $taskVoiceDir | Out-Null
Add-Type -AssemblyName System.Speech
$taskVoice = [System.Speech.Synthesis.SpeechSynthesizer]::new()
$taskVoice.SelectVoice('Microsoft David Desktop')
$taskVoice.Rate = $NarrationRate
$taskAudioFormat = [System.Speech.AudioFormat.SpeechAudioFormatInfo]::new(16000,[System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,[System.Speech.AudioFormat.AudioChannel]::Mono)
$taskRows = @()
try {
    for ($taskIndex=0; $taskIndex -lt $taskPlan.scenes.Count; $taskIndex++) {
        $taskName = '{0:d2}.wav' -f ($taskIndex+1)
        $taskId = 'IndependentVoiceProgress' + $taskIndex
        $taskSub = Register-ObjectEvent -InputObject $taskVoice -EventName SpeakProgress -SourceIdentifier $taskId
        try {
            $taskVoice.SetOutputToWaveFile((Join-Path $taskVoiceDir $taskName),$taskAudioFormat)
            $taskVoice.Speak([string]$taskPlan.scenes[$taskIndex].narration)
            $taskVoice.SetOutputToNull()
            $taskWords = @(Get-Event -SourceIdentifier $taskId -ErrorAction SilentlyContinue | ForEach-Object {
                @{text=$_.SourceEventArgs.Text; audio_seconds=$_.SourceEventArgs.AudioPosition.TotalSeconds; character=$_.SourceEventArgs.CharacterPosition}
            })
            $taskRows += @{file=$taskName; text=$taskPlan.scenes[$taskIndex].narration; words=$taskWords; sha256=(Get-FileHash -LiteralPath (Join-Path $taskVoiceDir $taskName) -Algorithm SHA256).Hash.ToLowerInvariant(); purpose='fresh-production-narration'}
        } finally {
            Unregister-Event -SourceIdentifier $taskId
            Get-Event -SourceIdentifier $taskId -ErrorAction SilentlyContinue | Remove-Event
        }
    }
} finally {$taskVoice.Dispose()}
@{voice='Microsoft David Desktop';engine='Offline Windows System.Speech';rate=$NarrationRate;audio_format='16000 Hz PCM16 mono';reference_audio_used=$false;timing='Local speech engine SpeakProgress audio positions; fixed output format cross-checked against voiced regions';scenes=$taskRows} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $taskOut 'voice-receipt.json') -Encoding utf8
Write-Output 'Fresh local narration and speech timing generated.'
