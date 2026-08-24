param(
    [string]$GradleVersion = "8.2.1"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$gradleRoot = Join-Path $projectRoot ".android-tools\gradle-$GradleVersion"
$gradleBat = Join-Path $gradleRoot "bin\gradle.bat"

if (-not $env:JAVA_HOME -or -not (Test-Path (Join-Path $env:JAVA_HOME "bin\java.exe"))) {
    throw "JAVA_HOME must point to JDK 17."
}
if (-not $env:ANDROID_SDK_ROOT -or -not (Test-Path $env:ANDROID_SDK_ROOT)) {
    throw "ANDROID_SDK_ROOT must point to an Android SDK containing platform 34."
}

if (-not (Test-Path $gradleBat)) {
    $toolsRoot = Split-Path -Parent $gradleRoot
    New-Item -ItemType Directory -Force -Path $toolsRoot | Out-Null
    $zipPath = Join-Path $toolsRoot "gradle-$GradleVersion-bin.zip"
    Invoke-WebRequest "https://services.gradle.org/distributions/gradle-$GradleVersion-bin.zip" -OutFile $zipPath
    Expand-Archive -LiteralPath $zipPath -DestinationPath $toolsRoot -Force
}

& $gradleBat --no-daemon clean assembleDebug
if ($LASTEXITCODE -ne 0) {
    throw "Android build failed with exit code $LASTEXITCODE."
}

$dist = Join-Path $projectRoot "dist"
New-Item -ItemType Directory -Force -Path $dist | Out-Null
Copy-Item (Join-Path $projectRoot "app\build\outputs\apk\debug\app-debug.apk") (Join-Path $dist "Elemental-Mobile.apk") -Force
Write-Host "Built universal APK in $dist"
