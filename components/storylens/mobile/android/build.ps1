param([switch]$Offline)
$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
$jdk=Get-ChildItem -LiteralPath '.\toolchain\jdk' -Directory -ErrorAction SilentlyContinue | Where-Object {Test-Path (Join-Path $_.FullName 'bin\java.exe')} | Select-Object -First 1
if(-not $jdk){throw 'JDK21 missing. Restore the isolated toolchain or configure this script with an existing JDK21.'}
$env:JAVA_HOME=$jdk.FullName
$env:GRADLE_USER_HOME=Join-Path $PSScriptRoot '.gradle-home'
$env:ANDROID_USER_HOME=Join-Path $PSScriptRoot '.android-home'
$sdk=Join-Path $PSScriptRoot 'toolchain\sdk'
$gradle=Join-Path $PSScriptRoot 'toolchain\gradle-8.12.1\bin\gradle.bat'
if(-not(Test-Path (Join-Path $sdk 'platforms\android-35\android.jar'))){throw 'Android SDK35 missing.'}
if(-not(Test-Path $gradle)){throw 'Gradle8.12.1 missing.'}
New-Item -ItemType Directory -Force -Path '.private','checks\build-scratch' | Out-Null
$env:TEMP=Join-Path $PSScriptRoot 'checks\build-scratch'
$env:TMP=$env:TEMP
$owner=[System.Security.Principal.WindowsIdentity]::GetCurrent().Name
& icacls.exe '.private' /inheritance:r /grant:r "$owner`:(OI)(CI)F" /q | Out-Null
if($LASTEXITCODE -ne 0){throw 'Could not protect private signing directory.'}
$passwordPath=Join-Path $PSScriptRoot '.private\signing.password.dpapi'
if(-not(Test-Path $passwordPath)){
    $bytes=New-Object byte[] 32
    $rng=[System.Security.Cryptography.RandomNumberGenerator]::Create();$rng.GetBytes($bytes);$rng.Dispose()
    $password=[Convert]::ToBase64String($bytes)
    ConvertTo-SecureString $password -AsPlainText -Force | ConvertFrom-SecureString | Set-Content -LiteralPath $passwordPath -Encoding ascii
}
$secret=(Get-Content -LiteralPath $passwordPath -Raw).Trim() | ConvertTo-SecureString
$ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
try{$env:STORYLENS_SIGN_PASSWORD=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)}finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)}
try{
    if(-not(Test-Path '.private\storylens-personal.p12')){
        & (Join-Path $env:JAVA_HOME 'bin\keytool.exe') -genkeypair -keystore '.private\storylens-personal.p12' -storetype PKCS12 -storepass:env STORYLENS_SIGN_PASSWORD -alias storylens-personal -keypass:env STORYLENS_SIGN_PASSWORD -dname 'CN=StoryLens Personal Development,O=Personal,C=IN' -keyalg RSA -keysize 3072 -validity 10000
        if($LASTEXITCODE -ne 0){throw 'Personal signing key creation failed.'}
    }
    Set-Content -LiteralPath 'local.properties' -Value ('sdk.dir='+$sdk.Replace('\','\\')) -Encoding ascii
    $gradleArgs=@('--no-daemon','--console=plain',':core:check',':app:assembleRelease',':app:lintRelease')
    if($Offline){$gradleArgs=@('--offline')+$gradleArgs}
    & $gradle @gradleArgs
    if($LASTEXITCODE -ne 0){throw 'Native checks/build/lint failed. No APK packaged.'}
    $destination=Join-Path $PSScriptRoot '..\..\output\phone-native'
    New-Item -ItemType Directory -Force -Path $destination | Out-Null
    Copy-Item -LiteralPath '.\app\build\outputs\apk\release\app-release.apk' -Destination (Join-Path $destination 'StoryLens-Phone.apk') -Force
    $hash=Get-FileHash -LiteralPath (Join-Path $destination 'StoryLens-Phone.apk') -Algorithm SHA256
    ($hash.Hash.ToLower()+'  StoryLens-Phone.apk') | Set-Content -LiteralPath (Join-Path $destination 'StoryLens-Phone.apk.sha256') -Encoding ascii
    Write-Output ('APK: '+(Join-Path $destination 'StoryLens-Phone.apk'))
    Write-Output ('SHA256: '+$hash.Hash.ToLower())
}finally{Remove-Item Env:\STORYLENS_SIGN_PASSWORD -ErrorAction SilentlyContinue}
