# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import os
from pydantic import BaseModel, Field


class Settings(BaseModel):
    public_base_url: str = Field(default_factory=lambda: os.getenv("PUBLIC_BASE_URL", "http://localhost:8080"))
    source_url: str = Field(default_factory=lambda: os.getenv("SOURCE_URL", "https://github.com/dxos-core/dxos"))

    # Cơ sở dữ liệu PostgreSQL
    postgres_host: str = Field(default_factory=lambda: os.getenv("POSTGRES_HOST", "postgres"))
    postgres_port: int = Field(default_factory=lambda: int(os.getenv("POSTGRES_PORT", "5432")))
    postgres_db: str = Field(default_factory=lambda: os.getenv("POSTGRES_DB", "dxos"))
    postgres_user: str = Field(default_factory=lambda: os.getenv("DB_USER", os.getenv("POSTGRES_USER", "dxos_svc")))
    postgres_password: str = Field(default_factory=lambda: os.getenv("DB_PASSWORD", ""))

    # Keycloak
    keycloak_url: str = Field(default_factory=lambda: os.getenv("KEYCLOAK_URL", "http://localhost:8080/auth"))
    keycloak_internal_url: str = Field(default_factory=lambda: os.getenv("KEYCLOAK_INTERNAL_URL", "http://keycloak:8080/auth"))
    keycloak_realm: str = Field(default_factory=lambda: os.getenv("KEYCLOAK_REALM", "dxos"))
    keycloak_admin: str = Field(default_factory=lambda: os.getenv("KEYCLOAK_ADMIN", "admin"))
    keycloak_admin_password: str = Field(default_factory=lambda: os.getenv("KEYCLOAK_ADMIN_PASSWORD", ""))

    # Flowable
    flowable_url: str = Field(default_factory=lambda: os.getenv("FLOWABLE_URL", "http://flowable:8080/flowable-rest"))
    flowable_user: str = Field(default_factory=lambda: os.getenv("FLOWABLE_USER", "rest-admin"))
    flowable_password: str = Field(default_factory=lambda: os.getenv("FLOWABLE_PASSWORD", "test"))

    # NATS
    nats_url: str = Field(default_factory=lambda: os.getenv("NATS_URL", "nats://nats:4222"))

    # SeaweedFS S3
    s3_endpoint: str = Field(default_factory=lambda: os.getenv("SEAWEEDFS_S3_ENDPOINT", "http://seaweedfs:8333"))
    s3_access_key: str = Field(default_factory=lambda: os.getenv("SEAWEEDFS_ACCESS_KEY", "dxos_dev_s3_key_2026"))
    s3_secret_key: str = Field(default_factory=lambda: os.getenv("SEAWEEDFS_SECRET_KEY", "dxos_dev_s3_secret_2026"))

    # ClamAV
    clamav_host: str = Field(default_factory=lambda: os.getenv("CLAMAV_HOST", "clamav"))
    clamav_port: int = Field(default_factory=lambda: int(os.getenv("CLAMAV_PORT", "3310")))

    # OpenBao
    openbao_addr: str = Field(default_factory=lambda: os.getenv("OPENBAO_ADDR", "http://openbao:8200"))
    openbao_token: str = Field(default_factory=lambda: os.getenv("OPENBAO_TOKEN", ""))

    # Ký số: pkcs11 (SoftHSM/PAdES) hoặc openbao (Transit legacy)
    signing_mode: str = Field(default_factory=lambda: os.getenv("SIGNING_MODE", "openbao"))
    softhsm_lib: str = Field(default_factory=lambda: os.getenv("SOFTHSM_LIB", "/usr/lib/softhsm/libsofthsm2.so"))
    softhsm_token: str = Field(default_factory=lambda: os.getenv("SOFTHSM_TOKEN", "dxos"))
    softhsm_pin: str = Field(default_factory=lambda: os.getenv("SOFTHSM_PIN", "1234"))
    softhsm_cert_label: str = Field(default_factory=lambda: os.getenv("SOFTHSM_CERT_LABEL", "doc-sign"))
    softhsm_key_label: str = Field(default_factory=lambda: os.getenv("SOFTHSM_KEY_LABEL", "doc-sign"))
    test_ca_cert: str = Field(default_factory=lambda: os.getenv("TEST_CA_CERT", "/certs/ca.crt"))

    # Demo mode
    demo_mode: bool = Field(default_factory=lambda: os.getenv("DEMO_MODE", "false").lower() == "true")
    demo_mfa: bool = Field(default_factory=lambda: os.getenv("DEMO_MFA", "false").lower() == "true")
    demo_time_scale: float = Field(default_factory=lambda: float(os.getenv("DEMO_TIME_SCALE", "1.0")))
    break_glass_ttl: str = Field(default_factory=lambda: os.getenv("BREAK_GLASS_TTL", "PT2H"))

    @property
    def postgres_dsn(self) -> str:
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"


settings = Settings()
