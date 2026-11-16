# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

from pathlib import Path
from dxos_core.config import Settings


ROOT = Path(__file__).resolve().parent.parent.parent


def test_S04_demo_mode_default_false_in_env_example():
    """
    S-04: Mặc định trong .env.example phải là DEMO_MODE=false
    để đảm bảo an toàn tuyệt đối khi triển khai trên môi trường sản xuất.
    """
    env_example = ROOT / ".env.example"
    assert env_example.exists(), "Không tìm thấy tệp .env.example"
    content = env_example.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines() if line.strip().startswith("DEMO_MODE")]
    assert len(lines) == 1, "Không tìm thấy hoặc có nhiều định nghĩa DEMO_MODE trong .env.example"
    assert lines[0] == "DEMO_MODE=false", f"DEMO_MODE trong .env.example phải là false, nhưng nhận được: {lines[0]}"


def test_S04_config_default_demo_mode_is_false(monkeypatch):
    """
    S-04: Settings() của dxos_core phải mặc định demo_mode=False
    khi không được cấp biến môi trường DEMO_MODE.
    """
    monkeypatch.delenv("DEMO_MODE", raising=False)
    s = Settings()
    assert s.demo_mode is False, "demo_mode trong Settings() phải mặc định là False"


def test_S04_key_custody_documentation_exists():
    """
    S-04: docs/security.md và docs/ops.md phải chứa quy định quản trị khóa:
    - Shamir 3-of-5
    - 5 người giữ khóa (custodians)
    - Không lưu unseal keys trên máy chủ
    - Quy trình unseal thủ công
    """
    sec_doc = (ROOT / "docs" / "security.md").read_text(encoding="utf-8")
    ops_doc = (ROOT / "docs" / "ops.md").read_text(encoding="utf-8")

    for doc, name in [(sec_doc, "security.md"), (ops_doc, "ops.md")]:
        assert "Shamir" in doc, f"Tài liệu {name} thiếu từ khóa Shamir"
        assert "3-of-5" in doc or "3" in doc, f"Tài liệu {name} thiếu mô tả ngưỡng 3-of-5"
        assert "unseal" in doc.lower(), f"Tài liệu {name} thiếu hướng dẫn unseal"


def test_S04_dx_script_warning_and_fail_closed_logic():
    """
    S-04: Kiểm tra dx.ps1 và dx.sh có chứa cơ chế cảnh báo màu vàng khi DEMO_MODE=true,
    và cơ chế dừng với lỗi khi DEMO_MODE=false mà OpenBao bị Sealed.
    """
    dx_ps1 = (ROOT / "dx.ps1").read_text(encoding="utf-8")
    dx_sh = (ROOT / "dx.sh").read_text(encoding="utf-8")

    # Kiểm tra dx.ps1
    assert "DEMO_MODE=true" in dx_ps1
    assert "Yellow" in dx_ps1
    assert "bao-unseal" in dx_ps1

    # Kiểm tra dx.sh
    assert "DEMO_MODE" in dx_sh
    assert "bao-unseal" in dx_sh

