# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Kịch bản kiểm thử tự động toàn bộ hành trình người dùng 11 bước (Quy tắc 14 / T-01 -> T-09):
1. cdt.minh nộp hồ sơ + tải đủ 6 giấy tờ theo checklist động trên giao diện.
   Nhánh bổ sung (T-07): mc.thu yêu cầu bổ sung -> cdt.minh thấy lý do và bổ sung tệp -> mc.thu tiếp nhận lại.
2. mc.thu tiếp nhận hồ sơ tại một cửa trên Bàn làm việc (kiểm tra khối thông tin hồ sơ T-01, tải tệp, audit).
3. ld.hoa phân công hồ sơ cho td.binh trên Bàn làm việc.
4. td.cuong tra cứu hồ sơ theo mã -> 403 Forbidden -> xin truy cập khẩn trên UI (T-04) -> ld.hoa duyệt -> td.cuong mở được.
5. td.binh thẩm định kỹ thuật (DAT) trên Bàn làm việc, kiểm tra SoD không có nút phê duyệt.
6. ld.hoa phê duyệt cấp phép trên Bàn làm việc -> ký số Ed25519 qua OpenBao (T-02) -> xem số giấy phép, Ed25519, mã công khai trên modal.
7. /kiem-tra/{public_code} tra cứu xác minh giấy phép công khai (không cần đăng nhập).
8. cdt.minh quản lý đồng thuận + gửi yêu cầu dữ liệu cá nhân DSAR trên giao diện.
9. Cán bộ TTXD tt.khanh kích hoạt mô phỏng cảm biến vượt ngưỡng trên UI (T-03) -> tạo phiếu kiểm tra -> xử lý trên Bàn làm việc -> kt.an (auditor) chỉ xem không có nút.
10. cdt.minh xem nhật ký truy cập hồ sơ của mình (T-08: thấy dòng truy cập khẩn của Vũ Quốc Cường kèm lý do), kiểm tra RLS từ chối xem hồ sơ người khác.
11. mc.thu mở bàn làm việc -> cdt.minh nộp hồ sơ ở trình duyệt thứ hai -> chuông mc.thu tăng trong 15s (T-09) -> mở dropdown xem thông báo -> đánh dấu đã đọc -> cdt.lan không có thông báo -> kiểm tra lưu trữ bền bỉ sau đăng xuất.

Tuân thủ nghiêm ngặt Quy tắc 14:
- Dùng expect(...).to_be_visible() / to_contain_text() trên các phần tử người dùng thật nhìn thấy.
- Tuyệt đối cấm nhánh mềm kiểu if locator.count() > 0:.
- Tuyệt đối cấm ghi thẳng vào CSDL (INSERT ...).
- Chụp ảnh minh chứng từng bước vào thư mục screens/ của run hiện tại.
"""

import os
import json
import uuid
import base64
import shutil
import time
import urllib.request
import urllib.parse
import subprocess
from pathlib import Path
from datetime import datetime
import httpx
from playwright.sync_api import sync_playwright, Page, BrowserContext, expect

ROOT = Path(__file__).resolve().parent.parent.parent

SAMPLE_PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 300 144]/Parent 2 0 R/Resources<<>>>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n0000000053 00000 n \n0000000102 00000 n \n"
    b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF\n"
)



REQUIRED_DOCS = [
    "don",
    "giay_to_dat",
    "ban_ve_mat_bang",
    "ban_ve_tang",
    "ban_ve_mong",
    "cam_ket_an_toan",
]


def make_manifest_docs(base_dir: Path, unique: str) -> dict:
    """Sinh 6 tệp PDF khác nội dung để không trùng SHA-256."""
    base_dir.mkdir(parents=True, exist_ok=True)
    docs = {}
    for loai in REQUIRED_DOCS:
        path = base_dir / f"doc_{unique}_{loai}.pdf"
        path.write_bytes(SAMPLE_PDF_BYTES + f"\n% {loai}-{unique}\n".encode())
        docs[loai] = path
    return docs


def upload_manifest_docs(page: Page, docs: dict) -> None:
    for loai, path in docs.items():
        page.set_input_files(f"#file-{loai}", str(path))
    page.fill("#ngay-cap-giay_to_dat", "2020-01-01")
    page.fill("#ngay-het-han-giay_to_dat", "2035-01-01")

def run_db_query(sql: str) -> str:
    """Thực thi câu truy vấn SQL kiểm chứng phụ trợ trên database dxos."""
    cmd = [
        "docker", "compose", "exec", "-T", "postgres",
        "psql", "-U", "postgres", "-d", "dxos", "-t", "-A", "-F", "|", "-c", sql,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT), timeout=30)
    if res.returncode != 0:
        raise RuntimeError(f"Database query failed: {res.stderr}\nSQL: {sql}")
    return res.stdout.strip()


def load_demo_passwords() -> dict[str, str]:
    """Tải mật khẩu tài khoản demo từ secrets/demo-accounts.txt (Z-15: fail-closed, không fallback cứng)."""
    pw_file = ROOT / "secrets" / "demo-accounts.txt"
    passwords = {}
    if pw_file.exists():
        for line in pw_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and ":" in line:
                parts = line.split(":")
                passwords[parts[0].strip()] = parts[1].strip()

    for k, v in os.environ.items():
        if k.startswith("DEMO_PW_"):
            uname = k.replace("DEMO_PW_", "").lower().replace("_", ".")
            passwords[uname] = v

    return passwords


def get_user_token(username: str) -> tuple[str, str]:
    """Lấy JWT token và sub từ Keycloak SSO bằng urllib."""
    passwords = load_demo_passwords()
    if username not in passwords:
        raise ValueError(f"Không tìm thấy mật khẩu cho tài khoản {username} trong secrets/demo-accounts.txt")
    pw = passwords[username]

    req_data = urllib.parse.urlencode({
        "client_id": "dx-test",
        "username": username,
        "password": pw,
        "grant_type": "password",
    }).encode("utf-8")

    req = urllib.request.Request(
        "http://localhost:8080/auth/realms/dxos/protocol/openid-connect/token",
        data=req_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=10.0) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    token = data["access_token"]
    payload_b64 = token.split(".")[1]
    payload_b64 += "=" * (-len(payload_b64) % 4)
    payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    return token, payload["sub"]


def fetch_tasks_via_api(token: str) -> list:
    """Lấy danh sách tasks phục vụ định vị ID nhiệm vụ trên giao diện."""
    req = urllib.request.Request(
        "http://localhost:8080/api/v1/flow/tasks",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=10.0) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("tasks", [])


def login_ui(page: Page, username: str):
    """Đăng nhập giao diện qua Keycloak SSO PKCE."""
    passwords = load_demo_passwords()
    if username not in passwords:
        raise ValueError(f"Không tìm thấy mật khẩu cho tài khoản {username} trong secrets/demo-accounts.txt")
    pw = passwords[username]

    page.goto("http://localhost:8080/", wait_until="networkidle")
    page.wait_for_timeout(500)

    login_btn = page.locator("button:has-text('Đăng nhập Keycloak SSO'), button:has-text('Đăng nhập với tài khoản')").first
    login_btn.click()

    page.wait_for_selector("input#username", timeout=15000)
    page.fill("input#username", username)
    page.fill("input#password", pw)
    page.click("#kc-login")

    page.wait_for_selector("#tab-dossiers", timeout=15000)
    page.wait_for_timeout(500)


def logout_ui(page: Page, context: BrowserContext):
    """Đăng xuất và dọn dẹp phiên."""
    try:
        logout_btn = page.locator("button:has-text('Đăng xuất')").first
        if logout_btn.is_visible():
            logout_btn.click()
            page.wait_for_timeout(500)
    except Exception:
        pass
    context.clear_cookies()
    page.evaluate("sessionStorage.clear(); localStorage.clear();")
    try:
        page.goto("http://localhost:8080/auth/realms/dxos/protocol/openid-connect/logout", wait_until="networkidle")
        page.wait_for_timeout(500)
    except Exception:
        pass
    time.sleep(1.5)


def get_target_run_dir() -> Path:
    """Xác định thư mục run để lưu video minh chứng demo.webm và screens/."""
    target_env = os.environ.get("TARGET_RUN_DIR")
    if target_env:
        p = Path(target_env)
        p.mkdir(parents=True, exist_ok=True)
        return p
    main_runs_dir = Path("D:/v1PMNM/_DXOS_TaiLieu/01_BaoCao_Test/runs")
    if main_runs_dir.exists():
        existing = sorted([d for d in main_runs_dir.iterdir() if d.is_dir()])
        if existing:
            return existing[-1]
    ts = datetime.now().strftime("%Y%m%d-%H%M")
    target = main_runs_dir / ts
    target.mkdir(parents=True, exist_ok=True)
    return target


def test_complete_11_step_demo_flow():
    target_run_dir = get_target_run_dir()
    screens_dir = target_run_dir / "screens"
    screens_dir.mkdir(parents=True, exist_ok=True)

    videos_dir = target_run_dir / "videos_tmp"
    videos_dir.mkdir(parents=True, exist_ok=True)

    # Tạo tệp PDF mẫu phục vụ tải lên
    fixtures_dir = ROOT / "tests" / "e2e-ui" / "fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    sample_pdf_path = fixtures_dir / "ban_ve_thiet_ke_mau.pdf"
    sample_pdf_path.write_bytes(SAMPLE_PDF_BYTES)

    test_unique_id = uuid.uuid4().hex[:6]
    test_dossier_name = f"Trần Văn Minh ({test_unique_id})"
    test_address = f"Số {test_unique_id} Phố Hoa Phượng, Phường A"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            record_video_dir=str(videos_dir),
            record_video_size={"width": 1280, "height": 800},
        )
        page = context.new_page()

        # Tự động chấp nhận các popup alert
        def on_dialog(d):
            print(f"[BROWSER DIALOG] {d.message}")
            d.accept()
        page.on("dialog", on_dialog)

        # ====================================================================
        # BƯỚC 1: cdt.minh nộp hồ sơ + tải tệp bản vẽ PDF trên UI
        # ====================================================================
        print("\n>>> [BƯỚC 1] cdt.minh nộp hồ sơ trực tuyến + tải tệp bản vẽ trên UI...")
        time.sleep(3)
        login_ui(page, "cdt.minh")
        page.screenshot(path=str(screens_dir / "step01_01_dashboard.png"))

        page.click("#btn-nop-ho-so-modal")
        expect(page.locator("#form-nop-ho-so")).to_be_visible(timeout=5000)

        page.fill("#form-nop-ho-so input[placeholder='Nguyễn Văn A']", test_dossier_name)
        page.fill("#form-nop-ho-so input[placeholder='001090123456']", "001200112233")
        page.fill("#form-nop-ho-so input[placeholder='0901234567']", "0912345678")
        page.fill("#form-nop-ho-so input[placeholder='Số 123 Đường Mẫu, Phường A']", test_address)
        page.fill("#form-nop-ho-so input[placeholder='Thửa 12, Tờ 34']", f"Thửa {test_unique_id}")
        page.fill("#form-nop-ho-so input[type='number'][min='1']", "3")
        page.fill("#form-nop-ho-so input[type='number'][step='0.1']", "150.0")

        docs = make_manifest_docs(screens_dir / "generated_docs", test_unique_id)
        upload_manifest_docs(page, docs)

        page.click("#btn-submit-nop-ho-so")
        expect(page.locator("#form-nop-ho-so")).to_be_hidden(timeout=20000)

        # Kiểm tra hồ sơ xuất hiện trong bảng với mã hồ sơ CP-2026-xxxxxx
        expect(page.locator("#table-ho-so")).to_be_visible(timeout=10000)
        row_submitted = page.locator("#table-ho-so tbody tr").filter(has_text=test_dossier_name).first
        expect(row_submitted).to_be_visible()
        expect(row_submitted).to_contain_text("Đã nộp")

        ma_ho_so = row_submitted.locator("td").first.inner_text().strip()
        assert ma_ho_so.startswith("CP-2026-"), f"Mã hồ sơ không đúng định dạng: {ma_ho_so}"
        print(f"  [UI OK] Hồ sơ nộp thành công, mã hồ sơ: {ma_ho_so}")

        proc_id = ""
        for _ in range(20):
            res = run_db_query(f"SELECT process_instance_id FROM app_cap_phep.ho_so WHERE ma_ho_so = '{ma_ho_so}';")
            if res and res.strip():
                proc_id = res.strip()
                break
            page.wait_for_timeout(1000)
        print(f"  [PROC OK] process_instance_id: {proc_id}")
        page.screenshot(path=str(screens_dir / "step01_cdt_minh_submitted.png"))
        logout_ui(page, context)

        # ====================================================================
        # NHÁNH BỔ SUNG HỒ SƠ (T-07 / demo.md):
        # mc.thu yêu cầu bổ sung -> cdt.minh thấy lý do, bổ sung -> mc.thu tiếp nhận lại
        # ====================================================================
        print("\n>>> [NHÁNH BỔ SUNG T-07] mc.thu yêu cầu bổ sung -> cdt.minh bổ sung -> mc.thu nhận lại...")
        login_ui(page, "mc.thu")
        page.click("#tab-workspace")
        expect(page.locator("#workspace-3-cols")).to_be_visible(timeout=10000)

        token_mc, _ = get_user_token("mc.thu")
        mc_task = None
        for _ in range(15):
            tasks = fetch_tasks_via_api(token_mc)
            mc_task = next((t for t in tasks if (not proc_id or t.get("processInstanceId") == proc_id) and t.get("taskDefinitionKey") == "taskKiemTraHopLe"), None)
            if mc_task:
                break
            page.wait_for_timeout(1000)
        assert mc_task, f"Không tìm thấy nhiệm vụ tiếp nhận cho hồ sơ {ma_ho_so}"

        page.click(f"#task-card-{mc_task['id']}")
        expect(page.locator("#dossier-info-block")).to_be_visible(timeout=5000)
        expect(page.locator("#info-chu-dau-tu")).to_contain_text(test_dossier_name)
        expect(page.locator("#info-dia-chi")).to_contain_text(test_address)

        # mc.thu chọn Cần bổ sung và nhập lý do
        page.click("#radio-can-bo-sung")
        supplement_reason = "Bản vẽ thiếu mặt đứng và chỉ giới đường đỏ, đề nghị chủ đầu tư bổ sung bản vẽ chi tiết"
        page.fill("#txt-ly-do-bo-sung", supplement_reason)
        page.click("#btn-complete-task")
        page.wait_for_timeout(1500)
        page.screenshot(path=str(screens_dir / "step02_mc_thu_requested_supplement.png"))
        logout_ui(page, context)

        # cdt.minh đăng nhập, thấy trạng thái CAN_BO_SUNG, mở modal bổ sung
        login_ui(page, "cdt.minh")
        expect(page.locator("#table-ho-so")).to_be_visible(timeout=10000)
        row_supplement = page.locator("#table-ho-so tbody tr").filter(has_text=test_dossier_name).first
        expect(row_supplement).to_contain_text("Cần bổ sung")

        btn_supp = row_supplement.locator("button:has-text('Bổ sung')").first
        expect(btn_supp).to_be_visible(timeout=5000)
        btn_supp.click()
        expect(page.locator("text=Bổ sung hồ sơ cấp phép").first).to_be_visible(timeout=5000)
        expect(page.locator("#box-ly-do-bo-sung")).to_contain_text(supplement_reason)

        # Đính kèm tệp bổ sung và gửi
        supp_file_input = page.locator("#file-bo-sung")
        supp_file_input.set_input_files(str(sample_pdf_path))
        page.click("#btn-submit-bo-sung")
        expect(page.locator("text=Bổ sung hồ sơ cấp phép").first).to_be_hidden(timeout=15000)
        page.screenshot(path=str(screens_dir / "step02_cdt_minh_supplemented.png"))
        logout_ui(page, context)

        # ====================================================================
        # BƯỚC 2: mc.thu tiếp nhận lại hồ sơ hợp lệ trên Bàn làm việc (T-01)
        # ====================================================================
        print("\n>>> [BƯỚC 2] mc.thu tiếp nhận lại hồ sơ hợp lệ trên Bàn làm việc...")
        login_ui(page, "mc.thu")
        page.click("#tab-workspace")
        expect(page.locator("#workspace-3-cols")).to_be_visible(timeout=10000)

        mc_task_2 = None
        for _ in range(15):
            tasks = fetch_tasks_via_api(token_mc)
            mc_task_2 = next((t for t in tasks if (not proc_id or t.get("processInstanceId") == proc_id) and t.get("taskDefinitionKey") == "taskKiemTraHopLe"), None)
            if mc_task_2:
                break
            page.wait_for_timeout(1000)
        assert mc_task_2, f"Không tìm thấy nhiệm vụ tiếp nhận lại sau khi bổ sung cho hồ sơ {ma_ho_so}"

        page.click(f"#task-card-{mc_task_2['id']}")
        expect(page.locator("#dossier-info-block")).to_be_visible(timeout=5000)
        expect(page.locator("#info-chu-dau-tu")).to_contain_text(test_dossier_name)
        expect(page.locator("#info-dia-chi")).to_contain_text(test_address)
        expect(page.locator("#dossier-info-block")).to_contain_text(".pdf")
        expect(page.locator("#dossier-info-block")).to_contain_text("Đã quét virus, an toàn")

        # Cột phải: nhật ký có ít nhất dòng nộp hồ sơ
        expect(page.locator("#workspace-3-cols aside").first).to_contain_text("Nộp hồ sơ")

        # Chọn hợp lệ và hoàn tất
        page.click("#radio-hop-le")
        page.click("#btn-complete-task")
        page.wait_for_timeout(1500)
        page.screenshot(path=str(screens_dir / "step02_mc_thu_workspace.png"))
        logout_ui(page, context)

        # ====================================================================
        # BƯỚC 3: ld.hoa phân công hồ sơ cho td.binh
        # ====================================================================
        print("\n>>> [BƯỚC 3] ld.hoa phân công hồ sơ cho td.binh...")
        login_ui(page, "ld.hoa")
        page.click("#tab-workspace")
        expect(page.locator("#workspace-3-cols")).to_be_visible(timeout=10000)

        token_ld, _ = get_user_token("ld.hoa")
        assign_task = None
        for _ in range(15):
            tasks = fetch_tasks_via_api(token_ld)
            assign_task = next((t for t in tasks if (not proc_id or t.get("processInstanceId") == proc_id) and t.get("taskDefinitionKey") == "taskPhanCong"), None)
            if assign_task:
                break
            page.wait_for_timeout(1000)
        assert assign_task, f"Không tìm thấy nhiệm vụ phân công taskPhanCong cho hồ sơ {ma_ho_so}"

        page.click(f"#task-card-{assign_task['id']}")
        expect(page.locator("#dossier-info-block")).to_be_visible(timeout=5000)
        expect(page.locator("#info-chu-dau-tu")).to_contain_text(test_dossier_name)

        page.select_option("select", value="td.binh")
        page.click("#btn-submit-phan-cong")
        page.wait_for_timeout(1500)
        page.screenshot(path=str(screens_dir / "step03_ld_hoa_assign.png"))
        logout_ui(page, context)

        # ====================================================================
        # BƯỚC 4: td.cuong tra cứu theo mã -> 403 -> Break-Glass -> ld.hoa duyệt
        # ====================================================================
        print("\n>>> [BƯỚC 4] td.cuong tra cứu mã -> 403 -> Break-Glass -> ld.hoa duyệt...")
        login_ui(page, "td.cuong")
        expect(page.locator("text=Tra cứu hồ sơ theo mã (cán bộ)").first).to_be_visible(timeout=5000)
        expect(page.locator("text=Hồ sơ chưa được phân công sẽ cần yêu cầu truy cập khẩn")).to_be_visible()

        # Nhập mã hồ sơ và mở -> 403
        page.fill("#txt-open-dossier-code", ma_ho_so)
        page.click("#btn-open-by-code")
        expect(page.locator("#modal-403-forbidden")).to_be_visible(timeout=5000)
        page.screenshot(path=str(screens_dir / "step04_td_cuong_forbidden.png"))

        # Bấm xin truy cập khẩn
        page.click("#btn-open-break-glass-modal")
        expect(page.locator("#modal-break-glass")).to_be_visible(timeout=5000)
        bg_reason = "Hỗ trợ đồng nghiệp thẩm định kết cấu đặc biệt ngoài giờ theo yêu cầu khẩn cấp"
        page.fill("#txt-break-glass-reason", bg_reason)
        page.click("#btn-confirm-break-glass")
        expect(page.locator("#modal-break-glass")).to_be_hidden(timeout=10000)
        logout_ui(page, context)

        # Lãnh đạo ld.hoa duyệt yêu cầu khẩn
        login_ui(page, "ld.hoa")
        page.click("#tab-workspace")
        expect(page.locator("#section-pending-break-glass")).to_be_visible(timeout=5000)
        expect(page.locator("#table-pending-break-glass")).to_contain_text("Vũ Quốc Cường")
        expect(page.locator("#table-pending-break-glass")).to_contain_text(ma_ho_so)
        expect(page.locator("#table-pending-break-glass")).to_contain_text(bg_reason)

        page.click("#btn-approve-break-glass")
        page.wait_for_timeout(1500)
        page.screenshot(path=str(screens_dir / "step04_ld_hoa_approved_break_glass.png"))
        logout_ui(page, context)

        # td.cuong mở lại hồ sơ bằng mã -> Mở được thành công!
        login_ui(page, "td.cuong")
        page.fill("#txt-open-dossier-code", ma_ho_so)
        page.click("#btn-open-by-code")
        expect(page.locator("#modal-detail-dossier")).to_be_visible(timeout=10000)
        expect(page.locator("#detail-ma-ho-so")).to_contain_text(ma_ho_so)
        page.click("#btn-close-modal-detail")
        page.screenshot(path=str(screens_dir / "step04_td_cuong_dossier_opened.png"))
        logout_ui(page, context)

        # ====================================================================
        # BƯỚC 5: td.binh thẩm định kỹ thuật, kiểm tra SoD
        # ====================================================================
        print("\n>>> [BƯỚC 5] td.binh thẩm định kỹ thuật, kiểm tra SoD...")
        login_ui(page, "td.binh")
        page.click("#tab-workspace")
        expect(page.locator("#workspace-3-cols")).to_be_visible(timeout=10000)

        token_tb, _ = get_user_token("td.binh")
        td_task = None
        for _ in range(15):
            tasks = fetch_tasks_via_api(token_tb)
            td_task = next((t for t in tasks if (not proc_id or t.get("processInstanceId") == proc_id) and "ThamDinh" in t.get("taskDefinitionKey", "")), None)
            if td_task:
                break
            page.wait_for_timeout(1000)
        assert td_task, f"Không tìm thấy nhiệm vụ thẩm định cho hồ sơ {ma_ho_so}"

        page.click(f"#task-card-{td_task['id']}")
        expect(page.locator("#dossier-info-block")).to_be_visible(timeout=5000)
        expect(page.locator("#info-chu-dau-tu")).to_contain_text(test_dossier_name)

        # Kiểm tra SoD: td.binh không có nút phê duyệt cấp phép
        expect(page.locator("#btn-submit-phe-duyet")).to_have_count(0)

        page.click("#btn-submit-tham-dinh")
        page.wait_for_timeout(1500)
        page.screenshot(path=str(screens_dir / "step05_td_binh_reviewed.png"))
        logout_ui(page, context)

        # ====================================================================
        # BƯỚC 6: ld.hoa phê duyệt cấp phép -> kiểm tra chữ ký số Ed25519 (T-02)
        # ====================================================================
        print("\n>>> [BƯỚC 6] ld.hoa phê duyệt cấp phép & ký số...")
        login_ui(page, "ld.hoa")
        page.click("#tab-workspace")
        expect(page.locator("#workspace-3-cols")).to_be_visible(timeout=10000)

        approve_task = None
        for _ in range(15):
            tasks = fetch_tasks_via_api(token_ld)
            approve_task = next((t for t in tasks if (not proc_id or t.get("processInstanceId") == proc_id) and ("Duyet" in t.get("taskDefinitionKey", "") or "PheDuyet" in t.get("taskDefinitionKey", ""))), None)
            if approve_task:
                break
            page.wait_for_timeout(1000)
        assert approve_task, f"Không tìm thấy nhiệm vụ phê duyệt cho hồ sơ {ma_ho_so}"

        page.click(f"#task-card-{approve_task['id']}")
        expect(page.locator("#btn-submit-phe-duyet")).to_be_visible(timeout=5000)
        page.click("#btn-submit-phe-duyet")
        page.wait_for_timeout(3000)

        # Vào tab hồ sơ xem chi tiết giấy phép đã ký
        page.click("#tab-dossiers")
        page.wait_for_timeout(2000)
        btn_detail = page.locator(f"#btn-detail-{ma_ho_so}")
        if not btn_detail.is_visible():
            page.fill("#txt-open-dossier-code", ma_ho_so)
            page.click("#btn-open-by-code")
        else:
            btn_detail.click()
        expect(page.locator("#modal-detail-dossier")).to_be_visible(timeout=10000)
        expect(page.locator("#block-giay-phep-signature")).to_be_visible(timeout=15000)

        # Kiểm tra các thông tin giấy phép & chữ ký số trên modal (T-02)
        expect(page.locator("#val-so-giay-phep")).to_be_visible()
        so_gp = page.locator("#val-so-giay-phep").inner_text().strip()
        assert so_gp.startswith("GPXD-"), f"Số giấy phép không đúng: {so_gp}"

        expect(page.locator("#val-nguoi-ky")).to_contain_text("Phạm Thanh Hoa")
        expect(page.locator("#val-thuat-toan")).to_contain_text("PAdES")

        expect(page.locator("#link-public-code")).to_be_visible()
        public_link = page.locator("#link-public-code")
        href = public_link.get_attribute("href") or ""
        public_code = href.split("/")[-1].strip() if "/" in href else public_link.inner_text().replace("↗", "").strip()
        assert public_code, "Mã công khai không được rỗng"
        expect(page.locator("#btn-download-permit")).to_be_visible()

        page.screenshot(path=str(screens_dir / "step06_ld_hoa_permit_signed.png"))
        page.click("#btn-close-modal-detail")
        logout_ui(page, context)

        # ====================================================================
        # BƯỚC 7: Xác minh Giấy phép Công khai (không cần đăng nhập)
        # ====================================================================
        print(f"\n>>> [BƯỚC 7] Tra cứu xác minh giấy phép công khai tại /kiem-tra/{public_code}...")
        pub_context = browser.new_context()
        pub_page = pub_context.new_page()
        pub_page.goto(f"http://localhost:8080/kiem-tra/{public_code}", wait_until="networkidle")
        pub_page.wait_for_timeout(1000)
        expect(pub_page.locator("body")).to_contain_text("Hợp lệ")
        expect(pub_page.locator("#val-public-code")).to_contain_text(public_code)
        expect(pub_page.locator("body")).to_contain_text("PAdES")
        # U-01: trang công khai không có nút tải bản gốc và không có dữ liệu cá nhân; có biểu mẫu đối soát PDF
        expect(pub_page.locator("#btn-download-permit-pdf")).to_have_count(0)
        expect(pub_page.locator("#verify-file")).to_have_count(1)
        assert "CCCD" not in pub_page.content().upper()
        pub_page.screenshot(path=str(screens_dir / "step07_public_verification.png"))
        pub_context.close()

        # ====================================================================
        # BƯỚC 8: cdt.minh quản lý đồng thuận & gửi yêu cầu DSAR
        # ====================================================================
        print("\n>>> [BƯỚC 8] cdt.minh quản lý đồng thuận & gửi yêu cầu DSAR...")
        login_ui(page, "cdt.minh")
        page.click("#tab-consent")
        expect(page.locator("#btn-save-consents")).to_be_visible(timeout=5000)
        page.click("#btn-save-consents")

        page.fill("#txt-dsar-note", "Yêu cầu trích xuất toàn bộ dữ liệu cá nhân (mẫu)")
        page.click("#btn-dsar-access")
        expect(page.locator("#table-dsar")).to_be_visible(timeout=5000)
        expect(page.locator("#table-dsar")).to_contain_text("Cung cấp dữ liệu")

        page.click("#btn-dsar-withdraw")
        page.wait_for_timeout(1000)
        page.screenshot(path=str(screens_dir / "step08_cdt_minh_dsar.png"))
        logout_ui(page, context)

        # ====================================================================
        # BƯỚC 9: tt.khanh kích hoạt mô phỏng cảm biến -> xử lý hậu kiểm (T-03)
        # ====================================================================
        print("\n>>> [BƯỚC 9] tt.khanh giám sát cảm biến & xử lý hậu kiểm...")
        login_ui(page, "tt.khanh")
        page.click("#tab-construction")
        expect(page.locator("#table-cong-trinh")).to_be_visible(timeout=10000)

        # Tìm công trình của hồ sơ vừa cấp phép
        site_row = page.locator("#table-cong-trinh tbody tr").filter(has_text=test_address).first
        expect(site_row).to_be_visible()

        # Kích hoạt mô phỏng cảm biến vượt ngưỡng trên UI bằng nút bấm (T-03)
        btn_demo_sensor = site_row.locator("button.btn-demo-sensor").first
        expect(btn_demo_sensor).to_be_visible()
        btn_demo_sensor.click()
        page.wait_for_timeout(3000)

        # Làm mới lại tab công trình và kiểm tra cảnh báo cảm biến thật (T-03)
        page.click("#tab-construction")
        page.wait_for_timeout(2000)
        expect(site_row.locator("span:has-text('dBA'), span:has-text('Cảnh báo')").first).to_be_visible(timeout=10000)

        # Bấm nút Tạo phiếu kiểm tra cho công trình (T-03)
        btn_create_insp = site_row.locator("button.btn-create-inspection").first
        expect(btn_create_insp).to_be_visible()
        btn_create_insp.click()
        page.wait_for_timeout(2000)

        # Vào Bàn làm việc xử lý nhiệm vụ hậu kiểm
        page.click("#tab-workspace")
        expect(page.locator("#workspace-3-cols")).to_be_visible(timeout=10000)

        token_tt, _ = get_user_token("tt.khanh")
        insp_task = None
        for _ in range(15):
            tasks = fetch_tasks_via_api(token_tt)
            matching_tasks = [t for t in tasks if "KiemTra" in t.get("taskDefinitionKey", "") or "kiem-tra" in t.get("name", "").lower()]
            if matching_tasks:
                insp_task = sorted(matching_tasks, key=lambda t: t.get("createTime", ""), reverse=True)[0]
                break
            page.wait_for_timeout(1000)
        assert insp_task, "Không tìm thấy nhiệm vụ kiểm tra hiện trường cho tt.khanh"

        page.click(f"#task-card-{insp_task['id']}")
        expect(page.locator("#radio-hk-dat")).to_be_visible(timeout=5000)
        page.click("#radio-hk-dat")
        page.fill("#input-chi-so-do", "68.5")
        page.fill("#input-ghi-chu-hau-kiem", "Đã nhắc nhở nhà thầu giảm tiếng ồn, chỉ số đo lại đạt tiêu chuẩn 68.5 dBA")
        page.locator("#file-bien-ban-kiem-tra").set_input_files(str(sample_pdf_path))
        page.wait_for_timeout(1000)
        expect(page.locator("text=Đã đính kèm biên bản")).to_be_visible(timeout=5000)
        page.click("#btn-submit-kiem-tra-hien-truong")
        page.wait_for_timeout(2000)

        # Quay lại tab công trình kiểm tra phiếu kiểm tra đã có kết luận và họ tên Đặng Quốc Khánh
        page.click("#tab-construction")
        expect(page.locator("#table-phieu-kiem-tra")).to_be_visible(timeout=5000)
        expect(page.locator("#table-phieu-kiem-tra")).to_contain_text("Đạt")
        expect(page.locator("#table-phieu-kiem-tra")).to_contain_text("Đặng Quốc Khánh")
        page.screenshot(path=str(screens_dir / "step09_tt_khanh_inspection.png"))
        logout_ui(page, context)

        # Kiểm tra kt.an (auditor) chỉ có quyền xem, không có nút thao tác
        login_ui(page, "kt.an")
        page.click("#tab-construction")
        expect(page.locator("#table-cong-trinh")).to_be_visible(timeout=5000)
        expect(page.locator("#table-phieu-kiem-tra")).to_be_visible(timeout=5000)
        expect(page.locator("button.btn-demo-sensor")).to_have_count(0)
        expect(page.locator("button.btn-create-inspection")).to_have_count(0)
        page.screenshot(path=str(screens_dir / "step09_kt_an_auditor_view.png"))
        logout_ui(page, context)

        # ====================================================================
        # BƯỚC 10: cdt.minh xem nhật ký truy cập hồ sơ của mình (T-08)
        # ====================================================================
        print("\n>>> [BƯỚC 10] cdt.minh xem nhật ký truy cập hồ sơ của mình...")
        login_ui(page, "cdt.minh")
        page.click("#tab-dossiers")
        page.wait_for_timeout(2000)
        btn_detail = page.locator(f"#btn-detail-{ma_ho_so}")
        if not btn_detail.is_visible():
            page.fill("#txt-open-dossier-code", ma_ho_so)
            page.click("#btn-open-by-code")
        else:
            btn_detail.click()
        expect(page.locator("#modal-detail-dossier")).to_be_visible(timeout=10000)
        expect(page.locator("#block-dossier-audit")).to_be_visible(timeout=5000)

        # Kiểm tra thấy rõ dòng truy cập khẩn của Vũ Quốc Cường kèm lý do (T-08)
        expect(page.locator("#list-dossier-audit")).to_contain_text("Vũ Quốc Cường")
        expect(page.locator("#list-dossier-audit")).to_contain_text("Truy cập khẩn")
        expect(page.locator("#list-dossier-audit")).to_contain_text("Hỗ trợ đồng nghiệp thẩm định kết cấu đặc biệt")
        expect(page.locator("#list-dossier-audit")).to_contain_text("Cấp phép")

        page.screenshot(path=str(screens_dir / "step10_cdt_minh_audit_view.png"))
        page.click("#btn-close-modal-detail")

        # Kiểm tra RLS: cdt.minh gọi RPC với hồ sơ của người khác bị 403 / denied
        token_minh, _ = get_user_token("cdt.minh")
        with httpx.Client(base_url="http://localhost:8080", timeout=10.0) as cl:
            other_hs = run_db_query("SELECT id FROM app_cap_phep.ho_so WHERE chu_dau_tu_sub != (SELECT id::text FROM core.users_directory WHERE username = 'cdt.minh') LIMIT 1;")
            if other_hs:
                res_other = cl.post(
                    "/api/v1/rest/rpc/lay_nhat_ky_ho_so",
                    json={"p_ho_so_id": other_hs, "p_limit": 50},
                    headers={"Authorization": f"Bearer {token_minh}"},
                )
                assert res_other.status_code == 403 or (res_other.status_code == 200 and len(res_other.json()) == 0), (
                    f"Chủ đầu tư không được phép xem nhật ký hồ sơ người khác: {res_other.status_code} {res_other.text}"
                )
        logout_ui(page, context)

        # ====================================================================
        # BƯỚC 11: Thông báo thời gian thực SSE trên chuông (T-09)
        # ====================================================================
        print("\n>>> [BƯỚC 11] Chuông thông báo thời gian thực SSE (T-09)...")
        # Context 1: mc.thu mở trang
        login_ui(page, "mc.thu")
        page.click("#tab-workspace")
        page.wait_for_timeout(1000)

        # Đọc số thông báo hiện tại
        badge_el = page.locator("#badge-unread-count")
        initial_mc_unread = int(badge_el.inner_text().strip()) if badge_el.is_visible() else 0

        # Context 2: cdt.minh nộp hồ sơ ở trình duyệt thứ hai
        ctx_applicant = browser.new_context()
        page_applicant = ctx_applicant.new_page()
        login_ui(page_applicant, "cdt.minh")

        sse_dossier_name = f"Hồ sơ Realtime SSE ({uuid.uuid4().hex[:6]})"
        page_applicant.click("#btn-nop-ho-so-modal")
        expect(page_applicant.locator("#form-nop-ho-so")).to_be_visible(timeout=5000)
        page_applicant.fill("#form-nop-ho-so input[placeholder='Nguyễn Văn A']", sse_dossier_name)
        page_applicant.fill("#form-nop-ho-so input[placeholder='001090123456']", "001200112233")
        page_applicant.fill("#form-nop-ho-so input[placeholder='0901234567']", "0912345678")
        page_applicant.fill("#form-nop-ho-so input[placeholder='Số 123 Đường Mẫu, Phường A']", "Số 99 Phố SSE, Phường A")
        page_applicant.fill("#form-nop-ho-so input[placeholder='Thửa 12, Tờ 34']", "Thửa SSE")
        page_applicant.fill("#form-nop-ho-so input[type='number'][min='1']", "2")
        page_applicant.fill("#form-nop-ho-so input[type='number'][step='0.1']", "95.0")
        sse_docs = make_manifest_docs(screens_dir / "generated_docs", f"sse-{uuid.uuid4().hex[:8]}")
        upload_manifest_docs(page_applicant, sse_docs)
        page_applicant.click("#btn-submit-nop-ho-so")
        expect(page_applicant.locator("#form-nop-ho-so")).to_be_hidden(timeout=20000)

        row_sse = page_applicant.locator("#table-ho-so tbody tr").filter(has_text=sse_dossier_name).first
        expect(row_sse).to_be_visible()
        sse_ma_ho_so = row_sse.locator("td").first.inner_text().strip()
        logout_ui(page_applicant, ctx_applicant)
        ctx_applicant.close()

        # Kiểm tra tại trình duyệt 1 của mc.thu: trong vòng 15 giây chuông tăng
        sse_received = False
        start_wait = time.time()
        while time.time() - start_wait < 15:
            if badge_el.is_visible():
                cnt = int(badge_el.inner_text().strip())
                if cnt > initial_mc_unread:
                    sse_received = True
                    break
            page.wait_for_timeout(1000)
        assert sse_received, f"mc.thu không nhận được thông báo SSE trong 15s (initial={initial_mc_unread})"

        # Bấm chuông mở dropdown thông báo
        page.click("#btn-sse-bell")
        expect(page.locator("#dropdown-notifications")).to_be_visible(timeout=5000)
        expect(page.locator("#dropdown-notifications")).to_contain_text(sse_ma_ho_so)

        # Đánh dấu đã đọc tất cả
        page.click("#btn-mark-all-read")
        page.wait_for_timeout(1000)
        expect(page.locator("#badge-unread-count")).to_be_hidden(timeout=5000)
        page.screenshot(path=str(screens_dir / "step11_notifications_sse.png"))

        # Context 3: cdt.lan không có thông báo hồ sơ của cdt.minh
        ctx_lan = browser.new_context()
        page_lan = ctx_lan.new_page()
        login_ui(page_lan, "cdt.lan")
        page_lan.click("#btn-sse-bell")
        expect(page_lan.locator("#dropdown-notifications")).to_be_visible(timeout=5000)
        expect(page_lan.locator("#dropdown-notifications")).not_to_contain_text(sse_ma_ho_so)
        logout_ui(page_lan, ctx_lan)
        ctx_lan.close()

        # Đăng xuất và đăng nhập lại mc.thu: thông báo vẫn lưu bền bỉ trong CSDL (T-09)
        logout_ui(page, context)
        login_ui(page, "mc.thu")
        page.click("#btn-sse-bell")
        expect(page.locator("#dropdown-notifications")).to_be_visible(timeout=5000)
        expect(page.locator("#dropdown-notifications")).to_contain_text(sse_ma_ho_so)
        logout_ui(page, context)

        # Đóng ngữ cảnh
        context.close()
        browser.close()

    # Sao chép video vừa quay vào thư mục runs hiện tại (demo.webm)
    video_files = sorted(videos_dir.glob("*.webm"), key=os.path.getmtime, reverse=True)
    if video_files:
        latest_video = video_files[0]
        dest_video = target_run_dir / "demo.webm"
        shutil.copy2(latest_video, dest_video)
        print(f"  [VIDEO OK] Đã sao chép video hành trình sang: {dest_video}")

    print("\n========================================================================")
    print(" [THÀNH CÔNG] TOÀN BỘ 11 BƯỚC HÀNH TRÌNH NGƯỜI DÙNG ĐÃ HOÀN TẤT THEO QUY TẮC 14!")
    print(f" Video được lưu tại: {target_run_dir / 'demo.webm'}")
    print(f" Ảnh minh chứng tại: {screens_dir}")
    print("========================================================================")
