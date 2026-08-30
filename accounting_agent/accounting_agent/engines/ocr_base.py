"""OCR 引擎抽象。"""
from __future__ import annotations

import os
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass

# onnxruntime/OpenMP 在服务端多线程下可能死锁，限制并行线程数
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")


@dataclass
class OCRBox:
    text: str
    confidence: float = 0.0
    # 像素坐标：同一视觉行（y 接近）的框会被合并成一行文本
    y: float = 0.0
    x: float = 0.0


def group_lines(boxes: list[OCRBox], y_tol: int = 14) -> list[str]:
    """按 y 坐标把同一视觉行内的 OCR 框合并为一行（按 x 排序后以空格连接）。

    支付截图里金额/商户/日期通常在同一行，OCR 却会拆成多个框；
    这里还原成整行文本，规则解析器才能正确抽取一笔完整交易。
    """
    if not boxes:
        return []
    ordered = sorted(boxes, key=lambda b: (round(b.y / max(y_tol, 1)), b.x))
    lines: list[list[OCRBox]] = []
    for b in ordered:
        if lines and abs(b.y - lines[-1][0].y) <= y_tol:
            lines[-1].append(b)
        else:
            lines.append([b])
    return [" ".join(b.text for b in line) for line in lines]


class BaseOCR(ABC):
    name: str = "base"

    @abstractmethod
    def recognize(self, image_path: str) -> list[OCRBox]:
        """识别图片，返回带坐标的文本框。"""

    def recognize_text(self, image_path: str) -> str:
        return "\n".join(group_lines(self.recognize(image_path)))

    def close(self) -> None:
        pass


def build_engine(engine: str = "auto", lang: str = "ch", use_gpu: bool = False) -> BaseOCR:
    """按配置选择可用引擎，支持 auto 自动探测。

    引擎实例全局缓存复用：服务端多请求场景避免重复加载模型，
    也避免并发初始化 onnxruntime 造成的线程竞争。
    """
    if engine == "auto":
        candidates = ["paddle", "rapid", "mock"]
    elif engine == "paddle":
        candidates = ["paddle"]
    elif engine == "rapid":
        candidates = ["rapid"]
    elif engine == "mock":
        candidates = ["mock"]
    else:
        raise ValueError(f"未知 OCR 引擎: {engine}")

    last_err: Exception | None = None
    for name in candidates:
        try:
            return _get_cached(name, lang, use_gpu)
        except Exception as e:  # noqa: BLE001
            last_err = e
    raise RuntimeError(f"没有可用的 OCR 引擎 (尝试: {', '.join(candidates)})。"
                       f"错误: {last_err}") from last_err


_engine_cache: dict[tuple, BaseOCR] = {}
_engine_cache_lock = threading.Lock()


def _get_cached(name: str, lang: str, use_gpu: bool) -> BaseOCR:
    key = (name, lang, use_gpu)
    with _engine_cache_lock:
        engine = _engine_cache.get(key)
        if engine is None:
            engine = _create(name, lang, use_gpu)
            _engine_cache[key] = engine
        return engine


def _create(name: str, lang: str, use_gpu: bool) -> BaseOCR:
    if name == "paddle":
        from accounting_agent.engines.paddle_ocr import PaddleEngine
        return PaddleEngine(lang=lang, use_gpu=use_gpu)
    if name == "rapid":
        from accounting_agent.engines.rapid_ocr import RapidEngine
        return RapidEngine()
    from accounting_agent.engines.mock_ocr import MockEngine
    return MockEngine()
