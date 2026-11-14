# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import socket
import struct
import logging
from typing import Tuple
from dxos_core.config import settings

logger = logging.getLogger("dxos.clamav")


class ClamAVClient:
    def __init__(self, host: str = None, port: int = None, timeout: float = 30.0):
        self._host = host
        self._port = port
        self.timeout = timeout

    @property
    def host(self) -> str:
        return self._host or settings.clamav_host

    @property
    def port(self) -> int:
        return self._port or settings.clamav_port

    def scan_stream(self, data: bytes) -> Tuple[str, str]:
        """
        Quét luồng byte qua lệnh zINSTREAM của ClamAV daemon.
        Tuân thủ nguyên tắc Fail-Closed: Mọi tệp đều phải được quét qua clamd thật,
        không tự kiểm tra chuỗi EICAR thủ công, không trả clean khi lỗi kết nối.
        Trả về: (trạng thái: 'clean' | 'infected' | 'scan_failed', chi tiết lỗi/tên virus)
        """
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
                sock.settimeout(self.timeout)
                sock.sendall(b"zINSTREAM\0")
                chunk_size = 2048
                offset = 0
                while offset < len(data):
                    chunk = data[offset : offset + chunk_size]
                    size_header = struct.pack("!I", len(chunk))
                    sock.sendall(size_header + chunk)
                    offset += chunk_size
                # Gửi 4 byte 0 báo hiệu kết thúc luồng
                sock.sendall(struct.pack("!I", 0))

                response = sock.recv(1024).decode("utf-8", errors="replace").strip()
                if "OK" in response:
                    return "clean", "Clean"
                elif "FOUND" in response:
                    virus_name = response.split("FOUND")[0].replace("stream:", "").strip()
                    return "infected", virus_name
                else:
                    logger.warning(f"ClamAV phản hồi bất thường: {response}")
                    return "scan_failed", f"Phản hồi không xác định: {response}"
        except Exception as e:
            logger.error(f"Lỗi kết nối ClamAV daemon: {e}")
            return "scan_failed", str(e)


clamav_client = ClamAVClient()
