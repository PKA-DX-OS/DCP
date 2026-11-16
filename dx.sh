#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

set -euo pipefail

# Dam bao khong bi ro ri bien moi truong cua host vao docker compose
unset KEYCLOAK_INTERNAL_URL || true
unset FLOWABLE_URL || true
unset POSTGRES_HOST || true

COMMAND="${1:-help}"
shift || true

ensure_tools_image() {
    docker compose --profile tools build tools
}

case "$COMMAND" in
    init)
        echo "--> Khởi tạo môi trường bảo mật DX-OS (.env, secrets)..."
        shift
        if command -v python3 >/dev/null 2>&1 && python3 -c "import cryptography" >/dev/null 2>&1; then
            python3 scripts/init.py "$@"
        elif command -v python >/dev/null 2>&1 && python -c "import cryptography" >/dev/null 2>&1; then
            python scripts/init.py "$@"
        else
            echo "--> Host Python thieu cryptography; dung tools container de khoi tao..."
            docker build -f tools/Dockerfile -t dxos/tools:1.1.0 .
            docker run --rm -v "$(pwd):/app" -w /app dxos/tools:1.1.0 python scripts/init.py "$@"
        fi
        echo "--> Xây dựng các hình ảnh container DX-OS..."
        docker compose --profile core --profile tools build
        ;;
    up)
        IS_DEMO=false
        if [ "$DEMO_MODE" = "true" ] || grep -q "^\s*DEMO_MODE\s*=\s*true" .env 2>/dev/null; then
            IS_DEMO=true
            echo -e "\033[1;33m[CẢNH BÁO] DX-OS đang chạy ở chế độ DEMO_MODE=true! Chế độ này chỉ dành cho thử nghiệm, không dùng cho môi trường sản xuất!\033[0m"
        fi

        echo "--> Xây dựng và kiểm tra cập nhật các hình ảnh container..."
        docker compose --profile core --profile tools build
        echo "--> Khởi chạy dịch vụ Lõi Tầng 1 (profile: core)..."
        docker compose --profile core up -d --wait
        # Fallback: Docker Desktop đôi khi tạo APISIX nhưng chưa start
        apisix_status=$(docker inspect --format '{{.State.Status}}' dxos-apisix 2>/dev/null || true)
        if [ "$apisix_status" != "running" ]; then
            echo "--> APISIX chưa chạy, thử start lại..."
            docker start dxos-apisix
            sleep 5
        fi
        ensure_tools_image
        echo "--> Đồng bộ khóa JWKS Keycloak sang PostgREST..."
        docker compose run --rm -T tools python scripts/fetch_jwks.py
        docker compose restart postgrest

        echo "--> Kiểm tra trạng thái OpenBao KMS..."
        BAO_RAW=$(docker compose exec -T openbao bao status 2>&1 || true)
        if echo "$BAO_RAW" | grep -q "Initialized\s*false"; then
            IS_DEMO=false
            if [ "$DEMO_MODE" = "true" ] || grep -q "^\s*DEMO_MODE\s*=\s*true" .env 2>/dev/null; then
                IS_DEMO=true
            fi
            if [ "$IS_DEMO" = "true" ]; then
                echo "[CẢNH BÁO] OpenBao KMS chưa được khởi tạo. Tự động khởi tạo (bao-init) vì DEMO_MODE=true..."
                docker compose run --rm -T tools python scripts/bao_ops.py init
                if [ $? -ne 0 ]; then
                    echo "[ERROR] Tự động khởi tạo OpenBao thất bại!"
                    exit 1
                fi
                docker compose restart doc-sign
            else
                echo "[ERROR] OpenBao KMS chưa được khởi tạo! Vui lòng chạy: ./dx.sh bao-init"
                exit 1
            fi
        elif echo "$BAO_RAW" | grep -q "Sealed\s*true" || ! docker compose exec -T openbao bao status >/dev/null 2>&1; then
            IS_DEMO=false
            if [ "$DEMO_MODE" = "true" ] || grep -q "^\s*DEMO_MODE\s*=\s*true" .env 2>/dev/null; then
                IS_DEMO=true
            fi
            if [ "$IS_DEMO" = "true" ]; then
                echo "[CẢNH BÁO] OpenBao KMS đang bị khóa (Sealed). Tự động mở khóa (bao-unseal) vì DEMO_MODE=true (Chỉ dùng cho môi trường demo/thử nghiệm!)"
                docker compose run --rm -T tools python scripts/bao_ops.py unseal
                if [ $? -ne 0 ]; then
                    echo "[ERROR] Tự động mở khóa OpenBao thất bại!"
                    exit 1
                fi
                docker compose restart doc-sign
            else
                echo "[ERROR] OpenBao KMS đang bị khóa (Sealed)! Vui lòng chạy: ./dx.sh bao-unseal"
                exit 1
            fi
        else
            echo "  [OK] OpenBao KMS đã mở khóa và sẵn sàng."
        fi

        # Luon dong bo goi ung dung (migrations/manifest/policies) de nang cap stack cu.
        echo "--> Dong bo goi ung dung cap-phep (migrations/manifest/policies)..."
        docker compose run --rm -T tools python scripts/app_manager.py install cap-phep
        if [ ! -f "secrets/demo-accounts.txt" ]; then
            echo "--> Khởi tạo tài khoản mẫu và hồ sơ kịch bản ban đầu..."
            docker compose run --rm -T tools python apps/cap-phep/seed/seed.py
        fi
        echo "--> Đồng bộ danh mục người dùng từ Keycloak sang users_directory..."
        docker compose run --rm -T tools python scripts/sync_users.py || true
        echo "--> Chạy chẩn đoán hệ thống (dx doctor)..."
        docker compose run --rm -T tools python scripts/doctor.py
        ;;
    doctor)
        ensure_tools_image
        docker compose run --rm tools python scripts/doctor.py
        ;;
    up-full)
        echo "--> Khởi chạy toàn bộ hệ sinh thái (core + ai + sim)..."
        docker compose --profile core --profile ai --profile sim up -d --wait
        ;;
    down)
        echo "--> Dừng toàn bộ các container hệ thống..."
        docker compose --profile core --profile ai --profile sim --profile tools down
        ;;
    ps)
        docker compose ps
        ;;
    logs)
        docker compose logs -f "$@"
        ;;
    bao-init)
        ensure_tools_image
        docker compose run --rm -T tools python scripts/bao_ops.py init
        ;;
    bao-unseal)
        ensure_tools_image
        docker compose run --rm -T tools python scripts/bao_ops.py unseal
        ;;
    postgrest-jwks)
        ensure_tools_image
        docker compose run --rm -T tools python scripts/fetch_jwks.py
        docker compose restart postgrest
        ;;
    app-install)
        ensure_tools_image
        APP="${1:-cap-phep}"
        docker compose run --rm -T tools python scripts/app_manager.py install "$APP"
        ;;
    app-uninstall)
        ensure_tools_image
        APP="${1:-cap-phep}"
        docker compose run --rm -T tools python scripts/app_manager.py uninstall "$APP"
        ;;
    sync-users)
        ensure_tools_image
        docker compose run --rm -T tools python scripts/sync_users.py
        ;;
    seed)
        ensure_tools_image
        docker compose run --rm -T tools python apps/cap-phep/seed/seed.py
        ;;
    verify)
        ensure_tools_image
        docker compose run --rm -T tools python scripts/verify_audit.py
        ;;
    export-warm)
        ensure_tools_image
        docker compose run --rm -T tools python services/export-warm/main.py
        ;;
    backup)
        ensure_tools_image
        docker compose run --rm -T tools python scripts/backup.py
        ;;
    restore)
        ensure_tools_image
        docker compose run --rm -T tools python scripts/restore.py
        ;;
    gitops)
        python3 ops/reconciler/reconciler.py 2>/dev/null || python ops/reconciler/reconciler.py
        ;;
    sensor)
        ensure_tools_image
        docker compose run --rm -T tools python tools/sensor-sim/sim.py --endpoint http://apisix:8080/api/v1/ingest
        ;;
    sensor-spike)
        ensure_tools_image
        docker compose run --rm -T tools python tools/sensor-sim/sim.py --endpoint http://apisix:8080/api/v1/ingest --spike --duration 120
        ;;
    demo-sensor)
        demo_mode=$(grep -E "^DEMO_MODE=" .env 2>/dev/null | cut -d '=' -f2 | tr -d ' "\r\n')
        if [ "$demo_mode" != "true" ] && [ "$DEMO_MODE" != "true" ]; then
            echo "demo-sensor chi hoat dong khi DEMO_MODE=true" >&2
            exit 1
        fi
        site="$1"
        if [ -z "$site" ]; then
            echo "Thieu ma_cong_trinh: ./dx.sh demo-sensor <ma_cong_trinh> [laeq_dba]" >&2
            exit 1
        fi
        laeq="${2:-86.5}"
        ensure_tools_image
        docker compose run --rm -T tools python tools/sensor-sim/sim.py --endpoint http://apisix:8080/api/v1/ingest --site "$site" --laeq "$laeq"
        ;;
    eicar)
        ensure_tools_image
        docker compose run --rm -T tools python scripts/upload_eicar.py
        ;;
    test)
        ensure_tools_image
        docker compose run --rm -T tools pytest tests/unit -v
        docker compose run --rm -T tools python scripts/scan_exposure.py
        ;;
    e2e)
        ensure_tools_image
        docker compose run --rm -T tools pytest tests/e2e -v
        ;;
    e2e-ui)
        python3 -m pytest tests/e2e-ui -v 2>/dev/null || python -m pytest tests/e2e-ui -v
        ;;
    test-qa)
        python3 -m pytest tests/integration -q 2>/dev/null || python -m pytest tests/integration -q
        ;;
    check-no-fakes)
        ensure_tools_image
        docker compose run --rm -T tools python scripts/check_no_fakes.py
        ;;
    sbom)
        python3 scripts/sbom.py 2>/dev/null || python scripts/sbom.py
        ;;
    release)
        version="${1:-1.1.0}"
        python3 scripts/release.py --version "$version" 2>/dev/null || python scripts/release.py --version "$version"
        ;;
    lint)
        ensure_tools_image
        echo "--> [LINT] Chạy ruff check..."
        docker compose run --rm -T tools ruff check .
        echo "--> [LINT] Kiểm tra TypeScript cap-phep-web..."
        docker compose run --rm -T -w /app/apps/cap-phep/web tools sh -c "[ -d node_modules ] || npm ci; npm run type-check"
        echo "--> [LINT] Kiểm tra TypeScript bang-dieu-hanh-web..."
        docker compose run --rm -T -w /app/apps/bang-dieu-hanh/web tools sh -c "[ -d node_modules ] || npm ci; npm run type-check"
        echo "--> [LINT] Hoàn tất kiểm tra mã nguồn (PASS)."
        ;;
    license-check)
        ensure_tools_image
        echo "--> [LICENSE] Kiểm tra tuân thủ bản quyền REUSE..."
        docker compose run --rm -T tools reuse lint
        ;;
    reset)
        CONFIRM="n"
        for arg in "$@"; do
            if [ "$arg" = "--yes" ] || [ "$arg" = "-y" ]; then
                CONFIRM="y"
            fi
        done
        if [ "$CONFIRM" != "y" ]; then
            read -r -p "CẢNH BÁO: Thao tác này sẽ xóa sạch toàn bộ cơ sở dữ liệu và volume hệ thống! Bạn có chắc chắn? [y/N] " ANS
            if [ "$ANS" = "y" ] || [ "$ANS" = "Y" ]; then
                CONFIRM="y"
            fi
        fi

        if [ "$CONFIRM" = "y" ]; then
            echo "--> Đang xóa sạch container và volume..."
            docker compose --profile core --profile ai --profile sim --profile tools down -v --remove-orphans
            rm -f secrets/demo-accounts.txt
            ensure_tools_image
            docker run --rm -T -v "$(pwd):/app" -w /app dxos/tools:1.1.0 python scripts/init.py
            echo "--> Đã reset toàn bộ hệ thống về trạng thái ban đầu sạch sẽ."
        else
            echo "--> Đã hủy thao tác reset."
        fi
        ;;
    *)
        echo "========================================================================"
        echo "                   DX-OS OPEN-CORE (v1.1) - CLI QUẢN TRỊ               "
        echo "========================================================================"
        echo "  ./dx.sh init           : Khởi tạo .env, chứng chỉ TLS và tệp bí mật  "
        echo "  ./dx.sh up             : Khởi chạy Lõi Tầng 1 (profile: core)        "
        echo "  ./dx.sh up-full        : Khởi chạy toàn bộ (core + ai + sim)         "
        echo "  ./dx.sh down           : Dừng toàn bộ các container hệ thống         "
        echo "  ./dx.sh ps             : Xem trạng thái và healthcheck các dịch vụ   "
        echo "  ./dx.sh logs           : Xem log trực tiếp của hệ thống              "
        echo "  ./dx.sh bao-init       : Khởi tạo Shamir 5/3 và tạo khóa cho doc-sign"
        echo "  ./dx.sh bao-unseal     : Mở khóa Unseal OpenBao KMS                  "
        echo "  ./dx.sh postgrest-jwks : Đồng bộ khóa JWKS Keycloak sang PostgREST   "
        echo "  ./dx.sh app-install    : Cài đặt gói ứng dụng (mặc định: cap-phep)   "
        echo "  ./dx.sh app-uninstall  : Gỡ bỏ gói ứng dụng                          "
        echo "  ./dx.sh seed           : Nạp 10 tài khoản mẫu và hồ sơ kịch bản demo "
        echo "  ./dx.sh verify         : Xác minh tính toàn vẹn chuỗi băm kiểm toán  "
        echo "  ./dx.sh export-warm    : Đóng gói Parquet sang Data Lake SeaweedFS   "
        echo "  ./dx.sh sensor-spike   : Giả lập tiếng ồn 78 dBA kích hoạt hậu kiểm  "
        echo "  ./dx.sh lint           : Kiểm tra ruff và TypeScript                 "
        echo "  ./dx.sh license-check  : Kiểm tra bản quyền mã nguồn bằng reuse      "
        echo "  ./dx.sh gitops         : Chạy chu kỳ đối soát cấu hình GitOps        "
        echo "  ./dx.sh backup         : Sao lưu toàn diện hệ thống                  "
        echo "  ./dx.sh restore        : Phục hồi thảm họa và đo thời gian RTO       "
        echo "  ./dx.sh test           : Chay bo kiem thu don vi"
        echo "  ./dx.sh e2e            : Chay 13 kich ban E2E qua APISIX"
        echo "  ./dx.sh e2e-ui         : Chay 11 buoc UI E2E bang Playwright"
        echo "  ./dx.sh test-qa        : Chay bo integration/security tren host"
        echo "  ./dx.sh check-no-fakes : Quet ma gia/mock/fallback"
        echo "  ./dx.sh sbom           : Sinh SBOM CycloneDX
  ./dx.sh release        : Dong goi tar.gz + SHA256SUMS"
        echo "  ./dx.sh reset          : Đặt lại toàn bộ dữ liệu (yêu cầu xác nhận)  "
        echo "========================================================================"
        ;;
esac
