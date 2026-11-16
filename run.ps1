# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# One-shot start script for DXOS-OpenCore-C3 on Windows.
# Usage:
#   .\run.ps1
#   .\run.ps1 -Reset
#   .\run.ps1 -NoBrowser

[CmdletBinding()]
param(
    [switch]$Reset,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

# Dung dung ten project khai bao trong compose.yaml ("name: dxos") de dx.ps1, pytest va run.ps1
# cung dieu khien mot stack. Khong dat $env:COMPOSE_PROJECT_NAME: bien nay con lai trong phien
# PowerShell sau khi script ket thuc va lam cac lenh docker compose sau do tro sang project khac.
$composeProject = "dxos"
if ($env:COMPOSE_PROJECT_NAME -and $env:COMPOSE_PROJECT_NAME -ne $composeProject) {
    Remove-Item Env:COMPOSE_PROJECT_NAME -ErrorAction SilentlyContinue
}

$logDir = Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ("run-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".log")

function Write-Step {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $Message
    Write-Host $line
    Add-Content -LiteralPath $logFile -Value $line -Encoding UTF8
}

function Stop-WithError {
    param([string]$Message)
    Write-Step "ERROR: $Message"
    Write-Host ""
    Write-Host "Log: $logFile" -ForegroundColor Yellow
    exit 1
}

Write-Step "DX-OS one-shot start"
Write-Step "Project: $composeProject"
Write-Step "Root: $root"

# 1. Docker daemon must be available.
try {
    $dockerVersion = docker version --format "{{.Server.Version}}" 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $dockerVersion) {
        Stop-WithError "Docker Desktop chua chay. Hay mo Docker Desktop roi chay lai."
    }
    Write-Step "Docker Server: $dockerVersion"
} catch {
    Stop-WithError "Khong tim thay Docker CLI hoac Docker Desktop chua chay."
}

# 2. Stop containers from another compose project that use the same dxos-* names.
# Doc nhan qua {{.Labels}} (khong co dau nhay kep ben trong) vi Windows PowerShell 5.1 lam hong
# doi so dang '{{.Label "..."}}' khi truyen cho docker, khien khong phat hien duoc stack cu.
$otherProjects = @()
try {
    $otherProjects = @(docker ps -a --filter "name=dxos-" --format "{{.Labels}}" 2>$null |
        ForEach-Object {
            foreach ($pair in ($_ -split ",")) {
                if ($pair -like "com.docker.compose.project=*") { $pair.Substring(27) }
            }
        } |
        Where-Object { $_ -and $_ -ne $composeProject } |
        Sort-Object -Unique)
} catch {
    $otherProjects = @()
}
foreach ($project in $otherProjects) {
    Write-Step "Phat hien stack cu project=$project; dung container de tranh xung dot (volume duoc giu nguyen)..."
    docker compose -p $project down 2>&1 | Tee-Object -FilePath $logFile -Append | Out-Null
}

# 3. Warn if port 8080 is held by a non-Docker process (Docker/vmnat/vpnkit are OK).
$portOwner = $null
try {
    $conn = Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($conn) {
        $portOwner = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
    }
} catch {
    $portOwner = $null
}
if ($portOwner -and $portOwner.ProcessName -notmatch "com\.docker|docker|vpnkit|vmnat|wsl") {
    Write-Step "CANH BAO: cong 8080 dang bi process '$($portOwner.ProcessName)' chiem. Neu Docker khong bind duoc, hay tat process do."
}

# 4. Optional clean reset.
if ($Reset) {
    Write-Step "Reset sach toan bo du lieu project $composeProject..."
    & "$root\dx.ps1" reset --yes 2>&1 | Tee-Object -FilePath $logFile -Append | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Stop-WithError "Reset that bai. Xem log."
    }
}

# 5. Initialize .env if missing or not in demo mode.
$envPath = Join-Path $root ".env"
$needInit = -not (Test-Path $envPath)
if (-not $needInit) {
    $isDemo = Select-String -Path $envPath -Pattern "^\s*DEMO_MODE\s*=\s*true" -Quiet
    if (-not $isDemo) {
        Write-Step ".env chua bat DEMO_MODE=true; chay init --demo de dam bao demo local."
        $needInit = $true
    }
}
if ($needInit) {
    Write-Step "Khoi tao .env, secrets va TLS..."
    & "$root\dx.ps1" init --demo 2>&1 | Tee-Object -FilePath $logFile -Append | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Stop-WithError "init --demo that bai. Xem log."
    }
}

# 6. Start the stack. Retry once for Docker Desktop APISIX race.
Write-Step "Khoi chay ha tang, app-install va seed..."
& "$root\dx.ps1" up 2>&1 | Tee-Object -FilePath $logFile -Append | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Step "Lan up dau that bai; doi 5 giay va thu lai..."
    Start-Sleep -Seconds 5
    & "$root\dx.ps1" up 2>&1 | Tee-Object -FilePath $logFile -Append | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Stop-WithError "Khong khoi chay duoc stack. Xem log."
    }
}

# 7. Wait for critical services.
$required = @(
    "dxos-postgres",
    "dxos-keycloak",
    "dxos-apisix",
    "dxos-doc-sign",
    "dxos-main-web",
    "dxos-bang-dieu-hanh-web"
)
foreach ($container in $required) {
    $healthy = $false
    for ($i = 0; $i -lt 90; $i++) {
        $status = docker inspect --format "{{.State.Health.Status}}" $container 2>$null
        if ($status -eq "healthy") {
            $healthy = $true
            break
        }
        Start-Sleep -Seconds 2
    }
    if (-not $healthy) {
        Stop-WithError "Container $container khong healthy sau 180 giay."
    }
    Write-Step "${container}: healthy"
}

# 7b. Verify the gateway actually answers HTTP (not just healthy container state).
$gatewayOk = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:8080/" -UseBasicParsing -TimeoutSec 5 -MaximumRedirection 3
        if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) {
            $gatewayOk = $true
            break
        }
    } catch {
        $gatewayOk = $false
    }
    Start-Sleep -Seconds 2
}
if (-not $gatewayOk) {
    Stop-WithError "Gateway http://localhost:8080 khong phan hoi. Kiem tra 'docker logs dxos-apisix' va log nay."
}
Write-Step "Gateway: http://localhost:8080 phan hoi OK"

# 8. Seed fallback if the DB is empty but demo-accounts.txt exists from an old run.
try {
    $userCount = docker exec dxos-postgres psql -U postgres -d dxos -t -A -c "SELECT count(*) FROM core.users_directory;" 2>$null
    $userCount = ($userCount | Out-String).Trim()
    if ($userCount -eq "0") {
        Write-Step "DB chua co user; chay app-install + seed..."
        & "$root\dx.ps1" app-install cap-phep 2>&1 | Tee-Object -FilePath $logFile -Append | Out-Null
        & "$root\dx.ps1" seed 2>&1 | Tee-Object -FilePath $logFile -Append | Out-Null
    }
} catch {
    Write-Step "WARN: khong kiem tra duoc users_directory: $($_.Exception.Message)"
}

# 9. Final doctor.
& "$root\dx.ps1" doctor 2>&1 | Tee-Object -FilePath $logFile -Append | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Step "WARN: doctor bao loi; kiem tra log neu web chua mo duoc."
} else {
    Write-Step "Doctor: PASS"
}

# 10. Open the app.
$appUrl = "http://localhost:8080"
$dashUrl = "http://localhost:8080/dieu-hanh/"
Write-Step "San sang: $appUrl"
Write-Step "Bang dieu hanh: $dashUrl"
Write-Step "Tai khoan demo: $root\secrets\demo-accounts.txt"
Write-Step "Log: $logFile"

if (-not $NoBrowser) {
    try {
        Start-Process $appUrl | Out-Null
        Write-Step "Da mo trinh duyet."
    } catch {
        Write-Step "WARN: khong mo duoc trinh duyet tu dong."
    }
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host " DX-OS DA SAN SANG" -ForegroundColor Green
Write-Host " Ung dung:      $appUrl" -ForegroundColor Green
Write-Host " Dieu hanh:     $dashUrl" -ForegroundColor Green
Write-Host " Tai khoan:     $root\secrets\demo-accounts.txt" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
