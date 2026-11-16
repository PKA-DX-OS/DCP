# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import asyncio
import json
import logging
import os
import uuid
import copy
from pathlib import Path
from typing import Optional, Dict, Any
import httpx
import nats
import yaml
from nats.js.errors import NotFoundError
from nats.js.api import ConsumerConfig
from dxos_core.config import settings
from dxos_core.db import get_db_pool
from dxos_core.audit import log_audit_event

logging.basicConfig(level=logging.INFO, format='{"time":"%(asctime)s","level":"%(levelname)s","message":"%(message)s"}')
logger = logging.getLogger("outbox-relay")


def get_alert_hook_config(trigger_process: str) -> Optional[Dict[str, Any]]:
    """Tự động phân giải hook SQL xử lý cảnh báo được app khai báo trong app.yaml (Layer 1/2 decoupling)."""
    apps_dir = Path("/app/apps")
    if not apps_dir.exists():
        apps_dir = Path("apps")
    for app_path in apps_dir.glob("*/app.yaml"):
        try:
            with open(app_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                hooks = data.get("alert_hooks", {})
                if trigger_process in hooks:
                    return hooks[trigger_process]
        except Exception as e:
            logger.warning(f"Lỗi đọc app.yaml tại {app_path}: {e}")
    return None


async def process_alert(msg):
    """
    Xử lý sự kiện cảnh báo vượt ngưỡng alert.threshold từ NATS JetStream (Z-06, N-04, N-05, P-03).
    Thứ tự xử lý:
    1. Gọi SQL hook on_alert trước để kiểm tra tính hợp lệ của site và chống trùng nguyên tử trong CSDL.
    2. Chỉ khi sinh phiếu kiểm tra thành công hoặc phiếu đang chờ quy trình (pending_process) mới khởi động Flowable.
    3. Cập nhật process_instance_id vào phiếu kiểm tra qua hook on_process_started.
    4. Thử lại tối đa 5 lần (nak delay 30s); lần cuối ghi audit alert.dead_letter và ack.
    """
    num_delivered = 1
    try:
        if hasattr(msg, "metadata") and msg.metadata:
            num_delivered = getattr(msg.metadata, "num_delivered", 1)
    except Exception as meta_err:
        logger.debug("Không thể đọc metadata num_delivered: %s", meta_err)

    data = None
    try:
        raw_payload = msg.data.decode("utf-8")
        data = json.loads(raw_payload)
        if isinstance(data, str):
            data = json.loads(data)
        tenant = data.get("tenant")
        site_id = data.get("site_id")
        entity_id = data.get("entity_id", f"urn:ngsi-ld:Site:{site_id}")
        breach = data.get("breach", {})
        if isinstance(breach, str):
            breach = json.loads(breach)
        metric = breach.get("metric", "laeq_dba")
        val = breach.get("value", 0.0)
        threshold = breach.get("threshold", 0.0)
        trigger_process = breach.get("trigger_process")
        window_minutes = int(data.get("window_minutes") or breach.get("window_minutes") or 60)

        # Chỉ ack khi dữ liệu thiếu không thể khắc phục được
        if not tenant or not trigger_process:
            logger.warning("Cảnh báo thiếu tenant hoặc trigger_process không thể sửa được, bỏ qua.")
            await msg.ack()
            return

        pool = await get_db_pool()
        if not pool:
            raise RuntimeError("Database pool chưa sẵn sàng")

        # 1. Tìm cấu hình hook cảnh báo từ app.yaml
        alert_hook_cfg = get_alert_hook_config(trigger_process)
        if not alert_hook_cfg:
            logger.warning(f"Không tìm thấy alert_hook cho process {trigger_process} trong các ứng dụng.")
            await msg.ack()
            return

        on_alert_fn = alert_hook_cfg.get("on_alert")
        if not on_alert_fn:
            logger.warning(f"Cấu hình alert_hook thiếu on_alert cho {trigger_process}.")
            await msg.ack()
            return

        # 2. Bước 1 (N-04, N-05, P-03): Gọi SQL hook on_alert trước để kiểm tra công trình và chống trùng trong CSDL
        result_json = None
        async with pool.acquire() as conn:
            raw_res = await conn.fetchval(
                f"SELECT {on_alert_fn}($1, $2, $3, $4, $5, $6, NULL, $7)",
                tenant, site_id, entity_id, metric, float(val), float(threshold), window_minutes,
            )
            if raw_res:
                result_json = json.loads(raw_res) if isinstance(raw_res, str) else raw_res

        if not result_json:
            raise RuntimeError(f"Hook {on_alert_fn} trả về kết quả rỗng")

        reason = result_json.get("reason")
        is_created = result_json.get("created", False)

        # Site lạ không khớp công trình nào -> không thể sửa, ack bỏ qua
        if not is_created and reason == "unmatched_site":
            logger.info(f"Cảnh báo cho site {site_id} không khớp công trình (unmatched_site). Bỏ qua.")
            await msg.ack()
            return

        # Đã có phiếu và đã có quy trình -> ack bỏ qua chống trùng
        if not is_created and reason == "deduplicated":
            logger.info(f"Cảnh báo cho site {site_id} trùng lặp trong cửa sổ (đã có quy trình). Bỏ qua.")
            await msg.ack()
            return

        # P-03: Nếu is_created = true HOẶC reason == 'pending_process' -> khởi động quy trình Flowable
        if not is_created and reason != "pending_process":
            logger.info(f"Cảnh báo cho site {site_id} không sinh phiếu kiểm tra (lý do: {reason}). Bỏ qua.")
            await msg.ack()
            return

        phieu_id = result_json.get("phieu_id") or result_json.get("id")
        if not phieu_id:
            logger.warning(f"Không tìm thấy phieu_id trong kết quả {result_json}, bỏ qua.")
            await msg.ack()
            return

        # 3. Bước 2 (N-04, P-03, Q-05): Khởi tạo quy trình trong Flowable với businessKey = str(phieu_id)
        # Chống mở trùng: Kiểm tra Flowable xem đã có quy trình nào có businessKey đó chưa trước khi mở mới.
        flowable_url = os.environ.get("FLOWABLE_URL", "http://flowable:8080/flowable-rest")
        flow_user = os.environ.get("FLOWABLE_USER", "rest-admin")
        flow_pass = os.environ.get("FLOWABLE_PASSWORD", "")
        proc_id = None
        phieu_str = str(phieu_id)

        async with httpx.AsyncClient(timeout=5.0) as client:
            # Q-05: Kiểm tra quy trình hiện hữu theo businessKey bằng phieu_id
            check_resp = await client.get(
                f"{flowable_url}/service/runtime/process-instances",
                params={"businessKey": phieu_str, "tenantId": tenant},
                auth=(flow_user, flow_pass),
            )
            if check_resp.status_code == 200:
                instances = check_resp.json().get("data", [])
                if instances:
                    proc_id = instances[0].get("id")
                    logger.info(f"Quy trình Flowable cho phiếu {phieu_str} đã tồn tại (proc_id={proc_id}), tái sử dụng tránh mở trùng.")

            if not proc_id:
                resp = await client.post(
                    f"{flowable_url}/service/runtime/process-instances",
                    auth=(flow_user, flow_pass),
                    json={
                        "processDefinitionKey": trigger_process,
                        "businessKey": phieu_str,
                        "tenantId": tenant,
                        "variables": [
                            {"name": "site_id", "value": site_id},
                            {"name": "entity_id", "value": entity_id},
                            {"name": "phieu_id", "value": phieu_str},
                            {"name": "chi_so", "value": metric},
                            {"name": "gia_tri", "value": float(val)},
                            {"name": "nguong", "value": float(threshold)},
                        ],
                    },
                )
                if resp.status_code not in (200, 201):
                    raise RuntimeError(f"Flowable trả mã {resp.status_code}: {resp.text}")
                proc_id = resp.json().get("id")
                logger.info(f"Đã khởi động quy trình Flowable {trigger_process} (proc_id={proc_id}) cho phiếu {phieu_str}.")

        # 4. Bước 3: Sau khi khởi động Flowable, gán proc_id vào phiếu qua on_process_started
        # Giả lập lỗi ở lần giao đầu tiên theo biến môi trường TEST_FAIL_ON_PROCESS_STARTED hoặc cờ file (Q-05)
        fail_flag = os.environ.get("TEST_FAIL_ON_PROCESS_STARTED") == "1" or Path("/tmp/test_fail_on_process_started").exists()
        if fail_flag and num_delivered == 1:
            raise RuntimeError("Giả lập sự cố on_process_started ở lần giao đầu tiên (Q-05)")

        on_proc_started_fn = alert_hook_cfg.get("on_process_started")
        if proc_id and phieu_id and on_proc_started_fn:
            async with pool.acquire() as conn:
                await conn.execute(
                    f"SELECT {on_proc_started_fn}($1::uuid, $2)",
                    uuid.UUID(str(phieu_id)), proc_id,
                )
                logger.info(f"Đã gán process_instance_id {proc_id} cho phiếu {phieu_id}.")

        await msg.ack()

    except Exception as e:
        logger.error(f"Lỗi khi xử lý thông điệp cảnh báo NATS (giao lần {num_delivered}): {e}")
        nak_delay = 2 if Path("/tmp/test_fail_on_process_started").exists() else int(os.environ.get("ALERT_RETRY_DELAY", "30"))
        if num_delivered >= 5:
            # Lần cuối mà vẫn lỗi -> ghi audit alert.dead_letter kèm payload (đã che dữ liệu nhạy cảm), rồi ack (P-03).
            try:
                masked_payload = {}
                if data and isinstance(data, dict):
                    masked_payload = copy.deepcopy(data)
                    for k in list(masked_payload.keys()):
                        if any(s in k.lower() for s in ("token", "secret", "password", "cccd", "dien_thoai", "phone")):
                            masked_payload[k] = "***"
                tenant_val = (data.get("tenant") if (data and isinstance(data, dict)) else None) or "system"
                site_val = (data.get("site_id") if (data and isinstance(data, dict)) else None) or "unknown"
                await log_audit_event(
                    tenant=tenant_val,
                    action="alert.dead_letter",
                    actor_sub="outbox-relay",
                    actor_type="system",
                    object_type="alert",
                    object_id=str(site_val),
                    detail={
                        "reason": f"Dead letter after {num_delivered} attempts: {str(e)}",
                        "payload": masked_payload,
                        "site_id": site_val,
                        "attempts": num_delivered,
                    },
                )
            except Exception as ae:
                logger.error(f"Lỗi ghi audit alert.dead_letter: {ae}")
            try:
                await msg.ack()
            except Exception as ack_err:
                logger.warning(f"Không thể ack thông điệp sau khi ghi dead letter: {ack_err}")
        else:
            try:
                await msg.nak(delay=nak_delay)
            except Exception as nak_err:
                logger.warning(f"Không thể nak thông điệp sau lỗi: {nak_err}")


async def periodic_user_sync_task():
    """Định kỳ đồng bộ danh mục người dùng từ Keycloak sang core.users_directory mỗi 15 phút (P-05)."""
    sync_interval = int(os.getenv("SYNC_USERS_INTERVAL_SECONDS", "900"))
    await asyncio.sleep(15.0)
    while True:
        try:
            from dxos_core.user_sync import sync_keycloak_users
            logger.info("Bắt đầu chu trình định kỳ đồng bộ người dùng Keycloak...")
            summary = await sync_keycloak_users()
            logger.info(f"Kết quả đồng bộ định kỳ người dùng: {summary}")
        except Exception as e:
            logger.warning(f"Lỗi trong chu trình đồng bộ định kỳ người dùng Keycloak: {e}")
        await asyncio.sleep(sync_interval)


async def run_outbox_relay():
    logger.info("Khởi động worker Outbox Relay...")
    nc = None
    js = None
    sub = None

    # P-05: Khởi động tác vụ nền định kỳ đồng bộ người dùng Keycloak
    asyncio.create_task(periodic_user_sync_task())

    async def ensure_nats_connection():
        nonlocal nc, js, sub
        if nc is not None and nc.is_connected and js is not None:
            return True

        # Đóng kết nối cũ nếu ở trạng thái lỗi
        if nc is not None:
            try:
                await nc.close()
            except Exception as close_err:
                logger.debug(f"Đóng kết nối NATS cũ: {close_err}")
            nc = None
            js = None
            sub = None

        try:
            connect_kwargs = {
                "max_reconnect_attempts": -1,
                "reconnect_time_wait": 2.0,
                "connect_timeout": 3.0,
            }
            nats_user = os.environ.get("NATS_INGEST_USER")
            nats_pass = os.environ.get("NATS_INGEST_PASSWORD")
            if nats_user and nats_pass and "@" not in settings.nats_url:
                connect_kwargs["user"] = nats_user
                connect_kwargs["password"] = nats_pass

            nc = await nats.connect(
                settings.nats_url,
                **connect_kwargs,
            )
            js = nc.jetstream()
            try:
                await js.stream_info("DX_EVENTS")
            except NotFoundError:
                await js.add_stream(name="DX_EVENTS", subjects=["dxos.>"])
            except Exception as se:
                logger.warning(f"Lưu ý kiểm tra stream DX_EVENTS: {se}")

            # Đăng ký consumer bền vững cho alert.threshold (Z-06, P-03)
            try:
                consumer_cfg = ConsumerConfig(
                    durable_name="outbox_alert_consumer",
                    max_deliver=5,
                    ack_wait=30,
                )
                try:
                    ci = await js.consumer_info("DX_EVENTS", "outbox_alert_consumer")
                    if ci.config.max_deliver != 5 or not ci.config.deliver_subject:
                        await js.delete_consumer("DX_EVENTS", "outbox_alert_consumer")
                except Exception as cons_err:
                    logger.debug("Consumer outbox_alert_consumer chưa tồn tại hoặc lỗi lấy thông tin: %s", cons_err)

                sub = await js.subscribe(
                    "dxos.*.alert.threshold",
                    cb=process_alert,
                    config=consumer_cfg,
                    manual_ack=True,
                )
                logger.info("Đã đăng ký JetStream subscriber cho alert.threshold thành công (max_deliver=5).")
            except Exception as sub_err:
                logger.warning(f"Không thể đăng ký subscriber alert.threshold: {sub_err}")

            logger.info("Kết nối thành công tới NATS JetStream.")
            return True
        except Exception as e:
            logger.warning(f"Chưa kết nối được NATS JetStream ({e}), sẽ thử lại sau...")
            nc = None
            js = None
            sub = None
            return False

    while True:
        try:
            pool = await get_db_pool()
            if pool is None:
                logger.warning("Cơ sở dữ liệu chưa sẵn sàng cho outbox-relay, thử lại sau 2 giây...")
                await asyncio.sleep(2.0)
                continue

            # 1. Đảm bảo kết nối tới NATS trước khi rút hàng đợi
            is_nats_ready = await ensure_nats_connection()
            if not is_nats_ready:
                await asyncio.sleep(2.0)
                continue

            # 2. Xử lý các bản ghi outbox chưa phát hành
            async with pool.acquire(timeout=3.0) as conn:
                async with conn.transaction():
                    rows = await conn.fetch(
                        """
                        SELECT id, tenant, topic, payload
                        FROM core.outbox
                        WHERE published_at IS NULL
                        ORDER BY id ASC
                        LIMIT 50
                        FOR UPDATE SKIP LOCKED
                        """
                    )

                    if rows:
                        published_count = 0
                        for row in rows:
                            subject = f"dxos.{row['tenant']}.{row['topic']}"
                            payload_bytes = json.dumps(row["payload"], ensure_ascii=False).encode("utf-8")
                            try:
                                await js.publish(subject, payload_bytes, timeout=3.0)
                                await conn.execute(
                                    "UPDATE core.outbox SET published_at = now() WHERE id = $1",
                                    row["id"],
                                 )
                                published_count += 1
                            except Exception as pub_err:
                                logger.error(f"Lỗi publish NATS subject {subject} (id={row['id']}): {pub_err}")
                                # Nếu publish thất bại, KHÔNG đánh dấu published_at và ngắt batch để kết nối lại
                                nc = None
                                js = None
                                sub = None
                                break

                        if published_count > 0:
                            logger.info(f"Đã phát sóng {published_count} sự kiện outbox lên NATS JetStream.")

        except Exception as e:
            logger.error(f"Lỗi trong chu trình outbox relay: {e}")
            await asyncio.sleep(2.0)
            continue

        await asyncio.sleep(1.0)


if __name__ == "__main__":
    asyncio.run(run_outbox_relay())
