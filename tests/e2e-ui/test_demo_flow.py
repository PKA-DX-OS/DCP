# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Hành trình demo trên giao diện thật cap-phep-web (C15), chạy bằng Playwright cho Python.

Mỗi người dùng đăng nhập Keycloak (PKCE) trong một ngữ cảnh trình duyệt riêng.

1. mc.thu mở Bàn làm việc, chờ kết nối thông báo "Trực tuyến".
2. cdt.minh nộp hồ sơ trên giao diện: điền form, tải 6 giấy tờ bắt buộc (biến thể của tệp mẫu
   fixtures/ban_ve_thiet_ke_mau.pdf), nhập ngày cấp/hết hạn giấy tờ đất.
3. Chuông của mc.thu tăng (SSE); mc.thu thấy việc của hồ sơ và mở xem chi tiết.
4. Một cửa tiếp nhận, lãnh đạo phân công td.binh: gọi API vì giao diện chưa có biểu mẫu
   cho việc nhận theo nhóm (candidate) và biến quy trình của các bước này.
5. td.binh thấy việc được giao trên Bàn làm việc và bấm Hoàn thành.
6. td.cuong (không được giao) xin truy cập khẩn qua API; ld.hoa duyệt ở tab Truy cập khẩn;
   sau đó td.cuong mở được hồ sơ.
7. Lãnh đạo phê duyệt (API, cùng lý do ở bước 4); hook ký số cấp giấy phép, hồ sơ sang DA_CAP.
8. cdt.minh xem giấy phép và chữ ký số, nhật ký có truy cập khẩn, tải PDF giấy phép.
9. Trang /kiem-tra/{mã} không cần đăng nhập: Hợp lệ, không lộ CCCD, đối soát tệp vừa tải là khớp,
   tệp khác là không khớp.
10. cdt.minh gửi yêu cầu cung cấp dữ liệu (DSAR).
11. tt.khanh lập phiếu kiểm tra cho công trình vừa cấp phép; kt.an (kiểm toán) không vào được app.

Chạy: `pip install playwright pytest && python -m playwright install chromium`, rồi
`pytest tests/e2e-ui -q` trên stack đã `dx up` với DEMO_MODE=true. Ảnh chụp từng bước ghi vào
`E2E_OUT_DIR` (mặc định logs/e2e-ui/<thời điểm>/). Dữ liệu demo tạo ra được giữ lại để xem lại.
"""

import hashlib
import os
import re
import time
import uuid
from datetime import datetime
from pathlib import Path

import httpx
import pytest

from tests.integration._auth import DEMO_ACCOUNTS_FILE, GATEWAY_URL, ROOT, get_token
from tests.integration._ho_so import REQUIRED_DOC_LOAI, complete_task, sub_of, wait_task

try:
    from playwright import sync_api
except ImportError:  # test tệp mẫu vẫn chạy khi chưa cài Playwright
    sync_api = None

FIXTURE = Path(__file__).parent / "fixtures" / "ban_ve_thiet_ke_mau.pdf"
FIXTURE_SHA256 = "f247e7c67576f17cb9afaf5a722be97c1cc77307da68dc5d0a91199c9922dab2"
BASE_URL = os.getenv("E2E_BASE_URL", GATEWAY_URL).rstrip("/")
HEADLESS = os.getenv("E2E_HEADED", "") != "1"


def expect(*args, **kwargs):
    return sync_api.expect(*args, **kwargs)


def _mat_khau() -> dict[str, str]:
    if not DEMO_ACCOUNTS_FILE.exists():
        pytest.fail("Thiếu secrets/demo-accounts.txt: chạy `dx up` với DEMO_MODE=true để seed sinh tài khoản demo")
    ds = {}
    for line in DEMO_ACCOUNTS_FILE.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split(":")
        if len(parts) >= 2 and parts[0] and not parts[0].startswith("#"):
            ds[parts[0]] = parts[1]
    return ds


def _thu_muc_ra() -> Path:
    goc = os.getenv("E2E_OUT_DIR") or str(ROOT / "logs" / "e2e-ui" / datetime.now().strftime("%Y%m%d-%H%M%S"))
    p = Path(goc)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _rpc(token: str, ten: str, body: dict) -> httpx.Response:
    return httpx.post(f"{BASE_URL}/api/v1/rest/rpc/{ten}", headers={"Authorization": f"Bearer {token}"},
                      json=body, timeout=15.0)


class Phien:
    """Một người dùng đăng nhập trong ngữ cảnh trình duyệt riêng."""

    def __init__(self, browser, username: str, mat_khau: str, ra: Path):
        self.username = username
        self.ra = ra
        self.ctx = browser.new_context(viewport={"width": 1280, "height": 860}, accept_downloads=True, locale="vi-VN")
        self.page = self.ctx.new_page()
        p = self.page
        p.goto(f"{BASE_URL}/", wait_until="domcontentloaded")
        p.get_by_role("button", name="Đăng nhập", exact=True).click()
        p.locator("#username").fill(username)
        p.locator("#password").fill(mat_khau)
        p.locator("#kc-login").click()
        p.wait_for_url(re.compile(re.escape(BASE_URL) + r"/(\?.*)?$"), timeout=20000)

    def da_vao_app(self) -> None:
        expect(self.page.get_by_role("button", name="Đăng xuất")).to_be_visible(timeout=20000)

    def tab(self, ten: str) -> None:
        self.page.locator("nav[aria-label='Điều hướng']").get_by_role("button", name=ten, exact=True).click()

    def muc(self, tieu_de: str):
        """Khối <section> có tiêu đề `tieu_de` (mỗi màn hình là một section)."""
        return self.page.locator("section").filter(has=self.page.get_by_role("heading", name=tieu_de, exact=True))

    def chup(self, ten: str) -> None:
        self.page.screenshot(path=str(self.ra / f"{ten}.png"), full_page=True)

    def dong(self) -> None:
        self.ctx.close()


def _tep_giay_to(ra: Path, tag: str) -> dict[str, Path]:
    """Sáu biến thể của tệp mẫu (thêm dòng chú thích sau %%EOF) để không trùng SHA-256 (lớp L6)."""
    goc = FIXTURE.read_bytes()
    thu_muc = ra / "giay-to"
    thu_muc.mkdir(exist_ok=True)
    ds = {}
    for loai in REQUIRED_DOC_LOAI:
        p = thu_muc / f"{loai}-{tag}.pdf"
        p.write_bytes(goc + f"\n% {loai}-{tag}\n".encode())
        ds[loai] = p
    return ds


def _cho(dieu_kien, timeout: float = 30.0, buoc: float = 1.0):
    het = time.time() + timeout
    while time.time() < het:
        kq = dieu_kien()
        if kq:
            return kq
        time.sleep(buoc)
    return None


def _quy_trinh_cua(token: str, ma: str) -> str | None:
    """Process id của hồ sơ `ma`, lấy từ việc trong danh sách của người dùng (biến quy trình ma_ho_so).

    Flowable REST không trả businessKey trong danh sách việc nên đối chiếu theo biến.
    """
    r = httpx.get(f"{BASE_URL}/api/v1/flow/tasks", headers={"Authorization": f"Bearer {token}"}, timeout=10.0)
    if r.status_code != 200:
        return None
    for t in r.json().get("tasks", []):
        bien = {v.get("name"): v.get("value") for v in t.get("variables") or []}
        if bien.get("ma_ho_so") == ma:
            return t["processInstanceId"]
    return None


def _so_chua_doc(phien: Phien) -> int:
    nut = phien.page.get_by_role("button", name=re.compile(r"^Thông báo, \d+ chưa đọc$"))
    return int(re.search(r"\d+", nut.get_attribute("aria-label") or "0").group())


def test_tep_mau_co_giay_phep_va_ma_bam():
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == FIXTURE_SHA256, "Tệp mẫu đã bị thay đổi"
    assert FIXTURE.read_bytes().startswith(b"%PDF-")
    giay_phep = FIXTURE.with_name(FIXTURE.name + ".license").read_text(encoding="utf-8")
    nhan = "SPDX-" + "License-Identifier:"  # tách chuỗi để công cụ REUSE không đọc nhầm dòng này
    assert f"{nhan} CC0-1.0" in giay_phep.splitlines()


def test_hanh_trinh_demo_tren_giao_dien():
    if sync_api is None:
        pytest.skip("Chưa cài Playwright: pip install playwright && python -m playwright install chromium")
    mk = _mat_khau()
    ra = _thu_muc_ra()
    tag = uuid.uuid4().hex[:6]
    ho_ten = f"Trần Văn Minh {tag}"
    dia_chi = f"Số {tag} Phố Hoa Phượng, Phường A"
    tok = {u: get_token(u) for u in ("cdt.minh", "mc.thu", "ld.hoa", "td.binh", "td.cuong")}

    with sync_api.sync_playwright() as pw:
        browser = pw.chromium.launch(headless=HEADLESS)
        try:
            # 1. Một cửa mở Bàn làm việc trước để nhận thông báo thời gian thực
            mc = Phien(browser, "mc.thu", mk["mc.thu"], ra)
            mc.da_vao_app()
            expect(mc.page.get_by_text("Trực tuyến", exact=True)).to_be_visible(timeout=20000)
            so_truoc = _so_chua_doc(mc)

            # 2. Chủ đầu tư nộp hồ sơ trên giao diện
            cdt = Phien(browser, "cdt.minh", mk["cdt.minh"], ra)
            cdt.da_vao_app()
            p = cdt.page
            p.locator("#btn-nop-ho-so-modal").click()
            expect(p.locator("#form-nop-ho-so")).to_be_visible()
            p.locator("#input-ho-ten").fill(ho_ten)
            p.locator("#input-cccd").fill("001200112233")
            p.locator("#input-dien-thoai").fill("0912345678")
            p.locator("#input-dia-chi").fill(dia_chi)
            p.locator("#input-thua-dat").fill(f"Thửa {tag}")
            p.locator("#input-so-tang").fill("3")
            p.locator("#input-dien-tich").fill("150")
            expect(p.locator("#document-checklist")).to_be_visible(timeout=15000)
            for loai, tep in _tep_giay_to(ra, tag).items():
                p.locator(f"#file-{loai}").set_input_files(str(tep))
                expect(p.locator(f"#doc-{loai}")).to_contain_text("Đã chọn")
            p.locator("#ngay-cap-giay_to_dat").fill("2020-01-01")
            p.locator("#ngay-het-han-giay_to_dat").fill("2035-01-01")
            cdt.chup("01-cdt-minh-form")
            p.locator("#btn-submit-nop-ho-so").click()
            try:
                expect(p.locator("#form-nop-ho-so")).to_be_hidden(timeout=60000)
            except AssertionError:
                cdt.chup("02-loi-nop")
                loi = p.locator("#submit-errors")
                raise AssertionError("Nộp hồ sơ không thành công: " + (loi.inner_text() if loi.count() else "không rõ lỗi"))
            p.locator("#txt-tim-ho-so").fill(tag)  # lọc theo tên để không phụ thuộc phân trang
            hang =p.locator("#table-ho-so tbody tr").filter(has_text=ho_ten)
            expect(hang).to_be_visible(timeout=15000)
            ma = hang.locator("td").first.inner_text().strip()
            assert re.fullmatch(r"CP-\d{4}-\d+", ma), f"Mã hồ sơ không đúng định dạng: {ma}"
            cdt.chup("02-cdt-minh-da-nop")

            ho_so = _cho(lambda: next(iter(httpx.get(
                f"{BASE_URL}/api/v1/rest/v_ho_so?ma_ho_so=eq.{ma}&select=id",
                headers={"Authorization": f"Bearer {tok['cdt.minh']}"}, timeout=10.0,
            ).json()), None))
            assert ho_so and ho_so["id"], f"Không đọc được hồ sơ {ma}"
            proc_id = _cho(lambda: _quy_trinh_cua(tok["mc.thu"], ma))
            assert proc_id, "Giao diện nộp xong phải khởi động quy trình cap-phep (việc một cửa theo mã hồ sơ)"

            # 3. Chuông một cửa tăng; việc của hồ sơ hiện trên Bàn làm việc, mở xem được
            assert _cho(lambda: _so_chua_doc(mc) > so_truoc, timeout=20.0), "Chuông của mc.thu không tăng trong 20 giây"
            ban = mc.muc("Bàn làm việc")
            ban.get_by_role("button", name="Làm mới").click()
            viec = ban.locator("aside button").filter(has_text=ma).first
            expect(viec).to_contain_text("Kiểm tra Hồ sơ Hợp lệ", timeout=15000)
            viec.click()
            ban.get_by_role("button", name="Mở hồ sơ đầy đủ").click()
            expect(mc.page.locator("#detail-ma-ho-so")).to_have_text(ma, timeout=15000)
            expect(mc.page.locator("#detail-chu-dau-tu")).to_have_text(ho_ten)
            expect(mc.page.locator("#block-dossier-files")).to_contain_text(f"{len(REQUIRED_DOC_LOAI)} tệp")
            mc.chup("03-mc-thu-xem-ho-so")
            mc.page.locator("#btn-close-modal-detail").click()
            mc.dong()

            # 4. Tiếp nhận và phân công qua API (giao diện chưa có biểu mẫu cho hai bước này)
            t = wait_task(tok["mc.thu"], proc_id, "taskKiemTraHopLe")
            assert complete_task(tok["mc.thu"], t["id"], {"hoSoHopLe": True}).status_code == 200
            t = wait_task(tok["ld.hoa"], proc_id, "taskPhanCong")
            r = complete_task(tok["ld.hoa"], t["id"], {"nguoiThamDinh": sub_of(tok["td.binh"]),
                                                       "lanhDaoPhanCong": sub_of(tok["ld.hoa"])})
            assert r.status_code == 200, r.text

            # 5. Thẩm định viên được giao hoàn thành việc trên Bàn làm việc
            td = Phien(browser, "td.binh", mk["td.binh"], ra)
            td.da_vao_app()
            ban = td.muc("Bàn làm việc")
            ban.get_by_role("button", name="Làm mới").click()
            viec = ban.locator("aside button").filter(has_text=ma).first
            expect(viec).to_be_visible(timeout=15000)
            td.chup("05-td-binh-viec-duoc-giao")
            viec.click()
            ban.get_by_role("button", name="Hoàn thành việc").click()
            expect(td.page.get_by_text("Đã hoàn thành việc")).to_be_visible(timeout=15000)
            expect(viec).to_have_count(0, timeout=15000)
            td.dong()

            # 6. Truy cập khẩn: td.cuong bị chặn, xin mở; ld.hoa duyệt trên giao diện
            assert _rpc(tok["td.cuong"], "mo_ho_so", {"p_id": ho_so["id"]}).status_code == 403
            ly_do = f"Hỗ trợ thẩm định kết cấu ngoài giờ {tag}"
            r = _rpc(tok["td.cuong"], "xin_truy_cap_khan", {"p_ho_so_id": ho_so["id"], "p_ly_do": ly_do})
            assert r.status_code == 200, r.text
            ld = Phien(browser, "ld.hoa", mk["ld.hoa"], ra)
            ld.da_vao_app()
            ld.tab("Truy cập khẩn")
            khan = ld.muc("Truy cập khẩn chờ duyệt")
            khan.get_by_role("button", name="Làm mới").click()
            yeu_cau = khan.locator("li").filter(has_text=ly_do)
            expect(yeu_cau).to_contain_text(ma, timeout=15000)
            expect(yeu_cau).to_contain_text("Vũ Quốc Cường")
            ld.chup("06-ld-hoa-truy-cap-khan")
            yeu_cau.get_by_role("button", name="Duyệt").click()
            expect(ld.page.get_by_text("Đã duyệt truy cập khẩn.")).to_be_visible(timeout=15000)
            expect(yeu_cau).to_have_count(0, timeout=15000)
            ld.dong()
            assert _rpc(tok["td.cuong"], "mo_ho_so", {"p_id": ho_so["id"]}).status_code == 200

            # 7. Phê duyệt qua API; hook ký số cấp giấy phép
            t = wait_task(tok["ld.hoa"], proc_id, "taskDuyetCapPhep")
            r = complete_task(tok["ld.hoa"], t["id"], {"dongYCapPhep": True, "pheDuyet": True,
                                                       "yKienPheDuyet": "Đồng ý cấp phép"})
            assert r.status_code == 200, r.text

            # 8. Chủ đầu tư xem giấy phép, chữ ký số, nhật ký; tải PDF giấy phép
            hs = cdt.muc("Hồ sơ cấp phép")

            def da_cap() -> bool:
                hs.get_by_role("button", name="Làm mới").click()
                try:
                    expect(hang).to_contain_text("Đã cấp phép", timeout=3000)
                    return True
                except AssertionError:
                    return False

            assert _cho(da_cap, timeout=45.0, buoc=0.5), f"Hồ sơ {ma} không sang Đã cấp phép"
            p.locator(f"#btn-detail-{ma}").click()
            expect(p.locator("#block-giay-phep-signature")).to_be_visible(timeout=15000)
            expect(p.locator("#val-so-giay-phep")).to_have_text(re.compile(r"^GPXD-phuong-a-\d{4}-\d{6}$"), timeout=15000)
            expect(p.locator("#val-nguoi-ky")).not_to_have_text("Không xác định")
            expect(p.locator("#val-thuat-toan")).to_have_text(re.compile(r"PAdES|Ed25519"))
            expect(p.locator("#list-dossier-audit")).to_contain_text("truy cập khẩn", ignore_case=True)
            ma_cong_khai = p.locator("#link-public-code").inner_text().strip()
            assert ma_cong_khai, "Thiếu mã tra cứu công khai"
            cdt.chup("08-cdt-minh-giay-phep")
            with p.expect_download(timeout=30000) as tai:
                p.locator("#btn-download-permit").click()
            pdf = ra / "giay-phep.pdf"
            tai.value.save_as(str(pdf))
            assert pdf.read_bytes().startswith(b"%PDF")
            p.locator("#btn-close-modal-detail").click()

            # 9. Tra cứu và đối soát công khai, không đăng nhập
            pub_ctx = browser.new_context(locale="vi-VN")
            pub = pub_ctx.new_page()
            pub.goto(f"{BASE_URL}/kiem-tra/{ma_cong_khai}")
            expect(pub.locator("#val-public-code")).to_have_text(ma_cong_khai)
            expect(pub.locator("body")).to_contain_text("Hợp lệ")
            assert "CCCD" not in pub.content().upper(), "Trang công khai không được lộ CCCD"
            assert ho_ten not in pub.content(), "Trang công khai không được lộ tên chủ đầu tư"
            pub.locator("#verify-file").set_input_files(str(pdf))
            pub.locator("#btn-verify-file").click()
            expect(pub.locator("#verify-result")).to_contain_text("Tệp khớp với văn bản đã ký.", timeout=15000)
            pub.screenshot(path=str(ra / "09-cong-khai-doi-soat.png"), full_page=True)
            pub.goto(f"{BASE_URL}/kiem-tra/{ma_cong_khai}")
            pub.locator("#verify-file").set_input_files(str(FIXTURE))
            pub.locator("#btn-verify-file").click()
            expect(pub.locator("#verify-result")).to_contain_text("Tệp không khớp với văn bản đã ký.", timeout=15000)
            pub_ctx.close()

            # 10. Chủ đầu tư gửi yêu cầu cung cấp dữ liệu cá nhân
            cdt.tab("Dữ liệu của tôi")
            p.locator("#txt-dsar-note").fill(f"Cung cấp dữ liệu cá nhân phường đang lưu ({tag})")
            p.locator("#btn-dsar-access").click()
            expect(p.locator("#table-dsar")).to_contain_text("Cung cấp dữ liệu", timeout=15000)
            cdt.chup("10-cdt-minh-dsar")
            cdt.dong()

            # 11. Trật tự xây dựng lập phiếu cho công trình mới; kiểm toán không vào được app nghiệp vụ
            tt = Phien(browser, "tt.khanh", mk["tt.khanh"], ra)
            tt.da_vao_app()
            tt.tab("Công trình")
            ct = tt.muc("Công trình").locator("li").filter(has_text=dia_chi).first
            expect(ct).to_be_visible(timeout=15000)
            ct.get_by_role("button", name="Lập phiếu").click()
            expect(tt.page.get_by_text("Đã lập phiếu kiểm tra")).to_be_visible(timeout=15000)
            ct = tt.muc("Công trình").locator("li").filter(has_text=dia_chi).first
            ct.get_by_role("button", name="Xem phiếu").click()
            expect(ct.locator("ul li").first).to_be_visible()
            expect(ct.locator("ul")).not_to_contain_text("Chưa có phiếu kiểm tra.")
            tt.chup("11-tt-khanh-phieu")
            tt.dong()

            kt = Phien(browser, "kt.an", mk["kt.an"], ra)
            expect(kt.page.get_by_role("heading", name="Không có quyền")).to_be_visible(timeout=20000)
            kt.dong()
        finally:
            browser.close()
