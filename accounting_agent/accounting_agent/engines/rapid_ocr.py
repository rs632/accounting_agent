"""RapidOCR 引擎（onnxruntime，兼容新版 Python）。"""
from __future__ import annotations

from accounting_agent.engines.ocr_base import BaseOCR, OCRBox


class RapidEngine(BaseOCR):
    name = "rapid"

    def __init__(self):
        from rapidocr_onnxruntime import RapidOCR  # 延迟导入

        self._engine = RapidOCR(intra_op_num_threads=4)

    def recognize(self, image_path: str) -> list[OCRBox]:
        result, _ = self._engine(image_path)
        if not result:
            return []
        rows = []
        for line in result:
            box, text, conf = line[0], line[1], float(line[2])
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            rows.append((min(ys), min(xs), text, conf))
        rows.sort(key=lambda r: (round(r[0] / 14), r[1]))
        return [OCRBox(text=t, confidence=c, y=y, x=x) for y, x, t, c in rows]
