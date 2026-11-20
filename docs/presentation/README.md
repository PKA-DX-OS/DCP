# Slide trình bày DX-OS C3

Bộ 10 slide theo mục 10.2 kế hoạch, dùng cho cảnh 1–3 và 9 của [demo-script.md](../demo-script.md):
1. Vấn đề
2. Giải pháp
3. Kiến trúc
4. Vòng đời hồ sơ
5. Quy hoạch
6. Thiết kế
7. Nghiệm thu
8. Bảo mật/kiểm toán
9. Tác động
10. Lộ trình

| Tệp | Dùng để |
|---|---|
| `dxos-c3.pdf` | Chiếu và gửi ban giám khảo |
| `dxos-c3.pptx` | Sửa bằng PowerPoint hoặc LibreOffice Impress |
| `build_slides.py` | Dựng lại cả hai tệp từ nội dung trong mã (nên sửa ở đây rồi dựng lại) |

Nhận diện theo [docs/brand.md](../brand.md): nền tối của design system, màu lam `--ds-brand`, vàng `--ds-gold`, font Inter, logo mái nhà và dấu kiểm.

## Điền số liệu slide 9

Slide 9 chỉ nhận số từ `scripts/impact_metrics.py`. Bản trong repo để "chưa đo" vì chưa chạy trên stack thật. Trước buổi trình bày:

```powershell
python scripts/impact_metrics.py --json > logs\impact.json
python docs/presentation/build_slides.py --metrics logs\impact.json
```

Cần `pip install python-pptx cairosvg` và LibreOffice (`soffice`) để xuất PDF. Không có LibreOffice thì mở `.pptx` và xuất PDF bằng tay.

Máy không có font Inter thì PowerPoint thay bằng font khác; bản PDF đã nhúng font nên giữ đúng hình.
