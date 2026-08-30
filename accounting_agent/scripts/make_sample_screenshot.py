"""生成模拟支付记录长截图（含同名 .txt，供 mock OCR 使用）。

用法:
  python scripts/make_sample_screenshot.py
"""
from __future__ import annotations

import random
import sys
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "screenshots"

SAMPLE_TXS = [
    ("美团外卖", 32.50, "餐饮"),
    ("瑞幸咖啡", 19.90, "餐饮"),
    ("地铁", 4.00, "交通"),
    ("滴滴出行", 23.60, "交通"),
    ("京东商城", 159.00, "购物"),
    ("拼多多", 45.90, "购物"),
    ("腾讯视频会员", 25.00, "娱乐"),
    ("星巴克", 39.00, "餐饮"),
    ("沃尔玛超市", 128.40, "购物"),
    ("工资发放", 12000.00, "收入"),
    ("肯德基", 48.50, "餐饮"),
    ("药房", 66.80, "医疗"),
    ("水电费", 156.20, "居住"),
    ("转账-给妈妈", 500.00, "转账"),
    ("支付宝红包", 8.88, "收入"),
]


def _font(size: int):
    for name in ("msyh.ttc", "msyhbd.ttc", "simhei.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_payment_screenshot(txs: list[tuple[str, float, str]],
                            start_date: date,
                            out_path: Path,
                            with_txt: bool = True) -> None:
    width, pad = 720, 40
    header_h, row_h, footer_h = 130, 108, 120
    n = len(txs)
    height = header_h + n * row_h + footer_h
    img = Image.new("RGB", (width, height), "#f7f8fa")
    draw = ImageDraw.Draw(img)
    title_font = _font(34)
    sub_font = _font(24)
    text_font = _font(26)
    money_font = _font(28)

    # 顶部
    draw.rectangle([0, 0, width, header_h], fill="#ffffff")
    draw.text((pad, 34), "账单明细", font=title_font, fill="#222222")
    draw.text((pad, 86), f"2025年 · {start_date.year}年{start_date.month}月", font=sub_font, fill="#999999")
    draw.line([0, header_h, width, header_h], fill="#eeeeee")

    ocr_lines: list[str] = []
    now = start_date
    for i, (merchant, amount, category) in enumerate(txs):
        y = header_h + i * row_h
        draw.rectangle([0, y, width, y + row_h], fill="#ffffff")
        is_income = category == "收入"
        draw.text((pad, y + 22), merchant, font=text_font, fill="#333333")
        time_str = now.strftime("%Y-%m-%d %H:%M")
        draw.text((pad, y + 62), time_str, font=sub_font, fill="#aaaaaa")
        money = f"+{amount:.2f}" if is_income else f"-{amount:.2f}"
        draw.text((width - pad - 190, y + 26), money, font=money_font,
                  fill=("#2f9e44" if is_income else "#333333"))
        draw.line([0, y + row_h, width, y + row_h], fill="#f0f0f0")
        ocr_lines.append(f"{time_str}  {money}  {merchant}")
        # 时间错开：同一张截图里日期递增
        if i % 3 == 2:
            now += timedelta(days=1)
        else:
            now += timedelta(hours=(random.randint(1, 6)))

    # 底部
    draw.rectangle([0, header_h + n * row_h, width, height], fill="#ffffff")
    draw.text((pad, header_h + n * row_h + 34), f"共 {n} 笔 · 本月支出 ¥8,688.00", font=sub_font, fill="#888888")
    ocr_lines.append(f"共 {n} 笔")

    img.save(out_path)
    if with_txt:
        out_path.with_suffix(".txt").write_text("\n".join(ocr_lines), encoding="utf-8")
    print(f"已生成截图: {out_path}  ({width}x{height})")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "payment_history.png"
    start = date.today().replace(day=5)
    draw_payment_screenshot(SAMPLE_TXS, start, out)
    print(f"对应 OCR 文本: {out.with_suffix('.txt')}")


if __name__ == "__main__":
    main()
