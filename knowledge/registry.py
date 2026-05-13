import json
from pathlib import Path
from typing import List, Dict

from config import settings
from core.logger import get_logger

logger = get_logger(__name__)

REGISTRY_FILE = settings.DATA_DIR / "document_registry.json"


def load_registry() -> List[Dict]:
    if not REGISTRY_FILE.exists():
        return []

    try:
        with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        logger.exception("读取文档注册表失败")
        return []


def save_registry(records: List[Dict]) -> None:
    settings.ensure_dirs()
    with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def upsert_registry_record(record: Dict) -> None:
    records = load_registry()
    updated = False

    for i, item in enumerate(records):
        if item.get("doc_id") == record.get("doc_id"):
            records[i] = record
            updated = True
            break

    if not updated:
        records.append(record)

    save_registry(records)
    logger.info("文档注册表已写入 | doc_id=%s", record.get("doc_id"))


def remove_registry_record(doc_id: str) -> None:
    records = load_registry()
    records = [r for r in records if r.get("doc_id") != doc_id]
    save_registry(records)
    logger.info("文档注册表已删除 | doc_id=%s", doc_id)