"""节点：capture_screen —— 读取长截图。

支持三种来源：
  - local: 显式指定本地图片路径
  - auto : 自动取 screenshots 目录下最新的一张图片
  - adb  : 通过 adb 实时截取安卓手机屏幕
"""
from __future__ import annotations

from pathlib import Path

from langchain_core.runnables import RunnableConfig

from accounting_agent.config import cfg_from_config
from accounting_agent.state import AgentState
from accounting_agent.tools.adb import capture_screen as adb_capture

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def capture_screen_node(state: AgentState, config: RunnableConfig) -> dict:
    cfg = cfg_from_config(config)
    source = state.get("input_path") or cfg.capture_source
    src = str(source).lower()

    if src == "adb":
        path = adb_capture(out_dir=cfg.screenshots_dir)
    elif src in ("auto", ""):
        path = _latest_screenshot(cfg.screenshots_dir)
    else:
        path = _resolve_local(source)

    return {"image_path": path}


def _latest_screenshot(screenshots_dir: str) -> str:
    d = Path(screenshots_dir)
    if not d.exists():
        raise FileNotFoundError(f"screenshots 目录不存在: {d}")
    files = [f for f in d.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTS]
    if not files:
        raise FileNotFoundError(f"screenshots 目录下没有图片: {d}")
    return str(max(files, key=lambda f: f.stat().st_mtime))


def _resolve_local(source: str) -> str:
    p = Path(source)
    if not p.exists():
        raise FileNotFoundError(f"图片不存在: {source}")
    if p.suffix.lower() not in IMAGE_EXTS:
        raise ValueError(f"不支持的图片格式: {source}")
    return str(p.resolve())
