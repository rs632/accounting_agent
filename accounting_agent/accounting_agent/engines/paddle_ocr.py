"""PaddleOCR 引擎（中文效果好，需要 paddlepaddle）。"""
from __future__ import annotations

from accounting_agent.engines.ocr_base import BaseOCR, OCRBox


class PaddleEngine(BaseOCR):
    name = "paddle"

    def __init__(self, lang: str = "ch", use_gpu: bool = False):
        import numpy as np
        from paddleocr import PaddleOCR  # 延迟导入

        self.np = np
        self._ocr = PaddleOCR(use_angle_cls=True, lang=lang, use_gpu=use_gpu, show_log=False)

    def recognize(self, image_path: str) -> list[OCRBox]:
        result = self._ocr.ocr(image_path, cls=True)
        if not result or not result[0]:
            return []
        rows = []
        for line in result[0]:
            box = line[0]  # 4 个角点
            text, conf = line[1][0], float(line[1][1])
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            rows.append((min(ys), min(xs), text, conf))
        rows.sort(key=lambda r: (round(r[0] / 14), r[1]))
        return [OCRBox(text=t, confidence=c, y=y, x=x) for y, x, t, c in rows]
