$ErrorActionPreference='Stop'
$captionTaskRoot=Split-Path -Parent $PSScriptRoot
$captionVoiceOut=Join-Path $captionTaskRoot 'tmp\serif-circle-english'
New-Item -ItemType Directory -Force -Path $captionVoiceOut | Out-Null
$captionNarration='Why one single post is not enough today. Your audience needs more. One post changes nothing. People need a clear reason to stop, listen, and care. Think about your middle and bottom funnel. Create reels that connect. Tell a story with real meaning. Then they will trust you. But without a message, you might lose clients. Good design supports your words. A simple idea can make a powerful impact. Keep the spacing tight. Let each line arrive with purpose. Make the important words stand out. Build a connection, stay consistent, and keep improving. That is how your story becomes worth remembering.'
Add-Type -AssemblyName System.Speech
$captionVoice=[System.Speech.Synthesis.SpeechSynthesizer]::new()
$captionVoice.SelectVoice('Microsoft Zira Desktop')
$captionVoice.Rate=-1
$captionFormat=[System.Speech.AudioFormat.SpeechAudioFormatInfo]::new(16000,[System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,[System.Speech.AudioFormat.AudioChannel]::Mono)
$captionEvent='SerifCircleEnglishProgress'
Register-ObjectEvent -InputObject $captionVoice -EventName SpeakProgress -SourceIdentifier $captionEvent | Out-Null
try {
    $captionVoice.SetOutputToWaveFile((Join-Path $captionVoiceOut 'narration.wav'),$captionFormat)
    $captionVoice.Speak($captionNarration)
    $captionVoice.SetOutputToNull()
    $captionWords=@(Get-Event -SourceIdentifier $captionEvent | ForEach-Object { @{text=$_.SourceEventArgs.Text; start=$_.SourceEventArgs.AudioPosition.TotalSeconds; character=$_.SourceEventArgs.CharacterPosition} })
    @{text=$captionNarration;voice='Microsoft Zira Desktop';language='English';words=$captionWords} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $captionVoiceOut 'timing.json') -Encoding utf8
} finally {
    Unregister-Event -SourceIdentifier $captionEvent -ErrorAction SilentlyContinue
    Get-Event -SourceIdentifier $captionEvent -ErrorAction SilentlyContinue | Remove-Event
    $captionVoice.Dispose()
}
Write-Output 'English narration and word timing are ready.'
