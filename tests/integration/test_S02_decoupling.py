# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

from .grep_utils import grep_repo


def test_S02_zero_business_terms_in_core_and_services():
    """
    S-02: Đảm bảo nguyên tắc tách tầng (Rule 10, S-02).
    core/ và services/ không được chứa các từ khóa nghiệp vụ của cap-phep,
    đặc biệt là 'chu-dau-tu' / 'chu_dau_tu' phải được chuyển sang app.yaml (submitter_roles).
    """
    pattern = r"cap[-_.]phep|giay[-_.]phep|cong[-_.]trinh|xay[-_.]dung|qcvn|tham[-_.]dinh|lanh[-_.]dao|mot[-_.]cua|nguoiThamDinh|taskPhanCong|chu[-_.]dau[-_.]tu"
    output = grep_repo(pattern)
    matches = [line.strip() for line in output.splitlines() if line.strip()]
    assert len(matches) == 0, f"Phát hiện {len(matches)} vi phạm từ khóa nghiệp vụ trong core/services:\n" + "\n".join(matches)
