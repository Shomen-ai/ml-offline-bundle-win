# ============================================================================
#  download_release.ps1 — МАШИНА A (с интернетом, любая Windows 10/11)
#
#  Скачивает ВСЕ файлы из GitHub Release этого репозитория и раскладывает
#  их в структуру D:\transfer, которую ожидает check_and_install.ps1:
#      D:\transfer\wheels\*.whl        (из wheels.zip)
#      D:\transfer\bin\*.zip|.exe|.msi
#      D:\transfer\models\*.gguf.part1..3
#      D:\transfer\requirements-new.txt, SHA256SUMS.txt, scripts\
#
#  Запуск:
#    powershell -ExecutionPolicy Bypass -File download_release.ps1
#    ... -Dest E:\transfer     положить в другое место
#    ... -Tag  v1.0.0          конкретная версия релиза
# ============================================================================

param(
    [string]$Repo = "Shomen-ai/ml-offline-bundle-win",
    [string]$Tag  = "v1.0.0",
    [string]$Dest = "D:\transfer"
)

$ErrorActionPreference = "Stop"
$base = "https://github.com/$Repo/releases/download/$Tag"
$raw  = "https://raw.githubusercontent.com/$Repo/main"

foreach ($d in @("$Dest", "$Dest\wheels", "$Dest\bin", "$Dest\models", "$Dest\scripts")) {
    New-Item -ItemType Directory -Force -Path $d | Out-Null
}

function Get-File($url, $out) {
    Write-Host ("  <- " + (Split-Path $out -Leaf))
    # curl.exe есть в Windows 10 1803+; докачивает при обрыве (-C -)
    & curl.exe -fL --retry 5 --retry-delay 5 -C - -o $out $url
    if ($LASTEXITCODE -ne 0) { throw "не скачалось: $url" }
}

Write-Host "=== 1/4: манифест и сопроводительные файлы ==="
Get-File "$base/SHA256SUMS.txt"          "$Dest\SHA256SUMS.txt"
Get-File "$raw/requirements-new.txt"     "$Dest\requirements-new.txt"
Get-File "$raw/scripts/check_and_install.ps1" "$Dest\scripts\check_and_install.ps1"
Get-File "$raw/scripts/install.bat"      "$Dest\scripts\install.bat"

Write-Host "=== 2/4: файлы релиза по манифесту ==="
$names = @()
foreach ($line in Get-Content "$Dest\SHA256SUMS.txt") {
    if ($line -match '^[0-9a-fA-F]{64}\s+(.+)$') {
        $n = $Matches[1].Trim()
        if (-not $n.StartsWith("ASSEMBLED:")) { $names += $n }
    }
}
foreach ($n in $names) {
    $out = if ($n -like "*.gguf.part*") { "$Dest\models\$n" }
           elseif ($n -eq "wheels.zip") { "$Dest\wheels.zip" }
           else { "$Dest\bin\$n" }
    Get-File "$base/$n" $out
}

Write-Host "=== 3/4: сверка SHA256 ==="
$bad = 0
foreach ($line in Get-Content "$Dest\SHA256SUMS.txt") {
    if ($line -notmatch '^([0-9a-fA-F]{64})\s+(.+)$') { continue }
    $hash = $Matches[1].ToLower(); $n = $Matches[2].Trim()
    if ($n.StartsWith("ASSEMBLED:")) { continue }
    $p = if ($n -like "*.gguf.part*") { "$Dest\models\$n" } elseif ($n -eq "wheels.zip") { "$Dest\wheels.zip" } else { "$Dest\bin\$n" }
    $a = (Get-FileHash -Algorithm SHA256 -Path $p).Hash.ToLower()
    if ($a -eq $hash) { Write-Host "  [OK]   $n" -ForegroundColor Green }
    else { Write-Host "  [FAIL] $n" -ForegroundColor Red; $bad++ }
}
if ($bad) { throw "$bad файл(ов) скачались битыми — перезапустите скрипт, докачает с места обрыва." }

Write-Host "=== 4/4: распаковка wheels.zip ==="
Expand-Archive -Path "$Dest\wheels.zip" -DestinationPath "$Dest\wheels" -Force
Write-Host ("  колёс: " + (Get-ChildItem "$Dest\wheels" -Filter *.whl).Count)

Write-Host ""
Write-Host "ГОТОВО. Скопируйте всю папку $Dest на флешку и запустите на рабочей машине:" -ForegroundColor Green
Write-Host "  D:\transfer\scripts\install.bat"
