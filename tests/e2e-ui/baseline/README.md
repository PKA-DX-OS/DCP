# Ảnh nền hồi quy hình ảnh

Ảnh nền cho `tests/e2e-ui/test_visual.py`: Chromium, 1366×900, nền tối, dữ liệu demo sau `dx up` (DEMO_MODE=true) và `python scripts/seed_hero.py`.

Lần chạy đầu, test tự tạo ảnh còn thiếu và cảnh báo (không skip), nên một lần chạy tạo đủ ảnh của mọi màn. Kiểm từng ảnh bằng mắt rồi mới commit. Khi giao diện đổi có chủ đích, tạo lại ảnh nền:

```bash
UPDATE_BASELINE=1 pytest tests/e2e-ui/test_visual.py
```

Ngưỡng so ảnh: một điểm ảnh tính là khác khi có kênh màu lệch quá 40/255; một màn hình đạt khi số điểm khác không quá 2 %. Vùng thay đổi theo dữ liệu được che trước khi chụp; màn nằm dưới nhật ký xem hồ sơ (quy hoạch, nghiệm thu, thẩm định thiết kế) chỉ chụp đúng phần đó vì nhật ký dài thêm sau mỗi lần chạy.
