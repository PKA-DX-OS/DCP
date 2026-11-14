# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import logging
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from fastapi import HTTPException, status
from dxos_core.config import settings

logger = logging.getLogger("dxos.storage")


class StorageClient:
    """
    Client kết nối dịch vụ lưu trữ đối tượng S3 (SeaweedFS).
    Tuân thủ nguyên tắc Fail-Closed: không có RAM fallback hay mock lưu trữ.
    """

    @property
    def s3(self):
        return boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                connect_timeout=3.0,
                read_timeout=10.0,
                retries={"max_attempts": 2},
            ),
        )

    def ensure_buckets(self):
        """Khởi tạo toàn bộ các bucket hệ thống nếu chưa tồn tại."""
        buckets = ["staging", "files", "lake", "worm", "logs"]
        try:
            client = self.s3
            existing = [b["Name"] for b in client.list_buckets().get("Buckets", [])]
            for bucket in buckets:
                if bucket not in existing:
                    try:
                        client.create_bucket(Bucket=bucket)
                    except ClientError as e:
                        logger.warning(f"Lỗi khi tạo bucket {bucket}: {e}")
        except Exception as e:
            logger.error(f"Lỗi kiểm tra buckets S3: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Dịch vụ lưu trữ S3 không sẵn sàng: {e}",
            )

    def put_object(self, bucket: str, key: str, body: bytes, content_type: str = "application/octet-stream") -> str:
        try:
            self.s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType=content_type)
            return key
        except Exception as e:
            logger.error(f"Lỗi ghi đối tượng S3 ({bucket}/{key}): {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Không thể ghi tệp vào kho lưu trữ S3: {e}",
            )

    def get_object(self, bucket: str, key: str) -> bytes:
        try:
            resp = self.s3.get_object(Bucket=bucket, Key=key)
            return resp["Body"].read()
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "NoSuchKey":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Không tìm thấy tệp trong kho lưu trữ",
                )
            logger.error(f"Lỗi đọc đối tượng S3 ({bucket}/{key}): {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Không thể đọc tệp từ kho lưu trữ S3: {e}",
            )
        except Exception as e:
            logger.error(f"Lỗi kết nối kho lưu trữ S3 ({bucket}/{key}): {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Dịch vụ lưu trữ S3 không sẵn sàng: {e}",
            )

    def delete_object(self, bucket: str, key: str):
        try:
            self.s3.delete_object(Bucket=bucket, Key=key)
        except Exception as e:
            logger.error(f"Lỗi xóa đối tượng S3 ({bucket}/{key}): {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Không thể xóa tệp trong kho lưu trữ S3: {e}",
            )

    def copy_object(self, src_bucket: str, src_key: str, dst_bucket: str, dst_key: str):
        try:
            copy_source = {"Bucket": src_bucket, "Key": src_key}
            self.s3.copy_object(CopySource=copy_source, Bucket=dst_bucket, Key=dst_key)
        except Exception as e:
            logger.error(f"Lỗi sao chép đối tượng S3 ({src_bucket}/{src_key} -> {dst_bucket}/{dst_key}): {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Không thể di chuyển/sao chép tệp trong kho lưu trữ S3: {e}",
            )

    def generate_presigned_url(self, bucket: str, key: str, expires_in: int = 300) -> str:
        try:
            url = self.s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=expires_in,
            )
            if settings.public_base_url and "seaweedfs:8333" in url:
                url = url.replace("http://seaweedfs:8333", f"{settings.public_base_url}/api/v1/storage")
            return url
        except Exception as e:
            logger.error(f"Lỗi sinh presigned URL S3 ({bucket}/{key}): {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Không thể tạo liên kết tải tệp: {e}",
            )


storage_client = StorageClient()
