#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Điểm vào vận hành DX-OS trên Linux/macOS. Bản Windows: dx.ps1 (cùng lệnh, cùng mã thoát).
# Mã thoát: 0 thành công; 1 lệnh con lỗi; 2 sai cú pháp; 3 reconciler phát hiện lệch.

set -uo pipefail
cd "$(dirname "$0")"

# Không để biến môi trường của máy lọt vào docker compose
unset KEYCLOAK_INTERNAL_URL FLOWABLE_URL POSTGRES_HOST 2>/dev/null || true

COMPOSE=(docker compose)
TOOLS=("${COMPOSE[@]}" --profile tools run --rm -T tools)

help_of() {
  case "$1" in
    init) echo "init [--demo]            Sinh .env, bí mật, chứng thư TLS, cấu hình Keycloak/APISIX (scripts/init.py)" ;;
    up) echo "up                       Build, chạy profile core, đồng bộ JWKS, mở khóa OpenBao (demo), cài app, seed, doctor" ;;
    down) echo "down                     Dừng mọi container (giữ volume dữ liệu)" ;;
    restart) echo "restart [dịch vụ...]     Khởi động lại toàn bộ hoặc vài dịch vụ" ;;
    ps) echo "ps                       Trạng thái và healthcheck các container" ;;
    doctor) echo "doctor [--bo-api]        Chẩn đoán: container, cổng, chứng thư, đĩa, Keycloak->PostgREST" ;;
    logs) echo "logs [dịch vụ...]        Xem log trực tiếp (Ctrl+C để thoát)" ;;
    backup) echo "backup                   Sao lưu CSDL, tệp, OpenBao, SoftHSM; mã hóa restic; ghi manifest mã băm" ;;
    restore) echo "restore [--list|--chi-kiem|--id ID] [--yes]  Phục hồi từ bản sao lưu (kiểm mã băm trước khi ghi)" ;;
    app-install) echo "app-install [app]        Cài hoặc nâng cấp gói ứng dụng (mặc định cap-phep)" ;;
    app-uninstall) echo "app-uninstall [app]      Gỡ gói ứng dụng (xóa schema của app, cần --yes)" ;;
    migrate) echo "migrate [--status|--dry-run] Chạy migration PostgreSQL lõi trên DB đang chạy" ;;
    seed) echo "seed [tham số seed.py]   Nạp dữ liệu mẫu và tài khoản demo" ;;
    sync-users) echo "sync-users               Đồng bộ người dùng Keycloak sang core.users_directory" ;;
    bao-init) echo "bao-init                 Khởi tạo OpenBao (Shamir 5/3) và khóa ký doc-sign" ;;
    bao-unseal) echo "bao-unseal               Mở khóa OpenBao" ;;
    postgrest-jwks) echo "postgrest-jwks           Đồng bộ JWKS Keycloak sang PostgREST rồi khởi động lại PostgREST" ;;
    gitops) echo "gitops [--apply]         Đối soát trạng thái mong muốn với thực tế; --apply để áp lại" ;;
    release) echo "release [phiên bản]      Đóng gói dist/dxos-<v>.tar.gz, SHA256SUMS, metadata" ;;
    reset) echo "reset [--yes]            Xóa container VÀ volume dữ liệu, sinh lại cấu hình (cần xác nhận)" ;;
    *) return 1 ;;
  esac
}
ORDER=(init up down restart ps doctor logs backup restore app-install app-uninstall seed sync-users bao-init bao-unseal postgrest-jwks gitops release reset)

usage() {
  echo "Cách dùng: ./dx.sh <lệnh> [tham số]    (./dx.sh <lệnh> --help để xem riêng một lệnh)"
  echo
  for c in "${ORDER[@]}"; do echo "  $(help_of "$c")"; done
}

is_demo() {
  [ "${DEMO_MODE:-}" = "true" ] || grep -qE '^[[:space:]]*DEMO_MODE[[:space:]]*=[[:space:]]*true' .env 2>/dev/null
}

need_env() {
  if [ ! -f .env ]; then
    echo "[ERROR] Chưa có .env. Chạy: ./dx.sh init --demo" >&2
    exit 1
  fi
}

host_python() {
  for p in python3 python; do
    if command -v "$p" >/dev/null 2>&1 && "$p" -c "import cryptography, yaml, httpx" >/dev/null 2>&1; then
      echo "$p"; return 0
    fi
  done
  return 1
}

run() { "$@" || exit 1; }

cmd_init() {
  if PY=$(host_python); then
    run "$PY" scripts/init.py "$@"
  else
    echo "--> Python trên máy thiếu cryptography/pyyaml/httpx; chạy init trong image tools..."
    # Build thẳng bằng docker build: chưa có .env thì docker compose không đọc được compose.yaml
    run docker build -f tools/Dockerfile -t dxos/tools:1.0 .
    # Chạy bằng uid/gid của người dùng để .env, secrets/ không thuộc root (Linux, WSL)
    run docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$(pwd):/app" -w /app dxos/tools:1.0 scripts/init.py "$@"
  fi
}

openbao_ready() {
  local raw
  raw=$("${COMPOSE[@]}" exec -T openbao bao status 2>&1 || true)
  if echo "$raw" | grep -qE 'Initialized[[:space:]]+false'; then
    if is_demo; then
      echo "[CẢNH BÁO] OpenBao chưa khởi tạo; tự khởi tạo vì DEMO_MODE=true"
      run "${TOOLS[@]}" scripts/bao_ops.py init
      run "${COMPOSE[@]}" restart doc-sign
    else
      echo "[ERROR] OpenBao chưa khởi tạo. Chạy: ./dx.sh bao-init" >&2; exit 1
    fi
  elif echo "$raw" | grep -qE 'Sealed[[:space:]]+true'; then
    if is_demo; then
      echo "[CẢNH BÁO] OpenBao đang khóa; tự mở vì DEMO_MODE=true (chỉ dùng cho demo)"
      run "${TOOLS[@]}" scripts/bao_ops.py unseal
      run "${COMPOSE[@]}" restart doc-sign
    else
      echo "[ERROR] OpenBao đang khóa. Chạy: ./dx.sh bao-unseal" >&2; exit 1
    fi
  else
    echo "  [OK] OpenBao đã mở khóa."
  fi
}

cmd_up() {
  need_env
  is_demo && echo "[CẢNH BÁO] DEMO_MODE=true: chỉ dùng thử nghiệm, không dùng cho môi trường thật."
  echo "--> Build image..."
  run "${COMPOSE[@]}" --profile core --profile tools build
  echo "--> Ghép route APISIX từ core/apisix/routes..."
  run "${TOOLS[@]}" scripts/build_apisix.py --from-env
  echo "--> Chạy profile core..."
  run "${COMPOSE[@]}" --profile core up -d --wait
  echo "--> Đồng bộ JWKS Keycloak sang PostgREST..."
  run "${TOOLS[@]}" scripts/fetch_jwks.py
  run "${COMPOSE[@]}" restart postgrest
  echo "--> Kiểm tra OpenBao..."
  openbao_ready
  echo "--> Cài/nâng cấp gói ứng dụng cap-phep..."
  run "${TOOLS[@]}" scripts/app_manager.py install cap-phep
  if [ ! -f secrets/demo-accounts.txt ] && is_demo; then
    echo "--> Nạp tài khoản và dữ liệu mẫu..."
    run "${TOOLS[@]}" apps/cap-phep/seed/seed.py
  fi
  echo "--> Đồng bộ danh mục người dùng..."
  "${TOOLS[@]}" scripts/sync_users.py || echo "  [WARN] sync_users lỗi, chạy lại: ./dx.sh sync-users"
  echo "--> Chẩn đoán..."
  run "${TOOLS[@]}" scripts/doctor.py
}

cmd_reset() {
  local ok=n
  for a in "$@"; do [ "$a" = "--yes" ] || [ "$a" = "-y" ] && ok=y; done
  if [ "$ok" != y ]; then
    read -r -p "Xóa toàn bộ container VÀ volume dữ liệu (CSDL, tệp, OpenBao, SoftHSM, bản sao lưu trong volume). Gõ XOA để tiếp tục: " ans
    [ "$ans" = "XOA" ] && ok=y
  fi
  if [ "$ok" != y ]; then echo "--> Đã hủy."; exit 1; fi
  run "${COMPOSE[@]}" --profile core --profile ai --profile sim --profile tools down -v
  rm -f secrets/demo-accounts.txt
  cmd_init
  echo "--> Đã reset. Chạy ./dx.sh up để dựng lại."
}

COMMAND="${1:-help}"
shift || true

case "$COMMAND" in
  help|-h|--help) usage; exit 0 ;;
esac

if ! help_of "$COMMAND" >/dev/null; then
  echo "[ERROR] Lệnh không hợp lệ: $COMMAND" >&2
  usage >&2
  exit 2
fi

for a in "$@"; do
  if [ "$a" = "--help" ] || [ "$a" = "-h" ]; then
    echo "./dx.sh $(help_of "$COMMAND")"
    exit 0
  fi
done

case "$COMMAND" in
  init)           cmd_init "$@" ;;
  up)             cmd_up ;;
  down)           run "${COMPOSE[@]}" --profile core --profile ai --profile sim --profile tools down ;;
  restart)        run "${COMPOSE[@]}" --profile core restart "$@" ;;
  ps)             run "${COMPOSE[@]}" --profile core ps ;;
  doctor)         need_env; run "${TOOLS[@]}" scripts/doctor.py "$@" ;;
  logs)           run "${COMPOSE[@]}" logs -f --tail=200 "$@" ;;
  backup)         need_env; run "${TOOLS[@]}" scripts/backup.py "$@" ;;
  restore)
    need_env
    # Cần TTY để hỏi xác nhận khi không có --yes
    if [[ " $* " == *" --yes "* || " $* " == *" --list "* || " $* " == *" --chi-kiem "* ]]; then
      run "${TOOLS[@]}" scripts/restore.py "$@"
    else
      run "${COMPOSE[@]}" --profile tools run --rm tools scripts/restore.py "$@"
    fi
    ;;
  app-install)    need_env; run "${TOOLS[@]}" scripts/app_manager.py install "${1:-cap-phep}" ;;
  app-uninstall)
    need_env
    if [[ " $* " != *" --yes "* ]]; then
      echo "[ERROR] Gỡ app xóa schema dữ liệu của app. Chạy lại với --yes để xác nhận." >&2; exit 1
    fi
    app="${1:-cap-phep}"; [ "$app" = "--yes" ] && app=cap-phep
    run "${TOOLS[@]}" scripts/app_manager.py uninstall "$app"
    ;;
  seed)           need_env; run "${TOOLS[@]}" apps/cap-phep/seed/seed.py "$@" ;;
  migrate)        need_env; PY=$(host_python) || PY=python3; run "$PY" scripts/migrate.py "$@" ;;
  sync-users)     need_env; run "${TOOLS[@]}" scripts/sync_users.py ;;
  bao-init)       need_env; run "${TOOLS[@]}" scripts/bao_ops.py init ;;
  bao-unseal)     need_env; run "${TOOLS[@]}" scripts/bao_ops.py unseal ;;
  postgrest-jwks) need_env; run "${TOOLS[@]}" scripts/fetch_jwks.py; run "${COMPOSE[@]}" restart postgrest ;;
  gitops)
    PY=$(host_python) || PY=python3
    "$PY" ops/reconciler/reconciler.py "$@"; exit $?
    ;;
  release)
    PY=$(host_python) || PY=python3
    run "$PY" scripts/release.py --version "${1:-1.0}"
    ;;
  reset)          cmd_reset "$@" ;;
esac
