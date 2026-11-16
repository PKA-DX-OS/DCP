# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

[CmdletBinding()]
param(
    [Parameter(Position=0)]
    [string]$Command = "help",

    [Parameter(Position=1, ValueFromRemainingArguments=$true)]
    [string[]]$ArgsList
)

$ErrorActionPreference = "Continue"

# Dam bao khong bi ro ri bien moi truong cua host vao docker compose
Remove-Item env:KEYCLOAK_INTERNAL_URL -ErrorAction SilentlyContinue
Remove-Item env:FLOWABLE_URL -ErrorAction SilentlyContinue
Remove-Item env:POSTGRES_HOST -ErrorAction SilentlyContinue

function Ensure-Tools-Image {
    docker compose --profile tools build tools
}

# Chon Python tren may host: uu tien venv dang bat, roi py -3.12 (neu thuc su co),
# cuoi cung la python trong PATH. Truoc day chi kiem tra lenh py co ton tai nen
# may khong cai Python 3.12 bao "No suitable Python runtime found".
# Ham don gian (khong co param) de cac doi so nhu "-m" duoc chuyen nguyen ven qua $args.
function Invoke-HostPython {
    $pyArgs = $args
    if ($env:VIRTUAL_ENV -and (Get-Command python -ErrorAction SilentlyContinue)) {
        & python @pyArgs
        return
    }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.12 -c "import sys" *> $null
        if ($LASTEXITCODE -eq 0) {
            & py -3.12 @pyArgs
            return
        }
    }
    & python @pyArgs
}

switch ($Command) {
    "init" {
        Write-Host "--> Khoi tao moi truong bao mat DX-OS (.env, secrets)..." -ForegroundColor Cyan
        $initArgs = @()
        if ($ArgsList -contains "--demo" -or $ArgsList -contains "-demo" -or $ArgsList -contains "-Demo") {
            $initArgs += "--demo"
        }
        $initOk = $false
        if (Get-Command py -ErrorAction SilentlyContinue) {
            & py -3.12 -c "import cryptography" 2>$null
            if ($LASTEXITCODE -eq 0) {
                & py -3.12 scripts/init.py @initArgs
                if ($LASTEXITCODE -eq 0) { $initOk = $true }
            }
        }
        if (-not $initOk -and (Get-Command python -ErrorAction SilentlyContinue)) {
            & python -c "import cryptography" 2>$null
            if ($LASTEXITCODE -eq 0) {
                & python scripts/init.py @initArgs
                if ($LASTEXITCODE -eq 0) { $initOk = $true }
            }
        }
        if (-not $initOk) {
            Write-Host "--> Host Python thieu cryptography; dung tools container de khoi tao..." -ForegroundColor Yellow
            docker build -f tools/Dockerfile -t dxos/tools:1.1.0 .
            if ($LASTEXITCODE -ne 0) { exit 1 }
            docker run --rm -v "${PWD}:/app" -w /app dxos/tools:1.1.0 python scripts/init.py @initArgs
            if ($LASTEXITCODE -ne 0) { exit 1 }
        }
        Write-Host "--> Xay dung cac hinh anh container DX-OS..." -ForegroundColor Cyan
        docker compose --profile core --profile tools build
    }

    "up" {
        $isDemo = $env:DEMO_MODE -eq "true"
        if (-not $isDemo -and (Test-Path ".env")) {
            $matchDemo = Select-String -Path ".env" -Pattern "^\s*DEMO_MODE\s*=\s*true" -Quiet
            if ($matchDemo) { $isDemo = $true }
        }
        if ($isDemo) {
            Write-Host "[CANH BAO] DX-OS dang chay o che do DEMO_MODE=true! Che do nay chi danh cho thu nghiem, khong dung cho moi truong san xuat!" -ForegroundColor Yellow
        }

        Write-Host "--> Xay dung va kiem tra cap nhat cac hinh anh container..." -ForegroundColor Cyan
        docker compose --profile core --profile tools build
        Write-Host "--> Khoi chay dich vu Loi Tang 1 (profile: core)..." -ForegroundColor Cyan
        docker compose --profile core up -d --wait
        # Fallback: Docker Desktop đôi khi tạo APISIX nhưng chưa start
        $apisixStatus = docker inspect --format "{{.State.Status}}" dxos-apisix 2>$null
        if ($apisixStatus -ne "running") {
            Write-Host "--> APISIX chưa chạy, thử start lại..." -ForegroundColor Yellow
            docker start dxos-apisix
            Start-Sleep -Seconds 5
        }
        Ensure-Tools-Image
        Write-Host "--> Dong bo khoa JWKS Keycloak sang PostgREST..." -ForegroundColor Cyan
        docker compose run --rm -T tools python scripts/fetch_jwks.py
        docker compose restart postgrest

        Write-Host "--> Kiem tra trang thai OpenBao KMS..." -ForegroundColor Cyan
        $baoRaw = docker compose exec -T openbao bao status 2>&1
        $baoExit = $LASTEXITCODE
        $isInitialized = $baoRaw -match "Initialized\s+true"
        $isSealed = ($baoExit -ne 0) -or ($baoRaw -match "Sealed\s+true")

        if (-not $isInitialized) {
            $isDemo = $env:DEMO_MODE -eq "true"
            if (-not $isDemo -and (Test-Path ".env")) {
                $matchDemo = Select-String -Path ".env" -Pattern "^\s*DEMO_MODE\s*=\s*true" -Quiet
                if ($matchDemo) { $isDemo = $true }
            }
            if ($isDemo) {
                Write-Host "[CANH BAO] OpenBao KMS chua duoc khoi tao. Tu dong khoi tao (bao-init) vi DEMO_MODE=true..." -ForegroundColor Yellow
                docker compose run --rm -T tools python scripts/bao_ops.py init
                if ($LASTEXITCODE -ne 0) {
                    Write-Host "[ERROR] Tu dong khoi tao OpenBao that bai!" -ForegroundColor Red
                    exit 1
                }
                docker compose restart doc-sign
            } else {
                Write-Host "[ERROR] OpenBao KMS chua duoc khoi tao! Vui long chay: .\dx.ps1 bao-init" -ForegroundColor Red
                exit 1
            }
        } elseif ($isSealed) {
            $isDemo = $env:DEMO_MODE -eq "true"
            if (-not $isDemo -and (Test-Path ".env")) {
                $matchDemo = Select-String -Path ".env" -Pattern "^\s*DEMO_MODE\s*=\s*true" -Quiet
                if ($matchDemo) { $isDemo = $true }
            }
            if ($isDemo) {
                Write-Host "[CANH BAO] OpenBao KMS dang bi khoa (Sealed). Tu dong mo khoa (bao-unseal) vi DEMO_MODE=true (Chi dung cho moi truong demo/thu nghiem!)" -ForegroundColor Yellow
                docker compose run --rm -T tools python scripts/bao_ops.py unseal
                if ($LASTEXITCODE -ne 0) {
                    Write-Host "[ERROR] Tu dong mo khoa OpenBao that bai!" -ForegroundColor Red
                    exit 1
                }
                docker compose restart doc-sign
            } else {
                Write-Host "[ERROR] OpenBao KMS dang bi khoa (Sealed)! Vui long chay: .\dx.ps1 bao-unseal" -ForegroundColor Red
                exit 1
            }
        } else {
            Write-Host "  [OK] OpenBao KMS da mo khoa va san sang." -ForegroundColor Green
        }

        # Luon dong bo goi ung dung (migrations/manifest/policies) de nang cap stack cu.
        Write-Host "--> Dong bo goi ung dung cap-phep (migrations/manifest/policies)..." -ForegroundColor Cyan
        docker compose run --rm -T tools python scripts/app_manager.py install cap-phep
        if (-not (Test-Path "secrets/demo-accounts.txt")) {
            Write-Host "--> Khoi tao tai khoan mau va ho so kich ban ban dau..." -ForegroundColor Cyan
            docker compose run --rm -T tools python apps/cap-phep/seed/seed.py
        }
        Write-Host "--> Dong bo danh muc nguoi dung tu Keycloak sang users_directory..." -ForegroundColor Cyan
        docker compose run --rm -T tools python scripts/sync_users.py
        Write-Host "--> Chay chan doan he thong (dx doctor)..." -ForegroundColor Cyan
        docker compose run --rm -T tools python scripts/doctor.py
    }

    "doctor" {
        Ensure-Tools-Image
        docker compose run --rm tools python scripts/doctor.py
    }

    "up-full" {
        Write-Host "--> Khoi chay toan bo he sinh thai (core + ai + sim)..." -ForegroundColor Cyan
        docker compose --profile core --profile ai --profile sim up -d --wait
    }

    "down" {
        Write-Host "--> Dung toan bo cac container he thong..." -ForegroundColor Yellow
        docker compose --profile core --profile ai --profile sim --profile tools down
    }

    "ps" {
        docker compose ps
    }

    "logs" {
        docker compose logs -f $ArgsList
    }

    "bao-init" {
        Ensure-Tools-Image
        docker compose run --rm -T tools python scripts/bao_ops.py init
    }

    "bao-unseal" {
        Ensure-Tools-Image
        docker compose run --rm -T tools python scripts/bao_ops.py unseal
    }

    "postgrest-jwks" {
        Ensure-Tools-Image
        docker compose run --rm -T tools python scripts/fetch_jwks.py
        docker compose restart postgrest
    }

    "app-install" {
        Ensure-Tools-Image
        $app = if ($ArgsList.Count -gt 0) { $ArgsList[0] } else { "cap-phep" }
        docker compose run --rm -T tools python scripts/app_manager.py install $app
    }

    "app-uninstall" {
        Ensure-Tools-Image
        $app = if ($ArgsList.Count -gt 0) { $ArgsList[0] } else { "cap-phep" }
        docker compose run --rm -T tools python scripts/app_manager.py uninstall $app
    }

    "sync-users" {
        Ensure-Tools-Image
        docker compose run --rm -T tools python scripts/sync_users.py
    }

    "seed" {
        Ensure-Tools-Image
        docker compose run --rm -T tools python apps/cap-phep/seed/seed.py
    }

    "verify" {
        Ensure-Tools-Image
        docker compose run --rm -T tools python scripts/verify_audit.py
    }

    "export-warm" {
        Ensure-Tools-Image
        docker compose run --rm -T tools python services/export-warm/main.py
    }

    "backup" {
        Ensure-Tools-Image
        docker compose run --rm -T tools python scripts/backup.py
    }

    "restore" {
        Ensure-Tools-Image
        docker compose run --rm -T tools python scripts/restore.py
    }

    "gitops" {
        Invoke-HostPython ops/reconciler/reconciler.py
    }

    "sensor" {
        Ensure-Tools-Image
        docker compose run --rm -T tools python tools/sensor-sim/sim.py --endpoint http://apisix:8080/api/v1/ingest
    }

    "sensor-spike" {
        Ensure-Tools-Image
        docker compose run --rm -T tools python tools/sensor-sim/sim.py --endpoint http://apisix:8080/api/v1/ingest --spike --duration 120
    }

    "demo-sensor" {
        $envFile = ".env"
        $demoMode = $false
        if (Test-Path $envFile) {
            $content = Get-Content $envFile -Raw
            if ($content -match "DEMO_MODE\s*=\s*(true|1)") {
                $demoMode = $true
            }
        }
        if (-not $demoMode -and $env:DEMO_MODE -ne "true") {
            Write-Error "demo-sensor chi hoat dong khi DEMO_MODE=true"
            exit 1
        }
        $site = $ArgsList[0]
        if (-not $site) {
            Write-Error "Thieu ma_cong_trinh: .\dx.ps1 demo-sensor <ma_cong_trinh> [laeq_dba]"
            exit 1
        }
        $laeq = if ($ArgsList.Length -gt 1) { $ArgsList[1] } else { "86.5" }
        Ensure-Tools-Image
        docker compose run --rm -T tools python tools/sensor-sim/sim.py --endpoint http://apisix:8080/api/v1/ingest --site $site --laeq $laeq
    }

    "eicar" {
        Ensure-Tools-Image
        docker compose run --rm -T tools python scripts/upload_eicar.py
    }

    "test" {
        Ensure-Tools-Image
        docker compose run --rm -T tools pytest tests/unit -v
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        docker compose run --rm -T tools python scripts/scan_exposure.py
    }

    "e2e" {
        Ensure-Tools-Image
        docker compose run --rm -T tools pytest tests/e2e -v
    }

    "e2e-ui" {
        Invoke-HostPython -m pytest tests/e2e-ui -v
    }

    "test-qa" {
        Invoke-HostPython -m pytest tests/integration -q
    }

    "check-no-fakes" {
        Ensure-Tools-Image
        docker compose run --rm -T tools python scripts/check_no_fakes.py
    }

    "sbom" {
        Invoke-HostPython scripts/sbom.py
    }

    "release" {
        $version = if ($ArgsList.Length -gt 0) { $ArgsList[0] } else { "1.1.0" }
        Invoke-HostPython scripts/release.py --version $version
    }

    "lint" {
        Ensure-Tools-Image
        Write-Host "--> [LINT] Chay ruff check..." -ForegroundColor Cyan
        docker compose run --rm -T tools ruff check .
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        Write-Host "--> [LINT] Kiem tra TypeScript cap-phep-web..." -ForegroundColor Cyan
        docker compose run --rm -T -w /app/apps/cap-phep/web tools sh -c "npm ls --depth=0 >/dev/null 2>&1 || npm ci; npm run type-check"
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        Write-Host "--> [LINT] Kiem tra TypeScript bang-dieu-hanh-web..." -ForegroundColor Cyan
        docker compose run --rm -T -w /app/apps/bang-dieu-hanh/web tools sh -c "npm ls --depth=0 >/dev/null 2>&1 || npm ci; npm run type-check"
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        Write-Host "--> [LINT] Hoan tat kiem tra ma nguon (PASS)." -ForegroundColor Green
    }

    "license-check" {
        Ensure-Tools-Image
        Write-Host "--> [LICENSE] Kiem tra tuan thu ban quyen REUSE..." -ForegroundColor Cyan
        docker compose run --rm -T tools reuse lint
    }

    "reset" {
        $confirm = $false
        if ($ArgsList -contains "--yes" -or $ArgsList -contains "-y") {
            $confirm = $true
        } else {
            $ans = Read-Host "CANH BAO: Thao tac nay se xoa sach toan bo co so du lieu va volume he thong! Ban co chac chan? [y/N]"
            if ($ans -eq "y" -or $ans -eq "Y") {
                $confirm = $true
            }
        }

        if ($confirm) {
            Write-Host "--> Dang xoa sach container va volume..." -ForegroundColor Red
            docker compose --profile core --profile ai --profile sim --profile tools down -v --remove-orphans
            Remove-Item -Path "secrets\demo-accounts.txt" -Force -ErrorAction SilentlyContinue
            Ensure-Tools-Image
            docker compose run --rm -T tools python scripts/init.py
            Write-Host "--> Da reset toan bo he thong ve trang thai ban dau sach se." -ForegroundColor Green
        } else {
            Write-Host "--> Da huy thao tac reset." -ForegroundColor Yellow
        }
    }

    Default {
        Write-Host "========================================================================" -ForegroundColor Green
        Write-Host "                   DX-OS OPEN-CORE (v1.1) - CLI QUAN TRI               " -ForegroundColor Green
        Write-Host "========================================================================" -ForegroundColor Green
        Write-Host "  .\dx.ps1 init           : Khoi tao .env, chung chi TLS va tep bi mat  "
        Write-Host "  .\dx.ps1 up             : Khoi chay Loi Tang 1 (profile: core)        "
        Write-Host "  .\dx.ps1 up-full        : Khoi chay toan bo (core + ai + sim)         "
        Write-Host "  .\dx.ps1 down           : Dung toan bo cac container he thong         "
        Write-Host "  .\dx.ps1 ps             : Xem trang thai va healthcheck cac dich vu   "
        Write-Host "  .\dx.ps1 logs           : Xem log truc tiep cua he thong              "
        Write-Host "  .\dx.ps1 bao-init       : Khoi tao Shamir 5/3 va tao khoa cho doc-sign"
        Write-Host "  .\dx.ps1 bao-unseal     : Mo khoa Unseal OpenBao KMS                  "
        Write-Host "  .\dx.ps1 postgrest-jwks : Dong bo khoa JWKS Keycloak sang PostgREST   "
        Write-Host "  .\dx.ps1 app-install    : Cai dat goi ung dung (mac dinh: cap-phep)   "
        Write-Host "  .\dx.ps1 app-uninstall  : Go bo goi ung dung                          "
        Write-Host "  .\dx.ps1 seed           : Nap 10 tai khoan mau va ho so kich ban demo "
        Write-Host "  .\dx.ps1 verify         : Xac minh tinh toan ven chuoi bam kiem toan  "
        Write-Host "  .\dx.ps1 export-warm    : Dong goi Parquet sang Data Lake SeaweedFS   "
        Write-Host "  .\dx.ps1 sensor-spike   : Gia lap tieng on 78 dBA kich hoat hau kiem  "
        Write-Host "  .\dx.ps1 lint           : Kiem tra ruff va TypeScript                 "
        Write-Host "  .\dx.ps1 license-check  : Kiem tra ban quyen ma nguon bang reuse      "
        Write-Host "  .\dx.ps1 gitops         : Chay chu ky doi soat cau hinh GitOps        "
        Write-Host "  .\dx.ps1 backup         : Sao luu toan dien he thong                  "
        Write-Host "  .\dx.ps1 restore        : Phuc hoi tham hoa va do thoi gian RTO       "
        Write-Host "  .\dx.ps1 doctor         : Chan doan ket noi va xac thuc token PostgREST"
        Write-Host "  .\dx.ps1 test           : Chay bo kiem thu don vi"
        Write-Host "  .\dx.ps1 e2e            : Chay 13 kich ban E2E qua APISIX"
        Write-Host "  .\dx.ps1 e2e-ui         : Chay 11 buoc UI E2E bang Playwright"
        Write-Host "  .\dx.ps1 test-qa        : Chay bo integration/security tren host"
        Write-Host "  .\dx.ps1 check-no-fakes : Quet ma gia/mock/fallback"
        Write-Host "  .\dx.ps1 sbom           : Sinh SBOM CycloneDX
  .\dx.ps1 release        : Dong goi tar.gz + SHA256SUMS"
        Write-Host "  .\dx.ps1 reset          : Dat lai toan bo du lieu (yeu cau xac nhan)  "
        Write-Host "========================================================================" -ForegroundColor Green
    }
}

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
