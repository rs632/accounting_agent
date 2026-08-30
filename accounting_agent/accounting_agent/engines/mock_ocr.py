"""Mock OCR 引擎：开发/测试用，读取与图片同名的 .txt 文件作为识别结果。

用途：在没有安装 paddle/rapid 或没有图片时验证整条流水线。
"""
from __future__ import annotations

from pathlib import Path

from accounting_agent.engines.ocr_base import BaseOCR, OCRBox


class MockEngine(BaseOCR):
    name = "mock"

    def recognize(self, image_path: str) -> list[OCRBox]:
        txt = Path(image_path).with_suffix(".txt")
        if not txt.exists():
            raise FileNotFoundError(
                f"[mock-ocr] 未找到 {txt.name}，请先生成同名 .txt 作为模拟 OCR 文本"
            )
        lines = txt.read_text(encoding="utf-8").strip().splitlines()
        return [OCRBox(text=line, confidence=1.0, y=i * 100, x=0.0)
                for i, line in enumerate(lines)]
