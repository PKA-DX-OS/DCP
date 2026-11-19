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

/** Bỏ tiền tố/đuôi tệp kỹ thuật để không hiện raw `file.md:` trên UI. */
export function tenNguon(nguon) {
  const s = String(nguon ?? "");
  const base = s.split("#")[0].split("/").pop() || s;
  return base.replace(/\.md$/i, "").replace(/[-_]/g, " ");
}
