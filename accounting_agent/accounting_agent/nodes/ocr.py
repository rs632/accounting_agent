"""节点：ocr_image —— 图片识别文字。"""
from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from accounting_agent.config import cfg_from_config
from accounting_agent.engines import build_engine
from accounting_agent.state import AgentState


def ocr_image_node(state: AgentState, config: RunnableConfig) -> dict:
    cfg = cfg_from_config(config)
    image_path = state["image_path"]
    engine = build_engine(engine=cfg.ocr_engine, lang=cfg.ocr_lang, use_gpu=cfg.ocr_use_gpu)
    text = engine.recognize_text(image_path)
    if not text.strip():
        raise RuntimeError(f"OCR 未识别到任何文本: {image_path}")
    return {"ocr_text": text.strip()}
