# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class RoleDef(BaseModel):
    code: str
    name: str
    description: Optional[str] = None


class DocTemplateDef(BaseModel):
    doc_type: str
    template_file: str
    title: str


class IngestRulesDef(BaseModel):
    rules_file: str


class KnowledgeDef(BaseModel):
    dir: str


class MetricDef(BaseModel):
    code: str
    name: str
    unit: str
    query_type: str  # lakehouse, transactional, hybrid, audit
    sql: Optional[str] = None


class SeedDef(BaseModel):
    script: str


class DocumentRequirementDef(BaseModel):
    loai: str
    ten: str
    bat_buoc: bool = True
    yeu_cau_hieu_luc: bool = False
    thong_tin: List[str] = []
    mo_ta: Optional[str] = None


class DocumentManifestDef(BaseModel):
    thu_tuc: str
    ten: str
    requirements: List[DocumentRequirementDef] = []


class AppManifest(BaseModel):
    code: str
    name: str
    version: str
    schema_name: str = Field(alias="schema")
    roles: List[RoleDef] = []
    bpmn: List[str] = []
    doc_templates: List[DocTemplateDef] = []
    ingest_rules: Optional[IngestRulesDef] = None
    knowledge: Optional[KnowledgeDef] = None
    metrics: List[MetricDef] = []
    seed: Optional[SeedDef] = None
    object_access: Dict[str, str] = {}
    flow_policies: Dict[str, Any] = {}
    doc_signers: Dict[str, Any] = {}
    break_glass: Dict[str, Any] = {}
    document_manifest: Optional[DocumentManifestDef] = None


def load_app_manifest(app_dir: Path) -> AppManifest:
    manifest_path = app_dir / "app.yaml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Không tìm thấy app.yaml tại {app_dir}")
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    return AppManifest(**data)


def discover_apps(apps_root: Path) -> Dict[str, AppManifest]:
    apps = {}
    if not apps_root.exists():
        return apps
    for item in apps_root.iterdir():
        if item.is_dir() and (item / "app.yaml").exists():
            try:
                manifest = load_app_manifest(item)
                apps[manifest.code] = manifest
            except Exception as e:
                print(f"[WARN] Lỗi khi nạp manifest app tại {item}: {e}")
    return apps
