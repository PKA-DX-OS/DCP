# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""V3-01: cài và gỡ gói ứng dụng.

- compose.yaml không gắn migration của app vào initdb của PostgreSQL lõi.
- Bảng của app thuộc dxos_owner.
- Một gói app tạm (sinh trong apps/ lúc chạy, không có vai trò, BPMN) cài được rồi gỡ sạch:
  schema, chính sách, tri thức không còn; app cap-phep và lõi không bị ảnh hưởng.
- Cài lại cap-phep (upgrade) chạy lặp an toàn: số loại giấy tờ, số chính sách không đổi.

Lệnh app_manager chạy trong container tools (`docker compose --profile tools run tools ...`).
"""

import shutil
import subprocess
import uuid

from tests.integration.conftest import ROOT, run_psql, run_sql


def app_manager(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", "--profile", "tools", "run", "--rm", "-T", "tools", "scripts/app_manager.py", *args],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=300,
    )


def test_V3_01_compose_no_app_mount_and_table_owner():
    compose_text = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert "app-cap-phep.sql" not in compose_text, "compose.yaml vẫn gắn migration app vào PostgreSQL lõi"
    owner = run_sql("SELECT tableowner FROM pg_tables WHERE schemaname = 'app_cap_phep' AND tablename = 'ho_so';")
    assert owner == "dxos_owner", f"app_cap_phep.ho_so thuộc '{owner}', phải là dxos_owner"


def test_V3_01_cai_va_go_app_tam_khong_anh_huong_loi(don_dep):
    code = f"qa-tam-{uuid.uuid4().hex[:6]}"
    schema = "app_" + code.replace("-", "_")
    app_dir = ROOT / "apps" / code
    (app_dir / "db" / "migrations").mkdir(parents=True)
    don_dep(lambda: shutil.rmtree(app_dir, ignore_errors=True))
    (app_dir / "app.yaml").write_text(
        f"code: {code}\nname: Gói kiểm thử tạm\nversion: 0.0.1\nschema: {schema}\n"
        "tenants: [phuong-a]\nmigrations: db/migrations\n"
        "flow_policies:\n  task_list_variables: [ho_so_id]\n",
        encoding="utf-8",
    )
    (app_dir / "db" / "migrations" / "01.sql").write_text(
        f"CREATE TABLE IF NOT EXISTS {schema}.ban_ghi (id serial PRIMARY KEY, ten text);\n"
        f"INSERT INTO {schema}.ban_ghi (ten) VALUES ('mẫu');\n",
        encoding="utf-8",
    )
    # Phòng khi test dừng giữa chừng: gỡ schema và chính sách bằng superuser
    don_dep(lambda: run_psql(f"DROP SCHEMA IF EXISTS {schema} CASCADE; DELETE FROM core.app_policies WHERE app_code = '{code}';"))
    cap_phep_truoc = run_sql("SELECT count(*) FROM core.app_policies WHERE app_code = 'cap-phep';")

    r = app_manager("install", code)
    assert r.returncode == 0, f"Cài app tạm thất bại:\n{r.stdout[-1500:]}\n{r.stderr[-800:]}"
    assert run_sql(f"SELECT count(*) FROM {schema}.ban_ghi;") == "1"
    assert run_sql(f"SELECT nspowner::regrole::text FROM pg_namespace WHERE nspname = '{schema}';") == "dxos_owner"
    assert run_sql(f"SELECT count(*) FROM core.app_policies WHERE app_code = '{code}';") == "1"

    r = app_manager("uninstall", code)
    assert r.returncode == 0, f"Gỡ app tạm thất bại:\n{r.stdout[-1500:]}\n{r.stderr[-800:]}"
    assert run_sql(f"SELECT count(*) FROM pg_namespace WHERE nspname = '{schema}';") == "0", "Schema app tạm còn sau khi gỡ"
    assert run_sql(f"SELECT count(*) FROM core.app_policies WHERE app_code = '{code}';") == "0"
    assert run_sql("SELECT count(*) FROM core.app_policies WHERE app_code = 'cap-phep';") == cap_phep_truoc, \
        "Gỡ app tạm không được động tới chính sách của cap-phep"


def test_V3_01_upgrade_cap_phep_chay_lap_an_toan():
    def dem() -> tuple[str, str, str]:
        return (
            run_sql("SELECT count(*) FROM app_cap_phep.document_requirements;"),
            run_sql("SELECT count(*) FROM core.app_policies WHERE app_code = 'cap-phep';"),
            run_sql("SELECT count(*) FROM core.knowledge_chunks WHERE app = 'cap-phep';"),
        )

    for _ in range(2):
        r = app_manager("upgrade", "cap-phep")
        assert r.returncode == 0, f"upgrade cap-phep thất bại:\n{r.stdout[-1500:]}\n{r.stderr[-800:]}"
        if _ == 0:
            truoc = dem()
    assert dem() == truoc, f"Chạy lại upgrade làm đổi số bản ghi: {truoc} -> {dem()}"
    assert r.returncode == 0 and "không đổi, bỏ qua" in r.stdout, "Lần upgrade thứ hai không được deploy lại BPMN"


def test_V3_01_tenant_khong_khai_bao_bi_tu_choi():
    r = app_manager("install", "cap-phep", "--tenant", "phuong-khong-co")
    assert r.returncode == 2, f"Tenant không có trong app.yaml phải thoát mã 2, nhận {r.returncode}"
