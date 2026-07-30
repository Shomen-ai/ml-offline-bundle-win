# ============================================================================
#  check_and_install.ps1 — МАШИНА B (изолированная, Windows x64, Python 3.11)
#
#  Что делает, по шагам:
#    1. Сверяет SHA256 всех перенесённых файлов с манифестом SHA256SUMS.txt
#    2. Склеивает модель из частей .part1/.part2/.part3 и проверяет её хеш
#    3. Ставит VC++ Redistributable, распаковывает Oracle Instant Client
#    4. Ставит python-пакеты СТРОГО ОФЛАЙН (--no-index) из папки wheels
#    5. Прогоняет проверки: CUDA-offload у llama.cpp, версия Oracle-клиента,
#       (опционально) тестовая загрузка модели на GPU
#
#  Запуск (из PowerShell или через install.bat):
#    powershell -ExecutionPolicy Bypass -File check_and_install.ps1
#    ... -TransferDir E:\transfer          если флешка не D:\transfer
#    ... -SkipSystem                       не трогать vc_redist/instantclient
#    ... -SkipModelTest                    пропустить загрузку модели на GPU
# ============================================================================

param(
    [string]$TransferDir = "D:\transfer",
    [string]$BundleDir   = "D:\bundle",
    [string]$OracleDir   = "D:\oracle",
    [string]$VenvPath    = "",             # по умолчанию <BundleDir>\ml-bundle\.venv
    [switch]$SkipSystem,
    [switch]$SkipChecksums,
    [switch]$SkipModelTest
)

$ErrorActionPreference = "Stop"
$script:fail = 0
function Ok($m)   { Write-Host "  [OK]   $m" -ForegroundColor Green }
function Warn($m) { Write-Host "  [WARN] $m" -ForegroundColor Yellow }
function Bad($m)  { Write-Host "  [FAIL] $m" -ForegroundColor Red; $script:fail++ }
function Step($m) { Write-Host "`n=== $m ===" -ForegroundColor Cyan }

if (-not $VenvPath) { $VenvPath = Join-Path $BundleDir "ml-bundle\.venv" }
$Wheels = Join-Path $TransferDir "wheels"
$Bin    = Join-Path $TransferDir "bin"
$Models = Join-Path $TransferDir "models"
$Req    = Join-Path $TransferDir "requirements-new.txt"
$Sums   = Join-Path $TransferDir "SHA256SUMS.txt"

# ---------------------------------------------------------------- 0. входные
Step "0. Проверка структуры $TransferDir"
foreach ($d in @($Wheels, $Bin, $Models)) {
    if (Test-Path $d) { Ok $d } else { Bad "нет папки $d" }
}
if (-not (Test-Path $Req)) { Bad "нет $Req" } else { Ok $Req }
if ($script:fail) { Write-Host "`nСтруктура неполная — сначала выполните download_release.ps1 на машине с интернетом."; exit 1 }

# ------------------------------------------------------------- 1. контрольные
if (-not $SkipChecksums -and (Test-Path $Sums)) {
    Step "1. Сверка SHA256 (это может занять пару минут)"
    foreach ($line in Get-Content $Sums) {
        if ($line -notmatch '^([0-9a-fA-F]{64})\s+(.+)$') { continue }
        $hash = $Matches[1].ToLower(); $name = $Matches[2].Trim()
        if ($name.StartsWith("ASSEMBLED:")) { continue }  # проверим после склейки
        # раскладка: части модели -> models\, wheels.zip -> корень, остальное -> bin\
        $p = if ($name -like "*.gguf.part*") { Join-Path $Models $name }
             elseif ($name -eq "wheels.zip") { Join-Path $TransferDir $name }
             else { Join-Path $Bin $name }
        if (-not (Test-Path $p)) { Warn "нет файла: $name (пропускаю)"; continue }
        $actual = (Get-FileHash -Algorithm SHA256 -Path $p).Hash.ToLower()
        if ($actual -eq $hash) { Ok $name } else { Bad "$name — хеш не совпал, файл побился при копировании" }
    }
    if ($script:fail) { Write-Host "`nЕсть побитые файлы — скопируйте их заново и перезапустите."; exit 1 }
} elseif (-not (Test-Path $Sums)) { Warn "SHA256SUMS.txt не найден — сверку пропускаю" }

# --------------------------------------------------------- 1b. wheels.zip
$WheelsZip = Join-Path $TransferDir "wheels.zip"
if ((Test-Path $WheelsZip) -and -not (Get-ChildItem $Wheels -Filter *.whl -ErrorAction SilentlyContinue)) {
    Step "1b. Распаковка wheels.zip"
    Expand-Archive -Path $WheelsZip -DestinationPath $Wheels -Force
    Ok ("колёс в папке: " + (Get-ChildItem $Wheels -Filter *.whl).Count)
}

# ------------------------------------------------------------- 2. модель
Step "2. Модель GGUF"
$parts = Get-ChildItem $Models -Filter "*.gguf.part*" -ErrorAction SilentlyContinue | Sort-Object Name
$assembledLine = (Get-Content $Sums -ErrorAction SilentlyContinue) | Where-Object { $_ -match '^\w{64}\s+ASSEMBLED:' } | Select-Object -First 1
if ($parts.Count -gt 0) {
    $target = Join-Path $Models ($parts[0].Name -replace '\.part\d+$','')
    if (-not (Test-Path $target)) {
        Write-Host "  Склеиваю $($parts.Count) части -> $(Split-Path $target -Leaf) (5+ ГБ, подождите)..."
        $out = [System.IO.File]::Create($target)
        try {
            foreach ($p in $parts) {
                $in = [System.IO.File]::OpenRead($p.FullName)
                try { $in.CopyTo($out, 8MB) } finally { $in.Dispose() }
            }
        } finally { $out.Dispose() }
        Ok "склеено: $target"
    } else { Ok "модель уже склеена: $target" }
    if ($assembledLine -and $assembledLine -match '^([0-9a-fA-F]{64})\s+ASSEMBLED:(.+)$') {
        $want = $Matches[1].ToLower()
        $actual = (Get-FileHash -Algorithm SHA256 -Path $target).Hash.ToLower()
        if ($actual -eq $want) { Ok "SHA256 склеенной модели совпал" }
        else { Bad "SHA256 склеенной модели НЕ совпал — части побились или их не хватает"; exit 1 }
    }
    # переносим в постоянное место
    $destModels = Join-Path $BundleDir "models"
    New-Item -ItemType Directory -Force -Path $destModels | Out-Null
    Copy-Item $target -Destination $destModels -Force
    $ModelPath = Join-Path $destModels (Split-Path $target -Leaf)
    Ok "модель скопирована в $ModelPath"
} else {
    $gguf = Get-ChildItem $Models -Filter "*.gguf" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($gguf) { $ModelPath = $gguf.FullName; Ok "найдена цельная модель: $ModelPath" }
    else { Warn "модели в $Models нет — шаг пропущен"; $ModelPath = $null }
}

# ------------------------------------------------------------- 3. системное
if (-not $SkipSystem) {
    Step "3. Системные компоненты"
    $vc = Join-Path $Bin "vc_redist.x64.exe"
    if (Test-Path $vc) {
        Write-Host "  Ставлю VC++ Redistributable (тихо)..."
        $p = Start-Process -FilePath $vc -ArgumentList "/install","/passive","/norestart" -Wait -PassThru
        if ($p.ExitCode -in 0,1638,3010) { Ok "vc_redist: код $($p.ExitCode) (0=ок, 1638=уже новее, 3010=нужна перезагрузка)" }
        else { Bad "vc_redist завершился с кодом $($p.ExitCode)" }
    } else { Warn "vc_redist.x64.exe не найден" }

    $ic = Join-Path $Bin "instantclient19.zip"
    if (Test-Path $ic) {
        New-Item -ItemType Directory -Force -Path $OracleDir | Out-Null
        $existing = Get-ChildItem $OracleDir -Directory -Filter "instantclient*" -ErrorAction SilentlyContinue
        if (-not $existing) {
            Write-Host "  Распаковываю Instant Client..."
            Expand-Archive -Path $ic -DestinationPath $OracleDir -Force
        }
        $icDir = (Get-ChildItem $OracleDir -Directory -Filter "instantclient*" | Select-Object -First 1).FullName
        if ($icDir) { Ok "Instant Client: $icDir" } else { Bad "не нашёл каталог instantclient_* в $OracleDir" }
    } else { Warn "instantclient19.zip не найден"; $icDir = $null }
} else {
    Step "3. Системное — пропущено (-SkipSystem)"
    $icDir = (Get-ChildItem $OracleDir -Directory -Filter "instantclient*" -ErrorAction SilentlyContinue | Select-Object -First 1).FullName
}

# ------------------------------------------------------------- 4. python
Step "4. Python-пакеты (строго офлайн)"
$py = Join-Path $VenvPath "Scripts\python.exe"
if (-not (Test-Path $py)) {
    Warn "venv не найден: $VenvPath"
    $sysPy = Get-Command py -ErrorAction SilentlyContinue
    if ($sysPy) {
        Write-Host "  Создаю venv через 'py -3.11'..."
        & py -3.11 -m venv $VenvPath
        if (-not (Test-Path $py)) { Bad "не удалось создать venv — проверьте, что установлен Python 3.11"; exit 1 }
    } else { Bad "нет ни venv, ни py-launcher. Установите Python 3.11 и перезапустите."; exit 1 }
}
$v = & $py -c "import sys; print('%d.%d' % sys.version_info[:2])"
if ($v -ne "3.11") { Bad "venv на Python $v, а колёса собраны под 3.11 — ставиться не будут"; exit 1 } else { Ok "Python $v" }

# cu118-проверка ДО установки, как в исходной инструкции
$llamaWheel = Get-ChildItem $Wheels -Filter "llama_cpp_python*.whl" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($llamaWheel) {
    if ($llamaWheel.Name -match "cu118") { Ok "колесо llama-cpp CUDA-шное: $($llamaWheel.Name)" }
    else { Warn "в имени $($llamaWheel.Name) нет cu118 — похоже, это CPU-сборка (GPU-offload не будет)" }
} else { Warn "колеса llama_cpp_python в wheels нет" }

& $py -m pip uninstall -y ollama langchain-ollama 2>$null | Out-Null
Write-Host "  pip install --no-index --find-links=$Wheels -r $Req"
& $py -m pip install --no-index --find-links=$Wheels -r $Req
if ($LASTEXITCODE -ne 0) {
    Bad "pip install упал. Чаще всего это значит: какой-то зависимости нет в wheels."
    Write-Host "  Запишите имя пакета из ошибки и докачайте его на машине с интернетом:"
    Write-Host "  pip download <имя> --only-binary=:all: --platform win_amd64 --python-version 311 --implementation cp --abi cp311 --dest wheels"
    exit 1
}
Ok "пакеты установлены офлайн"

# ------------------------------------------------------------- 5. проверки
Step "5. Проверки работоспособности"
$gpu = & $py -c "from llama_cpp import llama_cpp; print(llama_cpp.llama_supports_gpu_offload())" 2>&1
if ("$gpu" -match "True") { Ok "llama.cpp: GPU offload поддерживается" }
else { Bad "llama.cpp: GPU offload = $gpu (перенесено CPU-колесо? смотрите шаг 4)" }

if ($icDir) {
    $oc = & $py -c "import oracledb; oracledb.init_oracle_client(lib_dir=r'$icDir'); print(oracledb.clientversion())" 2>&1
    if ("$oc" -match "^\(19") { Ok "Oracle Instant Client: $oc" }
    else { Bad "oracledb/Instant Client: $oc" }
} else { Warn "Instant Client не распакован — проверка Oracle пропущена" }

if ($ModelPath -and -not $SkipModelTest) {
    Write-Host "  Тестовая загрузка модели на GPU (займёт минуту, следите за nvidia-smi)..."
    $t = & $py -c "from llama_cpp import Llama; l=Llama(model_path=r'$ModelPath', n_gpu_layers=-1, n_ctx=2048, verbose=False); print(l.create_chat_completion(messages=[{'role':'user','content':'2+2?'}], max_tokens=16)['choices'][0]['message']['content'])" 2>&1
    if ($LASTEXITCODE -eq 0) { Ok "модель отвечает: $t" } else { Bad "модель не загрузилась: $t" }
} elseif ($SkipModelTest) { Warn "тест модели пропущен (-SkipModelTest)" }

# ------------------------------------------------------------- 6. фиксация
Step "6. Фиксация результата"
$freeze = Join-Path (Split-Path $VenvPath -Parent) "requirements.txt"
& $py -m pip freeze > $freeze
Ok "pip freeze -> $freeze"
if ($llamaWheel) {
    $keep = Join-Path $BundleDir "wheels"
    New-Item -ItemType Directory -Force -Path $keep | Out-Null
    Copy-Item $llamaWheel.FullName $keep -Force
    Ok "CUDA-колесо llama-cpp сохранено в $keep (pip freeze не запоминает cu118!)"
}

Write-Host ""
if ($script:fail -eq 0) { Write-Host "ГОТОВО: все проверки пройдены." -ForegroundColor Green; exit 0 }
else { Write-Host "ЗАВЕРШЕНО С ОШИБКАМИ: $($script:fail) проблем(ы) выше." -ForegroundColor Red; exit 1 }
