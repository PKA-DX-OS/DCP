# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

.PHONY: help init init-demo up down reset logs ps doctor backup restore gitops seed sync-users app-install app-uninstall migrate config build test test-unit test-integration test-e2e check-no-fakes license-check sbom verify

APP ?= cap-phep
PYTHON ?= python3
COMPOSE ?= docker compose
DX ?= bash ./dx.sh

# Các mục vận hành gọi ./dx.sh (cùng tập lệnh với dx.ps1 trên Windows), không lặp lại logic ở đây.
help:
	@echo "Mục tiêu:"
	@echo "  make init-demo         Sinh .env, bí mật, chứng thư, cấu hình (DEMO_MODE=true)"
	@echo "  make init              Như trên nhưng DEMO_MODE=false"
	@echo "  make up                Build, chạy profile core, JWKS, OpenBao, cài app, seed (demo), doctor"
	@echo "  make down / reset      Dừng (giữ dữ liệu) / xóa toàn bộ dữ liệu (hỏi xác nhận)"
	@echo "  make doctor / ps / logs"
	@echo "  make backup / restore / gitops"
	@echo "  make app-install APP=cap-phep / seed / sync-users / migrate"
	@echo "  make test / test-integration / test-e2e"
	@echo "  make verify            compose config + no-fakes + license"
	@echo "Tương đương: ./dx.sh <lệnh>  (./dx.sh help để xem đủ)"

init:
	$(DX) init

init-demo:
	$(DX) init --demo

up:
	$(DX) up

down:
	$(DX) down

reset:
	$(DX) reset

logs:
	$(DX) logs

ps:
	$(DX) ps

doctor:
	$(DX) doctor

backup:
	$(DX) backup

restore:
	$(DX) restore

gitops:
	$(DX) gitops

seed:
	$(DX) seed

migrate:
	$(PYTHON) scripts/migrate.py

sync-users:
	$(DX) sync-users

app-install:
	$(DX) app-install $(APP)

app-uninstall:
	$(DX) app-uninstall $(APP)

config:
	$(COMPOSE) config >/dev/null
	@echo "compose.yaml hợp lệ"

build:
	$(COMPOSE) --profile core --profile tools build

test: test-unit

test-unit:
	$(PYTHON) -m pytest tests/unit -q

test-integration:
	$(PYTHON) -m pytest tests/integration -q

test-e2e:
	$(PYTHON) -m pytest tests/e2e tests/e2e-ui -q

check-no-fakes:
	$(PYTHON) scripts/check_no_fakes.py

license-check:
	$(PYTHON) scripts/license_check.py

sbom:
	$(PYTHON) scripts/sbom.py

verify: config check-no-fakes license-check
