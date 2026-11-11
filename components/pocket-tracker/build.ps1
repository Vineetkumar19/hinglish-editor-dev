param([switch]$Install,[switch]$TestDevice)
$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
$jdkCandidates=@($env:JAVA_HOME,'C:\Program Files\Eclipse Adoptium\jdk-21.0.12.101-hotspot')
$jdk=$jdkCandidates | Where-Object { $_ -and (Test-Path (Join-Path $_ 'bin\java.exe')) } | Select-Object -First 1
if(-not $jdk){throw 'Install JDK 17 or 21 and set JAVA_HOME.'}
$env:JAVA_HOME=$jdk
$env:GRADLE_USER_HOME=Join-Path $PSScriptRoot '.gradle-home'
$env:ANDROID_USER_HOME=Join-Path $PSScriptRoot '.android-home'
$sdk=Join-Path $env:LOCALAPPDATA 'Android\Sdk'
if(-not(Test-Path $sdk)){throw 'Install Android SDK platform 35 and build-tools 35.0.0 first.'}
Set-Content -LiteralPath 'local.properties' -Value ('sdk.dir='+$sdk.Replace('\','/')) -Encoding ascii
New-Item -ItemType Directory -Force -Path '.android-home' | Out-Null
if(-not(Test-Path '.android-home\debug.keystore')){& (Join-Path $jdk 'bin\keytool.exe') -genkeypair -keystore '.android-home\debug.keystore' -storepass android -alias androiddebugkey -keypass android -dname 'CN=Pocket Tracker Development,O=Personal,C=IN' -keyalg RSA -keysize 2048 -validity 10000;if($LASTEXITCODE -ne 0){throw 'Signing-key generation failed'}}
$gradle='C:\ProgramData\chocolatey\lib\gradle\tools\gradle-8.12.1\bin\gradle.bat'
if(Test-Path '.\gradlew.bat'){$gradle=Join-Path $PSScriptRoot 'gradlew.bat'}
if(-not(Test-Path $gradle)){throw 'Install Gradle 8.12.1 or use the Gradle wrapper.'}
& $gradle --no-daemon :core:test :app:assembleDebug :app:lintDebug
if($LASTEXITCODE -ne 0){throw 'Build or checks failed. Installation stopped.'}
if($Install){& (Join-Path $sdk 'platform-tools\adb.exe') install -r 'app\build\outputs\apk\debug\app-debug.apk';if($LASTEXITCODE -ne 0){throw 'Phone installation failed'};& (Join-Path $sdk 'platform-tools\adb.exe') shell am start -n 'in.pocketledger.app/.MainActivity'}
if($TestDevice){& $gradle --no-daemon :app:connectedDebugAndroidTest;if($LASTEXITCODE -ne 0){throw 'Device tests failed'}}
