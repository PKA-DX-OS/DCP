# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

.PHONY: help init preflight config build up up-full down reset logs ps test test-unit test-integration check-no-fakes license-check sbom verify app-install app-uninstall seed sync-users

APP ?= cap-phep
PYTHON ?= python3
COMPOSE ?= docker compose

help:
	@echo "Mục tiêu:"
	@echo "  make init              Tạo .env từ .env.example (chưa sinh secrets C11)"
	@echo "  make config            Kiểm tra compose.yaml"
	@echo "  make build             Build các image profile core"
	@echo "  make up                Chạy stack profile core"
	@echo "  make up-full           Chạy core + ai + sim + tools"
	@echo "  make down              Dừng stack"
	@echo "  make reset             Dừng và xóa volume"
	@echo "  make logs / make ps    Xem log / trạng thái"
	@echo "  make test              Chạy unit test"
	@echo "  make verify            config + no-fakes + license"
	@echo "  make app-install APP=cap-phep"
	@echo "  make seed              Nạp dữ liệu mẫu"

init:
	@if [ ! -f .env ]; then cp .env.example .env; echo "Đã tạo .env từ .env.example"; else echo ".env đã tồn tại"; fi
	@echo "Lưu ý: secrets/, chứng thư và cấu hình APISIX do C11 sinh; chưa có thì 'make up' sẽ lỗi."

preflight:
	@test -f .env || (echo "Thiếu .env: chạy 'make init' trước"; exit 1)
	@test -d secrets || (echo "Thiếu C11: secrets/; chưa thể up"; exit 1)
	@test -f scripts/softhsm_init.sh || (echo "Thiếu C11: scripts/softhsm_init.sh; chưa thể up"; exit 1)
	@test -f core/apisix/apisix.yaml || (echo "Thiếu C11: core/apisix/apisix.yaml; chưa thể up"; exit 1)
	@test -f core/postgrest/jwks.json || (echo "Thiếu C11: core/postgrest/jwks.json; chưa thể up"; exit 1)
	@test -d core/nats/certs || (echo "Thiếu C11: core/nats/certs; chưa thể up"; exit 1)

config:
	$(COMPOSE) config >/dev/null
	@echo "compose.yaml hợp lệ"

build:
	$(COMPOSE) --profile core build

up: preflight
	$(COMPOSE) --profile core up -d

up-full: preflight
	$(COMPOSE) --profile core --profile ai --profile sim --profile tools up -d

down:
	$(COMPOSE) down

reset:
	$(COMPOSE) down -v

logs:
	$(COMPOSE) logs -f --tail=100

ps:
	$(COMPOSE) ps

test: test-unit

test-unit:
	$(PYTHON) -m pytest tests/unit -q

test-integration:
	$(PYTHON) -m pytest tests/integration -q

check-no-fakes:
	$(PYTHON) scripts/check_no_fakes.py

license-check:
	$(PYTHON) scripts/license_check.py

sbom:
	$(PYTHON) scripts/sbom.py

verify: config check-no-fakes license-check

app-install:
	$(PYTHON) scripts/app_manager.py install --app $(APP)

app-uninstall:
	$(PYTHON) scripts/app_manager.py uninstall --app $(APP)

seed:
	$(PYTHON) apps/cap-phep/seed/seed.py

sync-users:
	$(PYTHON) scripts/sync_users.py
