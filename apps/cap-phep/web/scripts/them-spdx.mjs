// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

// Thêm dòng bản quyền REUSE và ghi chú "không sửa tay" vào đầu tệp sinh tự động.
import { readFileSync, writeFileSync } from "node:fs";

// REUSE-IgnoreStart
const HEADER =
  "// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors\n" +
  "// SPDX-License-Identifier: AGPL-3.0-or-later\n\n" +
  "// Sinh từ contracts/design-review.yaml bằng `npm run gen:design-review`; không sửa tay.\n\n";
// REUSE-IgnoreEnd

for (const f of process.argv.slice(2)) {
  const src = readFileSync(f, "utf8");
  if (!src.startsWith("// SPDX-")) writeFileSync(f, HEADER + src);
}
