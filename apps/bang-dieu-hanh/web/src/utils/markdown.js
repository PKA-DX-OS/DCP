// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/** Render Markdown tối giản, escape HTML trước để an toàn với nội dung RAG. */
export function escapeHtml(text) {
  return String(text ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function inline(text) {
  return text
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
}

export function renderMarkdown(text) {
  const escaped = escapeHtml(text);
  const lines = escaped.split(/\r?\n/);
  const out = [];
  let list = null;

  const dongList = () => {
    if (list) {
      out.push(`</${list}>`);
      list = null;
    }
  };

  for (const raw of lines) {
    const line = raw.trim();
    if (!line) {
      dongList();
      continue;
    }
    const heading = line.match(/^(#{1,4})\s+(.*)$/);
    if (heading) {
      dongList();
      const cap = Math.min(4, heading[1].length);
      out.push(`<h${cap}>${inline(heading[2])}</h${cap}>`);
      continue;
    }
    const bullet = line.match(/^[-*]\s+(.*)$/);
    if (bullet) {
      if (list !== "ul") {
        dongList();
        out.push("<ul>");
        list = "ul";
      }
      out.push(`<li>${inline(bullet[1])}</li>`);
      continue;
    }
    const ordered = line.match(/^\d+\.\s+(.*)$/);
    if (ordered) {
      if (list !== "ol") {
        dongList();
        out.push("<ol>");
        list = "ol";
      }
      out.push(`<li>${inline(ordered[1])}</li>`);
      continue;
    }
    dongList();
    out.push(`<p>${inline(line)}</p>`);
  }
  dongList();
  return out.join("\n");
}

const LOAI_VAN_BAN = {
  ND: "Nghị định",
  TT: "Thông tư",
  LXD: "Luật Xây dựng",
  LQH: "Luật Quy hoạch",
  LBDLCN: "Luật Bảo vệ dữ liệu cá nhân",
  LLT: "Luật Lưu trữ",
  LP: "Luật Phí và lệ phí",
  LTCQ: "Luật Tổ chức chính quyền địa phương",
};
const TEN_TEP = { "quy-dinh-cap-phep": "Quy định cấp phép của địa bàn" };

/**
 * Tên nguồn trích dẫn cho người đọc: mã trích dẫn pháp lý (`legal/ND217-D53-K1`) thành
 * "Nghị định 217, Điều 53, khoản 1"; tệp tri thức bỏ đuôi `.md`/`.pdf` và đường dẫn.
 */
export function tenNguon(nguon) {
  const s = String(nguon ?? "");
  const base = s.split("#")[0].split("/").pop() || s;
  const ma = base.replace(/\.(md|pdf)$/i, "");
  const m = /^([A-Z]+?)-?(\d+)(?:-D(\d+))?(?:-K(\d+))?(-TOANVAN)?$/.exec(ma);
  if (m && LOAI_VAN_BAN[m[1]]) {
    const phan = [m[1].startsWith("L") ? `${LOAI_VAN_BAN[m[1]]} số ${m[2]}` : `${LOAI_VAN_BAN[m[1]]} ${m[2]}`];
    if (m[3]) phan.push(`Điều ${m[3]}`);
    if (m[4]) phan.push(`khoản ${m[4]}`);
    if (m[5]) phan.push("toàn văn");
    return phan.join(", ");
  }
  if (TEN_TEP[ma]) return TEN_TEP[ma];
  const chu = ma.replace(/[-_]/g, " ").trim();
  return chu.charAt(0).toUpperCase() + chu.slice(1);
}
