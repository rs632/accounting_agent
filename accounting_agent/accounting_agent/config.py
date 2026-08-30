"""配置加载：config.yaml + 环境变量覆盖。"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT / "config.yaml"


class Config:
    def __init__(self, raw: dict[str, Any], base_dir: Path):
        self._raw = raw
        self.base_dir = base_dir

    def _resolve(self, value: str) -> str:
        return str((self.base_dir / value).resolve()) if value else value

    @property
    def capture_source(self) -> str:
        return self._raw.get("capture", {}).get("source", "auto")

    @property
    def screenshots_dir(self) -> str:
        return self._resolve(self._raw.get("capture", {}).get("screenshots_dir", "screenshots"))

    @property
    def ocr_engine(self) -> str:
        return self._raw.get("ocr", {}).get("engine", "auto")

    @property
    def ocr_lang(self) -> str:
        return self._raw.get("ocr", {}).get("lang", "ch")

    @property
    def ocr_use_gpu(self) -> bool:
        return bool(self._raw.get("ocr", {}).get("use_gpu", False))

    @property
    def parser_mode(self) -> str:
        return self._raw.get("parser", {}).get("mode", "llm")

    @property
    def llm_provider(self) -> str:
        return self._raw.get("llm", {}).get("provider", "openai")

    @property
    def llm_model(self) -> str:
        return self._raw.get("llm", {}).get("model", "gpt-4o-mini")

    @property
    def llm_base_url(self) -> str:
        return self._raw.get("llm", {}).get("base_url", "")

    @property
    def llm_api_key_env(self) -> str:
        return self._raw.get("llm", {}).get("api_key_env", "OPENAI_API_KEY")

    @property
    def llm_api_key(self) -> str:
        """API Key：优先 config.yaml 的 llm.api_key，其次环境变量。"""
        return self._raw.get("llm", {}).get("api_key") or os.environ.get(self.llm_api_key_env, "")

    @property
    def db_path(self) -> str:
        return self._resolve(self._raw.get("storage", {}).get("db_path", "data/ledger.db"))

    @property
    def csv_path(self) -> str:
        return self._resolve(self._raw.get("storage", {}).get("csv_path", "data/ledger.csv"))

    @property
    def dedupe_window_days(self) -> int:
        return int(self._raw.get("storage", {}).get("dedupe_window_days", 7))

    @property
    def report_dir(self) -> str:
        return self._resolve(self._raw.get("report", {}).get("dir", "data/reports"))

    @property
    def open_after(self) -> bool:
        return bool(self._raw.get("report", {}).get("open_after", True))

    @property
    def currency(self) -> str:
        return self._raw.get("stats", {}).get("currency", "¥")

    @property
    def has_llm_key(self) -> bool:
        return bool(self.llm_api_key)

    def dump(self) -> dict:
        return self._raw


def load_config(path: str | Path | None = None, base_dir: Path | None = None) -> Config:
    path = Path(path) if path else DEFAULT_CONFIG_PATH
    base_dir = base_dir or ROOT
    _load_dotenv(base_dir / ".env")
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return Config(raw, base_dir)


def _load_dotenv(path: Path) -> None:
    """极简 .env 加载器：KEY=VALUE，注释以 # 开头。"""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key:
            os.environ.setdefault(key, value.strip().strip("\"'"))


def thread_config(config: Config, thread_id: str) -> dict:
    """构造 LangGraph RunnableConfig，通过 configurable 注入业务配置。"""
    return {"configurable": {"thread_id": thread_id, "_cfg": config}}


def cfg_from_config(runtime: dict) -> Config:
    """节点内从注入的 config 中取出 Config。"""
    return runtime["configurable"]["_cfg"]
