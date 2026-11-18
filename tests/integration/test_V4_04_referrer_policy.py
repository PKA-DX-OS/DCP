# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Kiểm thử hồi quy bảo mật V4-04:
- Tất cả các tuyến đường qua Gateway APISIX đều có tiêu đề Referrer-Policy: same-origin
- Duy trì Content-Security-Policy nghiêm ngặt cho các giao diện web
- Duy trì X-Frame-Options và X-Content-Type-Options
"""

import httpx

def test_V4_04_referrer_policy_and_security_headers_on_all_routes():
    endpoints = [
        "http://localhost:8080/",
        "http://localhost:8080/dieu-hanh/",
        "http://localhost:8080/api/v1/health",
        "http://localhost:8080/kiem-tra/test-code"
    ]

    with httpx.Client(timeout=5.0) as client:
        for url in endpoints:
            resp = client.get(url)
            headers = resp.headers

            # 1. Kiểm tra Referrer-Policy
            ref_policy = headers.get("Referrer-Policy", "")
            assert ref_policy == "same-origin", f"Endpoint {url} thiếu hoặc sai Referrer-Policy: '{ref_policy}'"

            # 2. Kiểm tra X-Content-Type-Options và X-Frame-Options
            assert headers.get("X-Content-Type-Options") == "nosniff", f"Endpoint {url} thiếu X-Content-Type-Options"
            assert headers.get("X-Frame-Options") == "DENY", f"Endpoint {url} thiếu X-Frame-Options"

            # 3. Kiểm tra CSP trên các trang web SPA
            if url in ["http://localhost:8080/", "http://localhost:8080/dieu-hanh/"]:
                csp = headers.get("Content-Security-Policy", "")
                assert "default-src 'self'" in csp, f"Endpoint web {url} thiếu CSP nghiêm ngặt: '{csp}'"
