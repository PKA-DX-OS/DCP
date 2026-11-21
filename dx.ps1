# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Diem vao van hanh DX-OS tren Windows. Ban Linux/macOS: dx.sh (cung lenh, cung ma thoat).
# Ma thoat: 0 thanh cong; 1 lenh con loi; 2 sai cu phap; 3 reconciler phat hien lech.
# File chi dung ky tu ASCII de Windows PowerShell 5.1 doc dung khi khong co BOM.

$ErrorActionPreference = "Continue"
Set-Location -LiteralPath $PSScriptRoot

# Khong de bien moi truong cua may lot vao docker compose
foreach ($v in @("KEYCLOAK_INTERNAL_URL", "FLOWABLE_URL", "POSTGRES_HOST")) {
    Remove-Item "Env:$v" -ErrorAction SilentlyContinue
}

$Help = [ordered]@{
    "init"           = "init [--demo]            Sinh .env, bi mat, chung thu TLS, cau hinh Keycloak/APISIX (scripts/init.py)"
    "up"             = "up                       Build, chay profile core, dong bo JWKS, mo khoa OpenBao (demo), cai app, seed, doctor"
    "down"           = "down                     Dung moi container (giu volume du lieu)"
    "restart"        = "restart [dich vu...]     Khoi dong lai toan bo hoac vai dich vu"
    "ps"             = "ps                       Trang thai va healthcheck cac container"
    "doctor"         = "doctor [--bo-api]        Chan doan: container, cong, chung thu, dia, Keycloak->PostgREST"
    "logs"           = "logs [dich vu...]        Xem log truc tiep (Ctrl+C de thoat)"
    "backup"         = "backup                   Sao luu CSDL, tep, OpenBao, SoftHSM; ma hoa restic; ghi manifest ma bam"
    "restore"        = "restore [--list|--chi-kiem|--id ID] [--yes]  Phuc hoi tu ban sao luu (kiem ma bam truoc khi ghi)"
    "app-install"    = "app-install [app]        Cai hoac nang cap goi ung dung (mac dinh cap-phep)"
    "app-uninstall"  = "app-uninstall [app]      Go goi ung dung (xoa schema cua app, can --yes)"
    "migrate"        = "migrate [--status|--dry-run] Chay migration PostgreSQL loi tren DB dang chay"
    "seed"           = "seed [tham so seed.py]   Nap du lieu mau va tai khoan demo"
    "sync-users"     = "sync-users               Dong bo nguoi dung Keycloak sang core.users_directory"
    "bao-init"       = "bao-init                 Khoi tao OpenBao (Shamir 5/3) va khoa ky doc-sign"
    "bao-unseal"     = "bao-unseal               Mo khoa OpenBao"
    "postgrest-jwks" = "postgrest-jwks           Dong bo JWKS Keycloak sang PostgREST roi khoi dong lai PostgREST"
    "gitops"         = "gitops [--apply]         Doi soat trang thai mong muon voi thuc te; --apply de ap lai"
    "release"        = "release [phien ban]      Dong goi dist/dxos-<v>.tar.gz, SHA256SUMS, metadata"
    "reset"          = "reset [--yes]            Xoa container VA volume du lieu, sinh lai cau hinh (can xac nhan)"
}

function Show-Usage {
    Write-Host "Cach dung: .\dx.ps1 <lenh> [tham so]    (.\dx.ps1 <lenh> --help de xem rieng mot lenh)"
    Write-Host ""
    foreach ($k in $Help.Keys) { Write-Host "  $($Help[$k])" }
}

function Invoke-Step {
    # Chay lenh ngoai; loi thi thoat ma 1
    param([string]$Exe, [string[]]$ArgList)
    & $Exe @ArgList
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] $Exe $($ArgList -join ' ') -> ma $LASTEXITCODE" -ForegroundColor Red
        exit 1
    }
}

function Invoke-Tools {
    param([string[]]$ArgList, [switch]$Tty)
    $base = @("compose", "--profile", "tools", "run", "--rm")
    if (-not $Tty) { $base += "-T" }
    Invoke-Step "docker" ($base + @("tools") + $ArgList)
}

function Test-Demo {
    if ($env:DEMO_MODE -eq "true") { return $true }
    if (Test-Path ".env") { return [bool](Select-String -Path ".env" -Pattern "^\s*DEMO_MODE\s*=\s*true" -Quiet) }
    return $false
}

function Assert-Env {
    if (-not (Test-Path ".env")) {
        Write-Host "[ERROR] Chua co .env. Chay: .\dx.ps1 init --demo" -ForegroundColor Red
        exit 1
    }
}

function Get-HostPython {
    foreach ($p in @("python", "python3", "py")) {
        if (Get-Command $p -ErrorAction SilentlyContinue) {
            & $p -c "import cryptography, yaml, httpx" 2>$null
            if ($LASTEXITCODE -eq 0) { return $p }
        }
    }
    return $null
}

function Invoke-Init {
    param([string[]]$ArgList)
    $py = Get-HostPython
    if ($py) {
        Invoke-Step $py (@("scripts/init.py") + $ArgList)
    } else {
        Write-Host "--> Python tren may thieu cryptography/pyyaml/httpx; chay init trong image tools..."
        # Build thang bang docker build: chua co .env thi docker compose khong doc duoc compose.yaml
        Invoke-Step "docker" @("build", "-f", "tools/Dockerfile", "-t", "dxos/tools:1.1", ".")
        Invoke-Step "docker" (@("run", "--rm", "-v", "${PWD}:/app", "-w", "/app", "dxos/tools:1.1", "scripts/init.py") + $ArgList)
    }
}

function Confirm-OpenBao {
    $raw = (docker compose exec -T openbao bao status 2>&1 | Out-String)
    $demo = Test-Demo
    if ($raw -match "Initialized\s+false") {
        if (-not $demo) { Write-Host "[ERROR] OpenBao chua khoi tao. Chay: .\dx.ps1 bao-init" -ForegroundColor Red; exit 1 }
        Write-Host "[CANH BAO] OpenBao chua khoi tao; tu khoi tao vi DEMO_MODE=true" -ForegroundColor Yellow
        Invoke-Tools @("scripts/bao_ops.py", "init")
        Invoke-Step "docker" @("compose", "restart", "doc-sign")
    } elseif ($raw -match "Sealed\s+true") {
        if (-not $demo) { Write-Host "[ERROR] OpenBao dang khoa. Chay: .\dx.ps1 bao-unseal" -ForegroundColor Red; exit 1 }
        Write-Host "[CANH BAO] OpenBao dang khoa; tu mo vi DEMO_MODE=true (chi dung cho demo)" -ForegroundColor Yellow
        Invoke-Tools @("scripts/bao_ops.py", "unseal")
        Invoke-Step "docker" @("compose", "restart", "doc-sign")
    } else {
        Write-Host "  [OK] OpenBao da mo khoa."
    }
}

function Invoke-Up {
    Assert-Env
    if (Test-Demo) { Write-Host "[CANH BAO] DEMO_MODE=true: chi dung thu nghiem, khong dung cho moi truong that." -ForegroundColor Yellow }
    $ocrEngine = "0"
    if ((Test-Path Env:DH_OCR) -and ($env:DH_OCR -eq "true")) {
        $ocrEngine = "1"
    } elseif (Test-Path ".env") {
        $dhOcrLine = Get-Content ".env" | Select-String "^DH_OCR=true"
        if ($dhOcrLine) { $ocrEngine = "1" }
    }
    $env:OCR_ENGINE = $ocrEngine
    Write-Host "--> Build image..."
    Invoke-Step "docker" @("compose", "--profile", "core", "--profile", "tools", "build")
    Write-Host "--> Ghep route APISIX tu core/apisix/routes..."
    Invoke-Tools @("scripts/build_apisix.py", "--from-env")
    Write-Host "--> Khoa HMAC du lieu chu (giu khoa cu neu da co)..."
    Invoke-Tools @("scripts/dh_khoa.py")
    Write-Host "--> Chay profile core..."
    Invoke-Step "docker" @("compose", "--profile", "core", "up", "-d", "--wait")
    Write-Host "--> Dong bo JWKS Keycloak sang PostgREST..."
    Invoke-Tools @("scripts/fetch_jwks.py")
    Invoke-Step "docker" @("compose", "restart", "postgrest")
    Write-Host "--> Kiem tra OpenBao..."
    Confirm-OpenBao
    Write-Host "--> Chay migration PostgreSQL loi..."
    $pyMigrate = Get-HostPython
    if (-not $pyMigrate) { $pyMigrate = "python" }
    Invoke-Step $pyMigrate @("scripts/migrate.py")
    Write-Host "--> Cai/nang cap goi ung dung cap-phep..."
    Invoke-Tools @("scripts/app_manager.py", "install", "cap-phep")
    Write-Host "--> Nap kho van ban phap luat (chay lai khong tao trung)..."
    Invoke-Step $pyMigrate @("scripts/seed_legal.py")
    Write-Host "--> Khop du lieu va backfill MDM (mdm_backfill.py)..."
    docker compose --profile tools run --rm -T tools scripts/mdm_backfill.py
    if ($LASTEXITCODE -ne 0) { Write-Host "  [WARN] MDM backfill loi, chay lai: docker compose --profile tools run --rm tools scripts/mdm_backfill.py" -ForegroundColor Yellow }
    Write-Host "--> Cham chat luong du lieu (DQ worker)..."
    docker compose --profile tools run --rm -T tools scripts/data_quality_worker.py
    if ($LASTEXITCODE -ne 0) { Write-Host "  [WARN] DQ worker loi, chay lai: docker compose --profile tools run --rm tools scripts/data_quality_worker.py" -ForegroundColor Yellow }
    if ((-not (Test-Path "secrets\demo-accounts.txt")) -and (Test-Demo)) {
        Write-Host "--> Nap tai khoan va du lieu mau..."
        Invoke-Tools @("apps/cap-phep/seed/seed.py")
    }
    Write-Host "--> Dong bo danh muc nguoi dung..."
    docker compose --profile tools run --rm -T tools scripts/sync_users.py
    if ($LASTEXITCODE -ne 0) { Write-Host "  [WARN] sync_users loi, chay lai: .\dx.ps1 sync-users" -ForegroundColor Yellow }
    Write-Host "--> Chan doan..."
    Invoke-Tools @("scripts/doctor.py")
}

function Invoke-Reset {
    param([string[]]$ArgList)
    $ok = ($ArgList -contains "--yes") -or ($ArgList -contains "-y")
    if (-not $ok) {
        $ans = Read-Host "Xoa toan bo container VA volume du lieu (CSDL, tep, OpenBao, SoftHSM, ban sao luu trong volume). Go XOA de tiep tuc"
        $ok = ($ans -eq "XOA")
    }
    if (-not $ok) { Write-Host "--> Da huy."; exit 1 }
    Invoke-Step "docker" @("compose", "--profile", "core", "--profile", "ai", "--profile", "sim", "--profile", "tools", "down", "-v")
    Remove-Item "secrets\demo-accounts.txt" -ErrorAction SilentlyContinue
    Invoke-Init @()
    Write-Host "--> Da reset. Chay .\dx.ps1 up de dung lai."
}

$Command = if ($args.Count -gt 0) { [string]$args[0] } else { "help" }
$Rest = @()
if ($args.Count -gt 1) { $Rest = @($args[1..($args.Count - 1)] | ForEach-Object { [string]$_ }) }

if (@("help", "-h", "--help") -contains $Command) { Show-Usage; exit 0 }
if (-not $Help.Contains($Command)) {
    Write-Host "[ERROR] Lenh khong hop le: $Command" -ForegroundColor Red
    Show-Usage
    exit 2
}
if (($Rest -contains "--help") -or ($Rest -contains "-h")) {
    Write-Host ".\dx.ps1 $($Help[$Command])"
    exit 0
}

switch ($Command) {
    "init"           { Invoke-Init $Rest }
    "up"             { Invoke-Up }
    "down"           { Invoke-Step "docker" @("compose", "--profile", "core", "--profile", "ai", "--profile", "sim", "--profile", "tools", "down") }
    "restart"        { Invoke-Step "docker" (@("compose", "--profile", "core", "restart") + $Rest) }
    "ps"             { Invoke-Step "docker" @("compose", "--profile", "core", "ps") }
    "doctor"         { Assert-Env; Invoke-Tools (@("scripts/doctor.py") + $Rest) }
    "logs"           { Invoke-Step "docker" (@("compose", "logs", "-f", "--tail=200") + $Rest) }
    "backup"         { Assert-Env; Invoke-Tools (@("scripts/backup.py") + $Rest) }
    "restore" {
        Assert-Env
        $noTty = ($Rest -contains "--yes") -or ($Rest -contains "--list") -or ($Rest -contains "--chi-kiem")
        if ($noTty) { Invoke-Tools (@("scripts/restore.py") + $Rest) } else { Invoke-Tools (@("scripts/restore.py") + $Rest) -Tty }
    }
    "app-install"    { Assert-Env; $app = if ($Rest.Count -gt 0) { $Rest[0] } else { "cap-phep" }; Invoke-Tools @("scripts/app_manager.py", "install", $app) }
    "app-uninstall" {
        Assert-Env
        if (-not ($Rest -contains "--yes")) {
            Write-Host "[ERROR] Go app xoa schema du lieu cua app. Chay lai voi --yes de xac nhan." -ForegroundColor Red
            exit 1
        }
        $app = @($Rest | Where-Object { $_ -ne "--yes" })[0]
        if (-not $app) { $app = "cap-phep" }
        Invoke-Tools @("scripts/app_manager.py", "uninstall", $app)
    }
    "seed"           { Assert-Env; Invoke-Tools (@("apps/cap-phep/seed/seed.py") + $Rest) }
    "migrate"        {
        $py = Get-HostPython
        if (-not $py) { $py = "python" }
        Invoke-Step $py (@("scripts/migrate.py") + $Rest)
    }
    "sync-users"     { Assert-Env; Invoke-Tools @("scripts/sync_users.py") }
    "bao-init"       { Assert-Env; Invoke-Tools @("scripts/bao_ops.py", "init") }
    "bao-unseal"     { Assert-Env; Invoke-Tools @("scripts/bao_ops.py", "unseal") }
    "postgrest-jwks" { Assert-Env; Invoke-Tools @("scripts/fetch_jwks.py"); Invoke-Step "docker" @("compose", "restart", "postgrest") }
    "gitops" {
        $py = Get-HostPython
        if (-not $py) { $py = "python" }
        & $py (@("ops/reconciler/reconciler.py") + $Rest)
        exit $LASTEXITCODE
    }
    "release" {
        $py = Get-HostPython
        if (-not $py) { $py = "python" }
        $ver = if ($Rest.Count -gt 0) { $Rest[0] } else { "1.1" }
        Invoke-Step $py @("scripts/release.py", "--version", $ver)
    }
    "reset"          { Invoke-Reset $Rest }
}
exit 0
