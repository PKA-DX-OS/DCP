// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/**
 * Hai hiệu ứng toàn cục cho giao diện kính:
 * 1. Ánh sáng theo con trỏ: ghi toạ độ chuột (--mx, --my) lên tấm kính / nút đang được trỏ,
 *    CSS dùng toạ độ đó vẽ vệt sáng trên mặt kính và mép kính (xem style.css).
 * 2. Hiện lần lượt: khi một nhóm tấm kính được chèn cùng lúc (mở trang, mở chi tiết),
 *    gán độ trễ tăng dần để chúng nổi lên nối tiếp nhau thay vì cùng lúc.
 */
const CO_ANH_SANG = ".the, .btn, .chi-so";
const BUOC_TRE_MS = 70;
const TRE_TOI_DA = 6;

export function batAnhSang(): void {
  if (typeof window === "undefined") return;

  let suKien: PointerEvent | null = null;
  let khung = 0;
  const capNhat = () => {
    khung = 0;
    const e = suKien;
    if (!e) return;
    let el = (e.target as Element | null)?.closest?.(CO_ANH_SANG) as HTMLElement | null;
    // Cập nhật cả tấm kính bao ngoài để mép của nó vẫn sáng khi trỏ vào nút bên trong
    while (el) {
      const r = el.getBoundingClientRect();
      el.style.setProperty("--mx", `${Math.round(e.clientX - r.left)}px`);
      el.style.setProperty("--my", `${Math.round(e.clientY - r.top)}px`);
      el = el.parentElement?.closest(CO_ANH_SANG) as HTMLElement | null;
    }
  };
  window.addEventListener(
    "pointermove",
    (e) => {
      if (e.pointerType !== "mouse") return;
      suKien = e;
      if (!khung) khung = requestAnimationFrame(capNhat);
    },
    { passive: true },
  );

  const quanSat = new MutationObserver((ds) => {
    let thuTu = 0;
    for (const m of ds) {
      m.addedNodes.forEach((n) => {
        if (!(n instanceof HTMLElement)) return;
        const kinh: HTMLElement[] = n.matches(".the") ? [n] : [];
        n.querySelectorAll<HTMLElement>(".the").forEach((x) => kinh.push(x));
        for (const k of kinh) {
          k.style.animationDelay = `${Math.min(thuTu, TRE_TOI_DA) * BUOC_TRE_MS}ms`;
          thuTu++;
        }
      });
    }
  });
  quanSat.observe(document.body, { childList: true, subtree: true });
}
