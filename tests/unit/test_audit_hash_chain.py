# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

from dxos_core.audit import compute_audit_hash


def test_audit_hash_computation_deterministic():
    """Kiểm tra tính tất định của thuật toán băm chuỗi kiểm toán."""
    prev_hash = b"\x00" * 32
    h1 = compute_audit_hash(prev_hash, "phuong-a", "user-01", "user", "record.create", "object", "obj-1", {"status": "ok"})
    h2 = compute_audit_hash(prev_hash, "phuong-a", "user-01", "user", "record.create", "object", "obj-1", {"status": "ok"})
    assert h1 == h2
    assert len(h1) == 32


def test_audit_tamper_detection_in_memory():
    """Kiểm tra khả năng phát hiện khi một bản ghi trong chuỗi bị can thiệp trái phép."""
    prev_hash = b"\x00" * 32
    records = []

    # Tạo 3 bản ghi liên tiếp
    for i in range(1, 4):
        detail = {"index": i, "data": f"record-{i}"}
        curr_hash = compute_audit_hash(prev_hash, "phuong-a", "admin", "user", "update", "item", str(i), detail)
        records.append({
            "id": i,
            "tenant": "phuong-a",
            "prev_hash": prev_hash,
            "hash": curr_hash,
            "detail": detail,
            "actor_sub": "admin",
            "actor_type": "user",
            "action": "update",
            "object_type": "item",
            "object_id": str(i),
        })
        prev_hash = curr_hash

    # Kiểm tra chuỗi nguyên bản
    def verify(chain):
        p = b"\x00" * 32
        for r in chain:
            if r["prev_hash"] != p:
                return False, r["id"], "Đứt gãy liên kết prev_hash"
            expected = compute_audit_hash(p, r["tenant"], r["actor_sub"], r["actor_type"], r["action"], r["object_type"], r["object_id"], r["detail"])
            if r["hash"] != expected:
                return False, r["id"], "Mã băm không khớp nội dung"
            p = r["hash"]
        return True, None, "Hợp lệ"

    is_valid, tampered_id, _ = verify(records)
    assert is_valid is True

    # Sửa lén bản ghi số 2
    records[1]["detail"]["data"] = "tampered-content"
    is_valid, tampered_id, reason = verify(records)
    assert is_valid is False
    assert tampered_id == 2
    assert "Mã băm không khớp" in reason
