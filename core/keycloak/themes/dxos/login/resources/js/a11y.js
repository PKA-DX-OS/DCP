/* SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors */
/* SPDX-License-Identifier: AGPL-3.0-or-later */

/* Keycloak chèn tabindex dương vào form đăng nhập; bỏ để thứ tự focus theo DOM. */
(function () {
  function boTabindexDuong() {
    document.querySelectorAll("[tabindex]").forEach(function (el) {
      var n = Number(el.getAttribute("tabindex"));
      if (Number.isFinite(n) && n > 0) {
        el.removeAttribute("tabindex");
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boTabindexDuong);
  } else {
    boTabindexDuong();
  }
  window.addEventListener("load", boTabindexDuong);
})();
