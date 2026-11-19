# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Z-06: số đo vượt ngưỡng -> outbox alert.threshold -> đúng một phiếu kiểm tra và một quy trình hậu kiểm."""

import re

from tests.integration._auth import ROOT
from tests.integration._ho_so import run_sql
from tests.integration._iot import cho, don_iot, get_sensor_token, gui_so_do, ma_site, phieu_cua, so_quy_trinh, tao_cong_trinh

# Số ngưỡng của luật tiếng ồn/bụi (70, 55, 100, 50) chỉ được nằm trong apps/*/rules/*.yaml
NGUONG = re.compile(r"(?<![\d.])(70|55|100|50)\.0(?!\d)")


def test_Z06_no_hardcoded_thresholds_in_services():
    hits = []
    for p in (ROOT / "services").rglob("*.py"):
        rel = p.relative_to(ROOT).as_posix()
        if "__pycache__" in rel:
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if NGUONG.search(code):
                hits.append(f"{rel}:{i}: {line.strip()[:100]}")
    assert not hits, "Còn số ngưỡng viết cứng trong services/:\n" + "\n".join(hits)


def test_Z06_iot_sensor_spike_triggers_hau_kiem():
    token = get_sensor_token("phuong-a")
    site_id = ma_site("CT-TEST-HK")
    tao_cong_trinh(site_id)
    try:
        # 5 lần vượt ngưỡng liên tiếp
        for _ in range(5):
            r = gui_so_do(token, site_id, {"laeq_dba": 85.0}, device_id="DEV-NOISE-85")
            assert r.status_code == 201, r.text
            assert r.json()["alerts"], "85 dBA phải vượt ngưỡng cả ngày lẫn đêm"

        assert cho(lambda: int(run_sql(
            "SELECT count(*) FROM core.outbox WHERE tenant = 'phuong-a' AND topic = 'alert.threshold' "
            f"AND payload->>'site_id' = '{site_id}';"
        ) or "0") >= 1), "Phải có sự kiện alert.threshold trong core.outbox"

        assert cho(lambda: len(phieu_cua(site_id)) >= 1), "Cảnh báo phải sinh phiếu kiểm tra"
        assert cho(lambda: so_quy_trinh(phieu_cua(site_id)[0]) == 1, timeout=20), "Phiếu phải có quy trình hậu kiểm"
        phieu = phieu_cua(site_id)
        assert len(phieu) == 1, f"5 lần vượt ngưỡng liên tiếp chỉ được sinh 1 phiếu, thực tế {len(phieu)}"

        info = run_sql(f"SELECT chi_so || '|' || nguong FROM app_cap_phep.phieu_kiem_tra WHERE id = '{phieu[0]}';")
        assert info.startswith("laeq_dba|70") or info.startswith("laeq_dba|55"), f"Phiếu phải ghi chỉ số và ngưỡng: {info}"
    finally:
        don_iot(site_id)
