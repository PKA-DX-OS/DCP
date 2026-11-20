# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B-TEST-03: khả năng tiếp cận, đa trình duyệt và hiệu năng.

- Đa trình duyệt: chạy cả bộ e2e-ui với `--browser chromium --browser firefox --browser webkit`
  (conftest.py). Tệp này thêm phép thử khói chạy được trên mọi trình duyệt.
- Tiếp cận: axe-core (bản trong node_modules của app cấp phép) trên các màn chính mà test_B_a11y.py
  chưa phủ: Keycloak, tra cứu công khai, bàn làm việc, chi tiết hồ sơ, thẩm định thiết kế. Chặn lỗi
  mức serious/critical.
- Hiệu năng (đo tương đương Lighthouse, chỉ Chromium): thời gian DOMContentLoaded, load, LCP, tổng
  dung lượng JS/CSS tải về của các trang chính, so với ngân sách ghi dưới đây.

Kết quả mỗi lần chạy ghi vào E2E_OUT_DIR/qa/ket-qua-<trình duyệt>.json và .md (ngày giờ, commit,
phiên bản trình duyệt, hệ điều hành) để chép vào docs/QA_RESULTS_*.md.
Cần stack đã `dx up` với DEMO_MODE=true, `python scripts/seed_hero.py` và `npm ci` trong apps/cap-phep/web.
"""

import json
import os
import platform
import re
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from tests.integration._auth import DEMO_ACCOUNTS_FILE, GATEWAY_URL, ROOT

sync_api = pytest.importorskip("playwright.sync_api")
expect = sync_api.expect

BASE_URL = os.getenv("E2E_BASE_URL", GATEWAY_URL).rstrip("/")
AXE = ROOT / "apps" / "cap-phep" / "web" / "node_modules" / "axe-core" / "axe.min.js"
OUT = Path(os.getenv("E2E_OUT_DIR") or ROOT / "logs" / "e2e-ui") / "qa"
CHO = 20000

# Ngân sách hiệu năng trên máy chạy stack (mạng nội bộ, không giả lập 3G)
NGAN_SACH = {"dcl_ms": 2500, "load_ms": 4000, "lcp_ms": 2500, "js_css_kb": 1500}

KET_QUA: dict = {"axe": {}, "hieu_nang": {}, "khoi": {}}


def _mat_khau(user: str) -> str:
    if not DEMO_ACCOUNTS_FILE.exists():
        pytest.skip("Thiếu secrets/demo-accounts.txt")
    for line in DEMO_ACCOUNTS_FILE.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split(":")
        if len(parts) >= 2 and parts[0] == user:
            return parts[1]
    pytest.skip(f"Thiếu tài khoản demo {user}")


def _dang_nhap(page, user: str, url: str = "/") -> None:
    dich = f"{BASE_URL}{url}"
    page.goto(dich, wait_until="domcontentloaded")
    page.get_by_role("button", name="Đăng nhập", exact=True).click()
    page.locator("#username").fill(user)
    page.locator("#password").fill(_mat_khau(user))
    page.locator("#kc-login").click()
    page.wait_for_url(re.compile(re.escape(dich) + r"(\?.*)?$"), timeout=CHO)


def _axe(page, ten: str) -> list:
    if not AXE.exists():
        pytest.skip("Thiếu axe-core: chạy `npm ci` trong apps/cap-phep/web")
    page.add_script_tag(path=str(AXE))
    # Đo trạng thái cuối: kết thúc hiệu ứng chuyển cảnh trước khi tính độ tương phản
    page.evaluate("() => document.getAnimations().forEach((a) => { try { a.finish(); } catch (e) {} })")
    res = page.evaluate("async () => await axe.run(document, {resultTypes: ['violations']})")
    nang = [v for v in res["violations"] if v["impact"] in ("serious", "critical")]
    KET_QUA["axe"][ten] = {
        "serious_critical": [f"{v['id']} ({len(v['nodes'])})" for v in nang],
        "khac": [f"{v['id']}:{v['impact']}" for v in res["violations"] if v not in nang],
        # Ghi phần tử của mọi vi phạm (kể cả mức thấp) để sửa được ngay từ báo cáo
        "chi_tiet": [
            {"id": v["id"], "impact": v["impact"], "target": n.get("target"), "html": (n.get("html") or "")[:200],
             "ly_do": n.get("failureSummary")}
            for v in res["violations"] for n in v["nodes"][:5]
        ],
    }
    return nang


def _mo_ta(loi: list) -> list:
    """Thông điệp lỗi kèm phần tử vi phạm để sửa được ngay từ log."""
    return [f"{v['id']}: {', '.join(str(n.get('target')) for n in v['nodes'][:5])}" for v in loi]


@pytest.fixture()
def ctx(trinh_duyet):
    # bypass_csp: CSP chặn chèn axe-core; chỉ dùng trong test
    c = trinh_duyet.new_context(
        viewport={"width": 1366, "height": 900}, locale="vi-VN", bypass_csp=True, reduced_motion="reduce"
    )
    yield c
    c.close()


@pytest.fixture(scope="module", autouse=True)
def ghi_ket_qua(trinh_duyet):
    KET_QUA.update({"axe": {}, "hieu_nang": {}, "khoi": {}})
    yield
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except OSError:
        commit = "?"
    moi_truong = {
        "ngay_gio": datetime.now().astimezone().isoformat(timespec="seconds"),
        "commit": commit or "?",
        "trinh_duyet": f"{trinh_duyet.browser_type.name} {trinh_duyet.version}",
        "he_dieu_hanh": f"{platform.system()} {platform.release()} {platform.machine()}",
        "python": platform.python_version(),
        "base_url": BASE_URL,
        "ngan_sach": NGAN_SACH,
    }
    ten = trinh_duyet.browser_type.name
    (OUT / f"ket-qua-{ten}.json").write_text(json.dumps({"moi_truong": moi_truong, **KET_QUA}, ensure_ascii=False, indent=2), encoding="utf-8")
    dong = [f"## {moi_truong['trinh_duyet']}", "",
            f"- Ngày giờ: {moi_truong['ngay_gio']}; commit `{moi_truong['commit']}`",
            f"- Môi trường: {moi_truong['he_dieu_hanh']}, Python {moi_truong['python']}, {BASE_URL}", ""]
    if KET_QUA["khoi"]:
        dong += ["| Màn hình | Kết quả |", "| :--- | :--- |"] + [f"| {k} | {v} |" for k, v in KET_QUA["khoi"].items()] + [""]
    if KET_QUA["axe"]:
        dong += ["| Màn hình (axe) | serious/critical | Mức khác |", "| :--- | :--- | :--- |"]
        dong += [f"| {k} | {', '.join(v['serious_critical']) or 'không'} | {', '.join(v['khac']) or 'không'} |" for k, v in KET_QUA["axe"].items()]
        dong.append("")
        chi_tiet = [(k, c) for k, v in KET_QUA["axe"].items() for c in v.get("chi_tiet", [])]
        if chi_tiet:
            dong += ["Phần tử vi phạm:", ""] + [f"- {k}: `{c['id']}` ({c.get('impact')}) tại `{c['target']}`" for k, c in chi_tiet] + [""]
    if KET_QUA["hieu_nang"]:
        dong += ["| Trang | DCL (ms) | load (ms) | LCP (ms) | JS+CSS (KB) |", "| :--- | ---: | ---: | ---: | ---: |"]
        dong += [f"| {k} | {v['dcl_ms']} | {v['load_ms']} | {v['lcp_ms']} | {v['js_css_kb']} |" for k, v in KET_QUA["hieu_nang"].items()]
    (OUT / f"ket-qua-{ten}.md").write_text("\n".join(dong) + "\n", encoding="utf-8")


# ---------- Đa trình duyệt: phép thử khói ----------

def test_khoi_trang_chao_va_tra_cuu(ctx, trinh_duyet):
    p = ctx.new_page()
    p.goto(f"{BASE_URL}/", wait_until="domcontentloaded")
    expect(p.get_by_role("button", name="Đăng nhập", exact=True)).to_be_visible(timeout=CHO)
    r = p.goto(f"{BASE_URL}/kiem-tra/", wait_until="domcontentloaded")
    assert r is not None and r.status == 200
    expect(p.locator("input[name='ma']")).to_be_visible(timeout=CHO)
    KET_QUA["khoi"]["trang chào, tra cứu"] = "đạt"


def test_khoi_dang_nhap_va_ban_lam_viec(ctx, trinh_duyet):
    p = ctx.new_page()
    _dang_nhap(p, "mc.thu")
    p.locator("nav[aria-label='Điều hướng']").get_by_role("button", name="Bàn làm việc", exact=True).click()
    expect(p.get_by_role("button", name="Mở hồ sơ đầy đủ").first).to_be_visible(timeout=CHO)
    p.get_by_role("button", name="Mở hồ sơ đầy đủ").first.click()
    expect(p.locator("[role='dialog']").first).to_be_visible(timeout=CHO)
    KET_QUA["khoi"]["đăng nhập, bàn làm việc, chi tiết hồ sơ"] = "đạt"


def test_khoi_bang_dieu_hanh(ctx, trinh_duyet):
    p = ctx.new_page()
    _dang_nhap(p, "ld.hoa", "/dieu-hanh/")
    expect(p.get_by_text("Hồ sơ theo trạng thái")).to_be_visible(timeout=CHO)
    KET_QUA["khoi"]["bảng điều hành"] = "đạt"


# ---------- Khả năng tiếp cận ----------

def test_axe_keycloak_va_tra_cuu(ctx):
    p = ctx.new_page()
    p.goto(f"{BASE_URL}/kiem-tra/", wait_until="domcontentloaded")
    loi = _axe(p, "tra cứu công khai")
    p.goto(f"{BASE_URL}/", wait_until="domcontentloaded")
    p.get_by_role("button", name="Đăng nhập", exact=True).click()
    p.locator("#username").wait_for(timeout=CHO)
    loi += _axe(p, "đăng nhập Keycloak")
    assert loi == [], _mo_ta(loi)


def test_axe_ban_lam_viec_va_chi_tiet(ctx):
    p = ctx.new_page()
    _dang_nhap(p, "mc.thu")
    p.locator("nav[aria-label='Điều hướng']").get_by_role("button", name="Bàn làm việc", exact=True).click()
    p.get_by_role("button", name="Mở hồ sơ đầy đủ").first.wait_for(timeout=CHO)
    loi = _axe(p, "bàn làm việc")
    p.get_by_role("button", name="Mở hồ sơ đầy đủ").first.click()
    p.locator("[role='dialog']").first.wait_for(timeout=CHO)
    loi += _axe(p, "chi tiết hồ sơ (cán bộ)")
    assert loi == [], _mo_ta(loi)


def test_axe_tham_dinh_thiet_ke(ctx):
    p = ctx.new_page()
    _dang_nhap(p, "cdt.minh")
    p.locator("#txt-tim-ho-so").fill("CP-HERO-2026-001")
    p.locator("tr, li").filter(has_text="CP-HERO-2026-001").first.get_by_role("button").first.click(timeout=CHO)
    p.locator("#muc-thiet-ke").wait_for(timeout=CHO)
    loi = _axe(p, "thẩm định thiết kế (chủ đầu tư)")
    assert loi == [], _mo_ta(loi)


# ---------- Hiệu năng (Chromium) ----------

DO_TRANG = """
async () => {
  const lcp = await new Promise((ok) => {
    let v = 0;
    try {
      new PerformanceObserver((l) => { for (const e of l.getEntries()) v = Math.max(v, e.startTime); })
        .observe({ type: 'largest-contentful-paint', buffered: true });
    } catch (e) { ok(null); return; }
    setTimeout(() => ok(v || null), 1500);
  });
  const nav = performance.getEntriesByType('navigation')[0];
  const tep = performance.getEntriesByType('resource').filter((r) => /\\.(js|css)(\\?|$)/.test(r.name));
  return {
    dcl_ms: Math.round(nav.domContentLoadedEventEnd),
    load_ms: Math.round(nav.loadEventEnd),
    lcp_ms: lcp === null ? null : Math.round(lcp),
    js_css_kb: Math.round(tep.reduce((s, r) => s + (r.transferSize || r.encodedBodySize || 0), 0) / 1024),
  };
}
"""


def _do(page, ten: str, url: str) -> dict:
    page.goto(url, wait_until="load")
    kq = page.evaluate(DO_TRANG)
    KET_QUA["hieu_nang"][ten] = kq
    return kq


def _trong_ngan_sach(kq: dict) -> list:
    return [f"{k}={kq[k]} > {v}" for k, v in NGAN_SACH.items() if kq.get(k) is not None and kq[k] > v]


def test_hieu_nang_trang_chinh(trinh_duyet):
    if trinh_duyet.browser_type.name != "chromium":
        pytest.skip("Chỉ số LCP và transferSize đo trên Chromium")
    c = trinh_duyet.new_context(viewport={"width": 1366, "height": 900}, locale="vi-VN")
    try:
        p = c.new_page()
        vuot = []
        vuot += [f"trang chào: {x}" for x in _trong_ngan_sach(_do(p, "trang chào /", f"{BASE_URL}/"))]
        vuot += [f"tra cứu: {x}" for x in _trong_ngan_sach(_do(p, "tra cứu /kiem-tra/", f"{BASE_URL}/kiem-tra/"))]
        _dang_nhap(p, "ld.hoa", "/dieu-hanh/")
        vuot += [f"bảng điều hành: {x}" for x in _trong_ngan_sach(_do(p, "bảng điều hành /dieu-hanh/", f"{BASE_URL}/dieu-hanh/"))]
        assert vuot == [], f"Vượt ngân sách hiệu năng {NGAN_SACH}: {vuot}"
    finally:
        c.close()
