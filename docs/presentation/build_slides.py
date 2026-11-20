#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Dựng bộ 10 slide trình bày DX-OS C3 (B-DEMO-02) theo mục 10.2 kế hoạch, nhận diện ở docs/brand.md.

Đầu ra: docs/presentation/dxos-c3.pptx (sửa được bằng PowerPoint/LibreOffice) và, nếu có LibreOffice,
docs/presentation/dxos-c3.pdf.

Số liệu slide 9 chỉ lấy từ scripts/impact_metrics.py --json; không có thì slide ghi "chưa đo", không
điền số tự đặt.

Chạy:
    python scripts/impact_metrics.py --json > logs/impact.json     # trên stack đã đi hết kịch bản
    python docs/presentation/build_slides.py --metrics logs/impact.json
    python docs/presentation/build_slides.py                         # không có số đo: slide 9 để trống số
Cần: pip install python-pptx cairosvg; LibreOffice (soffice) để xuất PDF.
"""

import argparse
import io
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

import cairosvg
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Pt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
FONT = "Inter"

# Token nền tối của design system (apps/cap-phep/web/src/design-system/tokens.css)
NEN = RGBColor(11, 18, 32)
MAT = RGBColor(22, 32, 51)
VIEN = RGBColor(51, 65, 85)
CHU = RGBColor(226, 232, 240)
PHU = RGBColor(148, 163, 184)
LAM = RGBColor(96, 165, 250)
VANG = RGBColor(252, 211, 77)
XANH = RGBColor(134, 239, 172)
DO = RGBColor(252, 165, 165)

W, H = Emu(12192000), Emu(6858000)  # 16:9
LOGO_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 34 34"><rect x="1" y="1" width="32" height="32" rx="7" '
    'fill="none" stroke="#60a5fa"/><path d="M8 17 17 9l9 8" fill="none" stroke="#e2e8f0" stroke-width="2.2" '
    'stroke-linecap="round" stroke-linejoin="round"/><path d="M11 16v9h12v-9" fill="none" stroke="#e2e8f0" '
    'stroke-width="2.2" stroke-linejoin="round"/><path d="M14.5 20.5l2 2 3.5-3.6" fill="none" stroke="#fcd34d" '
    'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
)


def cm(x: float) -> Emu:
    return Emu(int(x * 360000))


def _png(svg: Optional[str] = None, url: Optional[str] = None, width: int = 1600) -> io.BytesIO:
    buf = io.BytesIO(cairosvg.svg2png(bytestring=svg.encode() if svg else None, url=url, output_width=width))
    buf.seek(0)
    return buf


def text(slide, x, y, w, h, s, size=16, color=CHU, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(cm(x), cm(y), cm(w), cm(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    lines = s if isinstance(s, list) else [s]
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(4)
        r = p.add_run()
        r.text = line
        r.font.name, r.font.size, r.font.bold, r.font.color.rgb = FONT, Pt(size), bold, color
    return tb


def card(slide, x, y, w, h, fill=MAT, line=VIEN, accent: Optional[RGBColor] = None):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, cm(x), cm(y), cm(w), cm(h))
    s.adjustments[0] = 0.08
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    s.line.color.rgb = line
    s.line.width = Pt(1)
    s.shadow.inherit = False
    if accent is not None:
        bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, cm(x), cm(y + 0.3), cm(0.12), cm(h - 0.6))
        bar.fill.solid()
        bar.fill.fore_color.rgb = accent
        bar.line.fill.background()
    return s


def khung(prs, so: int, tieu_de: str, phu: str = ""):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = NEN
    s.shapes.add_picture(_png(LOGO_SVG, width=128), cm(1.4), cm(1.0), cm(1.0), cm(1.0))
    text(s, 2.7, 1.12, 10, 0.8, "DX-OS C3", 12, PHU, True)
    text(s, 30.0, 1.12, 2.5, 0.8, f"{so}/10", 12, PHU, align=PP_ALIGN.RIGHT)
    text(s, 1.4, 2.4, 31, 1.6, tieu_de, 30, CHU, True)
    if phu:
        text(s, 1.4, 4.0, 31, 1.0, phu, 15, PHU)
    return s


def chan(s, ghi: str):
    text(s, 1.4, 18.1, 31, 0.6, ghi, 10, PHU)


def build(metrics: Optional[Dict[str, Any]]) -> Presentation:
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H

    # 1. Vấn đề
    s = khung(prs, 1, "Xin phép xây một căn nhà vẫn đi nhiều vòng",
              "Không thiếu văn bản pháp luật, thiếu cách chứng minh hồ sơ được xử lý đúng luật")
    o = [
        ("Người nộp và quy định", "Không biết hồ sơ thiếu gì cho đến khi bị trả lại", "Nộp đi nộp lại, tốn chi phí"),
        ("Cán bộ và thẩm quyền", "Không rõ được và không được yêu cầu gì", "Yêu cầu thừa (trái Điều 56) hoặc bỏ sót (Điều 60)"),
        ("Hậu kiểm và hồ sơ", "Không dựng lại được vì sao hồ sơ được duyệt", "Khó quy trách nhiệm, tranh chấp kéo dài"),
    ]
    for i, (a, b, c) in enumerate(o):
        x = 1.4 + i * 10.4
        card(s, x, 6.0, 9.8, 7.6, accent=DO)
        text(s, x + 0.7, 6.6, 8.6, 1, a, 18, CHU, True)
        text(s, x + 0.7, 8.2, 8.6, 2.4, b, 15, CHU)
        text(s, x + 0.7, 11.0, 8.6, 2.2, c, 13, PHU)
    card(s, 1.4, 14.4, 30.6, 2.8)
    text(s, 2.1, 14.9, 29, 2, ["Luật định: cấp giấy phép xây dựng mới nhà ở riêng lẻ trong 07 ngày làm việc,",
                                "thẩm định trong 03 ngày làm việc (Điều 54 NĐ 217/2026/NĐ-CP)."], 16, VANG, True)
    chan(s, "Nguồn: TaiLieuHanhChinh_C3/00_TAM_NHIN.md, 03_PHAN_TICH/05_DANH_MUC_TTHC_CAP_PHEP.md")

    # 2. Giải pháp
    s = khung(prs, 2, "DX-OS C3: luật chạy được trong phần mềm",
              "Nền tảng mã nguồn mở cho phường: lõi dùng chung và ứng dụng cấp phép xây dựng nhà ở riêng lẻ")
    kg = [
        ("Công dân", "Nộp hồ sơ theo Điều 60, theo dõi tiến độ, dữ liệu của tôi"),
        ("Một cửa", "Tiếp nhận, yêu cầu bổ sung có lý do"),
        ("Thẩm định", "Quy hoạch trên bản đồ, thiết kế theo bộ môn"),
        ("Lãnh đạo", "Phân công, duyệt, ký số; bảng điều hành"),
        ("Trật tự xây dựng", "Nghiệm thu theo mốc, hậu kiểm công trường"),
        ("Kiểm toán và tra cứu", "Chuỗi kiểm toán; ai cũng tra cứu được giấy phép"),
    ]
    for i, (a, b) in enumerate(kg):
        x = 1.4 + (i % 3) * 10.4
        y = 5.6 + (i // 3) * 5.0
        card(s, x, y, 9.8, 4.4, accent=LAM)
        text(s, x + 0.7, y + 0.6, 8.6, 1, a, 18, CHU, True)
        text(s, x + 0.7, y + 1.9, 8.6, 2.2, b, 14, PHU)
    text(s, 1.4, 16.0, 31, 1.6, "6 không gian làm việc theo vai, một quy trình BPMN, một nhật ký kiểm toán. "
         "Chạy trọn trên máy chủ của phường, không phụ thuộc dịch vụ đám mây.", 15, CHU)
    chan(s, "Mã nguồn: github.com/PKA-DX-OS/DCP · AGPL-3.0-or-later")

    # 3. Kiến trúc
    s = khung(prs, 3, "Kiến trúc: bốn lớp, bảo mật xuyên suốt")
    arch = ROOT / "docs" / "images" / "architecture.svg"
    s.shapes.add_picture(_png(url=str(arch), width=2400), cm(3.2), cm(4.2), cm(27.2), cm(17.5 * 27.2 / 40.0))
    chan(s, "Chi tiết: docs/architecture-onepage.md, docs/architecture.md")

    # 4. Vòng đời hồ sơ
    s = khung(prs, 4, "Vòng đời một hồ sơ", "Mỗi bước là một việc trong quy trình, có người chịu trách nhiệm và hạn xử lý")
    buoc = [
        ("Nộp", "Công dân", "Điều 60"), ("Tiếp nhận", "Một cửa", "Điều 56"), ("Phân công", "Lãnh đạo", "SoD"),
        ("Quy hoạch", "Thẩm định", "chỉ tiêu vùng"), ("Thiết kế", "Thẩm định", "đa bộ môn"),
        ("Duyệt, ký", "Lãnh đạo", "PAdES"), ("Nghiệm thu", "Trật tự XD", "theo mốc"), ("Tra cứu", "Mọi người", "mã công khai"),
    ]
    for i, (a, b, c) in enumerate(buoc):
        x = 1.4 + i * 3.85
        sh = s.shapes.add_shape(MSO_SHAPE.CHEVRON if i else MSO_SHAPE.PENTAGON, cm(x), cm(6.6), cm(3.75), cm(3.0))
        sh.fill.solid()
        sh.fill.fore_color.rgb = MAT
        sh.line.color.rgb = LAM
        text(s, x + (0.2 if i == 0 else 0.9), 7.65, 2.7, 1, a, 13, CHU, True, PP_ALIGN.CENTER)
        text(s, x + 0.2, 10.2, 3.4, 0.8, b, 12, CHU, True, PP_ALIGN.CENTER)
        text(s, x + 0.2, 11.0, 3.4, 0.8, c, 11, PHU, align=PP_ALIGN.CENTER)
    card(s, 1.4, 13.0, 30.6, 4.2)
    text(s, 2.1, 13.5, 29, 3.4, [
        "Hạn hiển thị đúng luật: 07 ngày làm việc cấp phép, 03 ngày thẩm định, 02 ngày bổ sung (Điều 54).",
        "Hồ sơ thiếu giấy bị chặn ngay khi nộp; yêu cầu bổ sung phải có lý do và được ghi nhật ký.",
        "Người thẩm định không tự duyệt; truy cập ngoài phân công phải xin truy cập khẩn, có thời hạn.",
    ], 15, CHU)

    # 5. Quy hoạch
    s = khung(prs, 5, "Quy hoạch: phát hiện sai từ bước thẩm định",
              "Thửa TD-A-01 (vùng QH-A1, dữ liệu tổng hợp): kiểm từng chỉ tiêu, có trích dẫn văn bản")
    hang = [("Chỉ tiêu", "Giới hạn", "Phương án 5 tầng", "Phương án 3 tầng"),
            ("Số tầng", "≤ 3", "5: không đạt", "3: đạt"), ("Chiều cao", "≤ 12 m", "18 m: không đạt", "11,5 m: đạt"),
            ("Mật độ xây dựng", "≤ 70 %", "đạt", "đạt"), ("Khoảng lùi trước", "≥ 3 m", "đạt", "đạt"),
            ("Mục đích sử dụng đất", "đất ở", "đạt", "đạt")]
    tbl = s.shapes.add_table(len(hang), 4, cm(1.4), cm(5.8), cm(30.6), cm(9.0)).table
    for r, row in enumerate(hang):
        for c, v in enumerate(row):
            cell = tbl.cell(r, c)
            cell.fill.solid()
            cell.fill.fore_color.rgb = MAT if r else VIEN
            cell.text = v
            run = cell.text_frame.paragraphs[0].runs[0]
            mau = DO if "không đạt" in v else XANH if v.endswith("đạt") and r else CHU
            run.font.name, run.font.size, run.font.bold, run.font.color.rgb = FONT, Pt(15), r == 0, mau
    text(s, 1.4, 15.6, 31, 2, "Sửa phương án ngay trên màn hình và kiểm lại; mọi lần kiểm tra được lưu để hậu kiểm.", 15, CHU)

    # 6. Thiết kế
    s = khung(prs, 6, "Thẩm định thiết kế đa bộ môn", "Nhận xét gắn vào từng bản vẽ; phiên bản sau chỉ thẩm định phần thay đổi")
    for i, (ten, mau, dong) in enumerate([
        ("Phiên bản v1: không đạt", DO, ["Kiến trúc KT-01: đạt", "Kết cấu: thiếu bản vẽ", "MEP-01 sơ đồ cấp điện: không đạt",
                                         "Nhận xét: bổ sung sơ đồ cấp điện, ghi rõ công suất phụ tải"]),
        ("Phiên bản v2: đạt", XANH, ["Kiến trúc KT-01: đạt (không đổi)", "Kết cấu KC-01: đạt (thêm mới)",
                                     "MEP-02 sơ đồ cấp điện sửa: đạt", "Đủ 3 bộ môn bắt buộc"]),
    ]):
        x = 1.4 + i * 15.6
        card(s, x, 5.8, 15.0, 9.4, accent=mau)
        text(s, x + 0.8, 6.4, 13.6, 1, ten, 20, mau, True)
        text(s, x + 0.8, 8.0, 13.6, 7, ["• " + d for d in dong], 15, CHU)
    text(s, 1.4, 15.9, 31, 1.6, "Bản vẽ xem trực tiếp trong trình duyệt; tệp được quét virus và lưu kèm mã băm.", 15, PHU)
    chan(s, "Hồ sơ minh hoạ CP-HERO-2026-001 (scripts/seed_hero.py), dữ liệu tổng hợp")

    # 7. Nghiệm thu
    s = khung(prs, 7, "Nghiệm thu theo mốc, sai thì ghi lại", "Mỗi lần nghiệm thu là một phiên bản, không ghi đè")
    moc = [("Móng lần 1", "Không đạt", DO, "Cao độ đáy móng thấp hơn thiết kế 12 cm"),
           ("Khắc phục", "Đã khắc phục", VANG, "Chủ đầu tư sửa, trật tự xây dựng xác nhận"),
           ("Móng lần 2", "Đạt", XANH, "Nghiệm thu lại, có biên bản"),
           ("Kết cấu", "Đạt", XANH, "Mốc tiếp theo"),
           ("Hoàn công", "Chờ", PHU, "Một cửa hoặc lãnh đạo xác nhận")]
    for i, (a, b, mau, c) in enumerate(moc):
        x = 1.4 + i * 6.2
        card(s, x, 6.0, 5.8, 7.0, accent=mau)
        text(s, x + 0.6, 6.6, 5, 1, a, 16, CHU, True)
        text(s, x + 0.6, 8.0, 5, 1, b, 18, mau, True)
        text(s, x + 0.6, 9.6, 5, 3, c, 13, PHU)
    text(s, 1.4, 14.2, 31, 2.4, ["Quy trình BPMN nghiệm thu: móng, kết cấu, hoàn thiện, hoàn công.",
                                 "Biên bản và bản vẽ hoàn công nộp kèm từng mốc."], 15, CHU)

    # 8. Bảo mật và kiểm toán
    s = khung(prs, 8, "Tin được: ký số, kiểm toán, dữ liệu cá nhân")
    bm = [("Ký số PAdES", "Khoá nằm trong SoftHSM; sửa một byte là chữ ký không khớp"),
          ("Tra cứu công khai", "/kiem-tra/: không đăng nhập, không lộ dữ liệu cá nhân, trang không script"),
          ("Chuỗi kiểm toán", "Mỗi thao tác một bản ghi nối băm; xác minh và niêm phong được"),
          ("Cách ly dữ liệu", "RLS PostgreSQL theo phường và theo phân công hồ sơ"),
          ("Truy cập khẩn", "Có lý do, có thời hạn, lãnh đạo duyệt, ghi nhật ký"),
          ("Dữ liệu cá nhân", "Đồng thuận, yêu cầu cung cấp và xoá dữ liệu; che CCCD (Luật 91/2025/QH15)")]
    for i, (a, b) in enumerate(bm):
        x = 1.4 + (i % 2) * 15.6
        y = 4.6 + (i // 2) * 4.4
        card(s, x, y, 15.0, 3.9, accent=LAM)
        text(s, x + 0.8, y + 0.5, 13.6, 1, a, 17, CHU, True)
        text(s, x + 0.8, y + 1.7, 13.6, 2, b, 14, PHU)

    # 9. Tác động
    s = khung(prs, 9, "Tác động đo từ hệ thống", "Số liệu chạy lại được bằng scripts/impact_metrics.py")
    d = (metrics or {}).get("do_duoc") or {}

    def so(v, don_vi=""):
        return "chưa đo" if v is None else f"{v}{don_vi}"

    lon = [
        (so(d.get("thoi_gian_xu_ly_tb_ngay_lam_viec")), "ngày làm việc từ nộp đến ký", "luật định: 07 ngày (Điều 54)"),
        (so(d.get("so_kiem_tra_tu_dong")), "lần kiểm tra tự động", "quy hoạch, quét virus, bản vẽ, ký số, nghiệm thu"),
        (so(d.get("ho_so_phat_hien_loi_quy_hoach_som")), "hồ sơ phát hiện sai quy hoạch sớm", "trước khi thiết kế được duyệt"),
    ]
    for i, (a, b, c) in enumerate(lon):
        x = 1.4 + i * 10.4
        card(s, x, 5.6, 9.8, 7.0, accent=VANG)
        text(s, x + 0.8, 6.2, 8.4, 2.6, a, 40 if a != "chưa đo" else 28, VANG, True)
        text(s, x + 0.8, 9.0, 8.4, 1.4, b, 15, CHU, True)
        text(s, x + 0.8, 10.6, 8.4, 1.6, c, 12, PHU)
    tl = d.get("ty_le_ky_dung_han_pct")
    text(s, 1.4, 13.3, 31, 2.4, [
        f"Ký đúng hạn: {so(tl, ' %')} · Hồ sơ phải bổ sung: {so(d.get('ho_so_phai_bo_sung'))} · "
        f"Số vòng thiết kế trung bình: {so(d.get('so_vong_thiet_ke_tb'))}",
        "Giả định: giấy tờ giảm còn 6 tệp điện tử nộp một lần (Điều 60). Mức độ hài lòng: chưa đo.",
    ], 15, CHU)
    ngay = (metrics or {}).get("ngay_do") or "chưa chạy scripts/impact_metrics.py"
    chan(s, f"Đo trên dữ liệu demo tổng hợp, ngày đo: {ngay}. Không có số liệu trước khi có hệ thống nên chỉ so với thời hạn luật.")

    # 10. Lộ trình
    s = khung(prs, 10, "Lộ trình")
    lt = [("Đã làm", XANH, ["Nộp hồ sơ theo Điều 60, chặn thiếu giấy", "Quy hoạch, thiết kế đa bộ môn, nghiệm thu",
                            "Ký số PAdES, tra cứu công khai, chuỗi kiểm toán", "Bảng điều hành, trợ lý có trích dẫn"]),
          ("Tiếp theo", LAM, ["Kết nối Cổng Dịch vụ công Quốc gia (Điều 56)",
                              "Lấy giấy tờ đất từ CSDL quốc gia, không bắt nộp lại (Điều 56 khoản 3)",
                              "Điều chỉnh, gia hạn, cấp lại giấy phép", "Thủ tục PCCC khi có yêu cầu"]),
          ("Thí điểm", VANG, ["Một phường, dữ liệu quy hoạch thật", "Đo thời gian xử lý trước và sau",
                              "Khảo sát hài lòng 5 mức sau khi trả kết quả", "Đối chiếu pháp lý định kỳ khi văn bản đổi"])]
    for i, (a, mau, dong) in enumerate(lt):
        x = 1.4 + i * 10.4
        card(s, x, 4.6, 9.8, 12.4, accent=mau)
        text(s, x + 0.8, 5.2, 8.4, 1, a, 20, mau, True)
        text(s, x + 0.8, 6.8, 8.4, 10, ["• " + d for d in dong], 15, CHU)
    return prs


def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(description="Dựng slide DX-OS C3")
    p.add_argument("--metrics", help="Tệp JSON từ scripts/impact_metrics.py --json")
    p.add_argument("--out", default=str(HERE / "dxos-c3.pptx"))
    p.add_argument("--no-pdf", action="store_true")
    a = p.parse_args(argv)

    metrics = json.loads(Path(a.metrics).read_text(encoding="utf-8")) if a.metrics else None
    out = Path(a.out)
    build(metrics).save(out)
    print(f"Đã ghi {out}")
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not a.no_pdf and soffice:
        subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(out.parent), str(out)],
                       check=True, capture_output=True)
        print(f"Đã ghi {out.with_suffix('.pdf')}")
    elif not a.no_pdf:
        print("Không có LibreOffice: mở .pptx và xuất PDF bằng tay.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
