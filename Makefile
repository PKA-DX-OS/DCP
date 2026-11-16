# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

.PHONY: help init up up-full down reset app-install app-uninstall sync-users seed test e2e e2e-ui test-qa check-no-fakes smoke lint license-check sbom verify export-warm sensor sensor-spike eicar gitops bao-init bao-unseal postgrest-jwks backup restore release

APP ?= cap-phep
VERSION ?= 1.1.0
PYTHON ?= python3

help:
	@./dx.sh help

init:
	@./dx.sh init

up:
	@./dx.sh up

up-full:
	@./dx.sh up-full

down:
	@./dx.sh down

reset:
	@./dx.sh reset

app-install:
	@./dx.sh app-install $(APP)

app-uninstall:
	@./dx.sh app-uninstall $(APP)

sync-users:
	@./dx.sh sync-users

seed:
	@./dx.sh seed

test:
	@./dx.sh test

e2e:
	@./dx.sh e2e

e2e-ui:
	@./dx.sh e2e-ui

test-qa:
	@./dx.sh test-qa

check-no-fakes:
	@./dx.sh check-no-fakes

sbom:
	@$(PYTHON) scripts/sbom.py

verify:
	@./dx.sh verify

export-warm:
	@./dx.sh export-warm

sensor:
	@./dx.sh sensor

sensor-spike:
	@./dx.sh sensor-spike

eicar:
	@./dx.sh eicar

gitops:
	@./dx.sh gitops

bao-init:
	@./dx.sh bao-init

bao-unseal:
	@./dx.sh bao-unseal

postgrest-jwks:
	@./dx.sh postgrest-jwks

backup:
	@./dx.sh backup

restore:
	@./dx.sh restore

license-check:
	@./dx.sh license-check

lint:
	@./dx.sh lint

smoke:
	@./dx.sh init --demo
	@./dx.sh up
	@./dx.sh app-install cap-phep
	@./dx.sh seed
	@./dx.sh test
	@./dx.sh e2e

release:
	$(PYTHON) scripts/release.py --version $(VERSION)
