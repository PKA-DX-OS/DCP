// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/**
 * Design system của giao diện cấp phép. Màn hình mới (cả track A) import từ đây,
 * không tự đặt màu hay kiểu riêng. Xem trang demo: `npm run dev` rồi mở `/?tab=design-system`.
 */
import "./tokens.css";

export { default as Button } from "./components/Button.vue";
export { default as Input } from "./components/Input.vue";
export { default as Select } from "./components/Select.vue";
export { default as Textarea } from "./components/Textarea.vue";
export { default as Checkbox } from "./components/Checkbox.vue";
export { default as Card } from "./components/Card.vue";
export { default as StatCard } from "./components/StatCard.vue";
export { default as Table } from "./components/Table.vue";
export { default as Badge } from "./components/Badge.vue";
export { default as StatusBadge } from "./components/StatusBadge.vue";
export { default as RoleBadge } from "./components/RoleBadge.vue";
export { default as Tabs } from "./components/Tabs.vue";
export { default as Modal } from "./components/Modal.vue";
export { default as Drawer } from "./components/Drawer.vue";
export { default as Toast } from "./components/Toast.vue";
export { default as EmptyState } from "./components/EmptyState.vue";
export { default as Skeleton } from "./components/Skeleton.vue";
export { default as Pagination } from "./components/Pagination.vue";

export type { SelectOption } from "./components/Select.vue";
export type { TableColumn } from "./components/Table.vue";
export type { TabItem } from "./components/Tabs.vue";
export * from "./variants";

/** Trang demo chỉ có khi chạy dev hoặc build với VITE_DEMO_MODE=1. */
export const DEMO_PAGE_ENABLED: boolean = import.meta.env.DEV || import.meta.env.VITE_DEMO_MODE === "1";
