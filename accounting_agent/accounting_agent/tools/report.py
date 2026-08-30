"""HTML 报告生成：纯内联 SVG 图表（离线可用，无需 CDN）。

图表能力（generate_chart 节点按需调用）：
  - weekly_pie    周度支出/收入分类占比【饼图·含具体数值】
  - monthly_pie   月度支出/收入分类占比【饼图】
  - daily_bar     消费集中在哪几天【柱状图】
  - monthly_trend 近6个月收支趋势【折线图】
"""
from __future__ import annotations

import base64
import html
from datetime import date, datetime
from pathlib import Path

from accounting_agent.config import Config
from accounting_agent.models import Transaction
from accounting_agent.tools import stats as statslib

# 图表用色板
PALETTE = ["#5B8FF9", "#5AD8A6", "#F6BD16", "#E8684A", "#6DC8EC", "#9270CA",
           "#FF9D4D", "#269A99", "#FF99C3", "#B1E243", "#FF6B81", "#8A94A6"]

_LATEX_ESCAPE = {}


def _esc(s: str) -> str:
    return html.escape(str(s))


def _fmt(value: float, currency: str = "¥") -> str:
    return f"{currency}{value:,.2f}"


# ---------------- SVG 基础 ----------------
def _svg_header(width: int, height: int, title: str) -> str:
    return (f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
            f'font-family="system-ui,-apple-system,Segoe UI,Microsoft YaHei,sans-serif">'
            f'<text x="{width/2}" y="22" text-anchor="middle" font-size="15" font-weight="700" fill="#333">{_esc(title)}</text>')


def _polar(cx: float, cy: float, r: float, angle_deg: float) -> tuple[float, float]:
    import math
    rad = math.radians(angle_deg - 90)
    return cx + r * math.cos(rad), cy + r * math.sin(rad)


def pie_svg(title: str, labels: list[str], values: list[float],
            currency: str = "¥", show_values: bool = True, show_pct: bool = True) -> str:
    """环形饼图，label 旁带具体数值与占比。无数据时显示「无」。"""
    n = len(labels)
    width, height, cx, cy, r = 560, 320, 130, 165, 92
    if n == 0:
        svg = [_svg_header(width, height, title)]
        svg.append(f'<circle cx="{cx}" cy="{cy}" r="{r*0.6}" fill="#f2f3f7"/>')
        svg.append(f'<text x="{cx}" y="{cy+7}" text-anchor="middle" font-size="30" font-weight="700" fill="#bbb">无</text>')
        svg.append(f'<text x="{cx}" y="{cy+30}" text-anchor="middle" font-size="12" fill="#ccc">暂无该时段数据</text>')
        svg.append("</svg>")
        return "".join(svg)
    total = sum(values) or 1.0
    svg = [_svg_header(width, height, title)]
    start = 90
    for i in range(n):
        frac = values[i] / total
        sweep = frac * 360
        x1, y1 = _polar(cx, cy, r, start)
        x2, y2 = _polar(cx, cy, r, start + sweep)
        large = 1 if sweep > 180 else 0
        inner_r = r * 0.58
        ix1, iy1 = _polar(cx, cy, inner_r, start + sweep)
        ix2, iy2 = _polar(cx, cy, inner_r, start)
        color = PALETTE[i % len(PALETTE)]
        path = (f'M {cx} {cy} L {x1:.1f} {y1:.1f} A {r} {r} 0 {large} 1 {x2:.1f} {y2:.1f} '
                f'L {ix1:.1f} {iy1:.1f} A {inner_r} {inner_r} 0 {large} 0 {ix2:.1f} {iy2:.1f} Z')
        svg.append(f'<path d="{path}" fill="{color}" opacity="0.92"><title>{_esc(labels[i])}: {_fmt(values[i], currency)} ({frac*100:.1f}%)</title></path>')
        start += sweep
    svg.append(f'<text x="{cx}" y="{cy-4}" text-anchor="middle" font-size="22" font-weight="800" fill="#333">{_fmt(total, currency)}</text>')
    svg.append(f'<text x="{cx}" y="{cy+16}" text-anchor="middle" font-size="12" fill="#888">合计</text>')
    # 图例
    ly = 56
    for i in range(n):
        if ly > height - 16:
            break
        color = PALETTE[i % len(PALETTE)]
        val = values[i]
        pct = val / total * 100
        txt = f"{labels[i]}  {_fmt(val, currency)}  {pct:.1f}%"
        if not show_values:
            txt = f"{labels[i]}  {pct:.1f}%"
        if not show_pct and show_values:
            txt = f"{labels[i]}  {_fmt(val, currency)}"
        svg.append(f'<rect x="210" y="{ly-11}" width="10" height="10" rx="2" fill="{color}"/>')
        svg.append(f'<text x="226" y="{ly}" font-size="12.5" fill="#444">{_esc(txt)}</text>')
        ly += 19
    svg.append("</svg>")
    return "".join(svg)


def bar_svg(title: str, labels: list[str], values: list[float], currency: str = "¥") -> str:
    """柱状图。"""
    width, height, ml, mr, mt, mb = 760, 330, 70, 20, 42, 42
    n = len(labels)
    if n == 0:
        return _svg_header(width, height, title) + "</svg>"
    vmax = max(values) * 1.15 or 1.0
    pw, ph = width - ml - mr, height - mt - mb
    bw = pw / max(n, 1) * 0.62
    svg = [_svg_header(width, height, title)]
    # 网格线
    for gi in range(5):
        gy = mt + ph - ph * gi / 4
        svg.append(f'<line x1="{ml}" y1="{gy:.1f}" x2="{width-mr}" y2="{gy:.1f}" stroke="#eee" stroke-width="1"/>')
        svg.append(f'<text x="{ml-8}" y="{gy+4:.1f}" text-anchor="end" font-size="11" fill="#999">{vmax*gi/4:.0f}</text>')
    for i in range(n):
        val = values[i]
        h = ph * (val / vmax)
        x = ml + pw * i / max(n, 1) + (pw / max(n, 1) - bw) / 2
        y = mt + ph - h
        color = PALETTE[i % len(PALETTE)]
        svg.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{h:.1f}" rx="3" fill="{color}"><title>{_fmt(val, currency)}</title></rect>')
        svg.append(f'<text x="{x+bw/2:.1f}" y="{y-5:.1f}" text-anchor="middle" font-size="11" font-weight="600" fill="#444">{_fmt(val, currency)}</text>')
        svg.append(f'<text x="{x+bw/2:.1f}" y="{mt+ph+18}" text-anchor="middle" font-size="11.5" fill="#666">{_esc(labels[i])}</text>')
    svg.append("</svg>")
    return "".join(svg)


def line_svg(title: str, labels: list[str], income: list[float], expense: list[float], currency: str = "¥") -> str:
    """双线趋势图。"""
    width, height, ml, mr, mt, mb = 760, 330, 70, 20, 42, 42
    n = len(labels)
    if n == 0:
        return _svg_header(width, height, title) + "</svg>"
    allv = income + expense
    vmax = max(allv) * 1.15 or 1.0
    pw, ph = width - ml - mr, height - mt - mb
    svg = [_svg_header(width, height, title)]
    for gi in range(5):
        gy = mt + ph - ph * gi / 4
        svg.append(f'<line x1="{ml}" y1="{gy:.1f}" x2="{width-mr}" y2="{gy:.1f}" stroke="#eee"/>')
        svg.append(f'<text x="{ml-8}" y="{gy+4:.1f}" text-anchor="end" font-size="11" fill="#999">{vmax*gi/4:.0f}</text>')
    step_x = pw / max(n - 1, 1)

    def series(vals: list[float], color: str) -> str:
        pts = [(ml + i * step_x, mt + ph - ph * (v / vmax)) for i, v in enumerate(vals)]
        poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        out = [f'<polyline points="{poly}" fill="none" stroke="{color}" stroke-width="2.5" stroke-linejoin="round"/>']
        for (x, y), v in zip(pts, vals):
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{color}"><title>{_fmt(v, currency)}</title></circle>')
        return "".join(out)

    svg.append(series(income, "#5AD8A6"))
    svg.append(series(expense, "#E8684A"))
    for i, lab in enumerate(labels):
        x = ml + i * step_x
        svg.append(f'<text x="{x:.1f}" y="{mt+ph+18}" text-anchor="middle" font-size="11" fill="#666">{_esc(lab)}</text>')
    svg.append(f'<rect x="{width-110}" y="46" width="12" height="12" rx="2" fill="#5AD8A6"/><text x="{width-94}" y="56" font-size="11.5" fill="#444">收入</text>')
    svg.append(f'<rect x="{width-110}" y="66" width="12" height="12" rx="2" fill="#E8684A"/><text x="{width-94}" y="76" font-size="11.5" fill="#444">支出</text>')
    svg.append("</svg>")
    return "".join(svg)


# ---------------- 报告组装 ----------------
CHART_BUILDERS = {
    "weekly_pie": lambda cfg, txs: pie_svg("本周支出分类占比",
                                           *(_pairs(statslib.weekly_pie(txs)["expense"], cfg)),
                                           currency=cfg.currency, show_values=True),
    "weekly_income_pie": lambda cfg, txs: pie_svg("本周收入分类占比",
                                                  *(_pairs(statslib.weekly_pie(txs)["income"], cfg)),
                                                  currency=cfg.currency, show_values=True),
    "monthly_pie": lambda cfg, txs: pie_svg("本月支出分类占比",
                                            *(_pairs(statslib.monthly_pie(txs)["expense"], cfg)),
                                            currency=cfg.currency, show_values=True),
    "monthly_income_pie": lambda cfg, txs: pie_svg("本月收入分类占比",
                                                   *(_pairs(statslib.monthly_pie(txs)["income"], cfg)),
                                                   currency=cfg.currency, show_values=True),
    "daily_bar": lambda cfg, txs: _daily_bar(cfg, txs),
    "monthly_trend": lambda cfg, txs: _trend(cfg, txs),
}


def _pairs(breakdown: dict, cfg: Config) -> tuple[list[str], list[float]]:
    by_cat = breakdown.get("by_category", {})
    labels = list(by_cat.keys())
    values = list(by_cat.values())
    return labels, values


def _daily_bar(cfg: Config, txs: list[Transaction]) -> str:
    data = statslib.daily_bar(txs)
    labels = [f"{d['day']}" for d in data["days"]]
    values = [d["value"] for d in data["days"]]
    return bar_svg(f"{data['month']} 每日消费分布", labels, values, currency=cfg.currency)


def _trend(cfg: Config, txs: list[Transaction]) -> str:
    data = statslib.monthly_trend(txs, months=6)
    labels = [m[2:] for m in data["months"]]
    return line_svg("近 6 个月收支趋势", labels, data["income"], data["expense"], currency=cfg.currency)


def build_report(cfg: Config, txs: list[Transaction], inserted: list[Transaction] | None = None,
                 duplicates: list[Transaction] | None = None,
                 extra_charts: list[str] | None = None) -> str:
    """生成并写入 HTML 报告，返回文件路径。"""
    inserted = inserted or []
    duplicates = duplicates or []
    extra_charts = extra_charts or []
    today = date.today().isoformat()

    monthly = statslib.monthly_stats(txs)
    cur_month = today[:7]
    cur = next((m for m in monthly if m.month == cur_month), None)

    blocks: list[str] = []
    # 概览卡片
    cards = []
    cards.append(_card("本月收入", _fmt(cur.total_income, cfg.currency) if cur else "-", "#2f9e44"))
    cards.append(_card("本月支出", _fmt(cur.total_expense, cfg.currency) if cur else "-", "#e8684a"))
    cards.append(_card("结余", _fmt(cur.net, cfg.currency) if cur else "-", "#1971c2"))
    cards.append(_card("累计笔数", str(len(txs)), "#6741d9"))
    blocks.append(f'<div class="cards">{"".join(cards)}</div>')

    # 核心图表（需求要求的三类）
    for key in ["weekly_pie", "weekly_income_pie", "monthly_pie", "monthly_income_pie", "daily_bar"]:
        if key in CHART_BUILDERS:
            blocks.append(f'<div class="chart">{CHART_BUILDERS[key](cfg, txs)}</div>')

    # 按需追加图表
    for key in extra_charts:
        if key in CHART_BUILDERS:
            blocks.append(f'<div class="chart">{CHART_BUILDERS[key](cfg, txs)}</div>')

    # 本次入库 / 去重
    if inserted or duplicates:
        rows = []
        for t in inserted:
            rows.append(f'<tr class="new"><td>{_esc(t.date)}</td><td>{_esc(t.time or "")}</td>'
                        f'<td>{_fmt(t.amount, cfg.currency)}</td><td>{_esc(t.category)}</td>'
                        f'<td>{_esc(t.merchant)}</td><td>入库</td></tr>')
        for t in duplicates:
            rows.append(f'<tr class="dup"><td>{_esc(t.date)}</td><td>{_esc(t.time or "")}</td>'
                        f'<td>{_fmt(t.amount, cfg.currency)}</td><td>{_esc(t.category)}</td>'
                        f'<td>{_esc(t.merchant)}</td><td>重复已跳过</td></tr>')
        blocks.append(f'<h2>本次识别（{len(inserted)} 入库 / {len(duplicates)} 重复）</h2>'
                      f'<table><tr><th>日期</th><th>时间</th><th>金额</th><th>类别</th><th>商户</th><th>状态</th></tr>{"".join(rows)}</table>')

    # 全量明细
    rows = []
    for t in sorted(txs, key=lambda x: (x.date, x.time or ""), reverse=True)[:200]:
        sign = "+" if t.type == "income" else "-"
        rows.append(f'<tr><td>{_esc(t.date)}</td><td>{_esc(t.time or "")}</td>'
                    f'<td class="{"inc" if t.type=="income" else "exp"}">{sign}{_fmt(t.amount, cfg.currency)}</td>'
                    f'<td>{_esc(t.category)}</td><td>{_esc(t.merchant)}</td></tr>')
    blocks.append(f'<h2>账本明细（最近 200 条 / 共 {len(txs)} 条）</h2>'
                  f'<table><tr><th>日期</th><th>时间</th><th>金额</th><th>类别</th><th>商户</th></tr>{"".join(rows)}</table>')

    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>智能记账助手 - {today}</title>
<style>
  body {{ font-family: system-ui,-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;
         margin:0; background:#f6f7fb; color:#222; }}
  header {{ background:linear-gradient(135deg,#5B8FF9,#9270CA); color:#fff;
           padding:26px 32px; }}
  header h1 {{ margin:0; font-size:22px; }}
  header p {{ margin:6px 0 0; opacity:.85; font-size:13px; }}
  main {{ max-width:960px; margin:22px auto; padding:0 16px 60px; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:14px; margin:18px 0; }}
  .card {{ background:#fff; border-radius:14px; padding:18px; box-shadow:0 1px 4px rgba(0,0,0,.06); }}
  .card .label {{ font-size:12.5px; color:#888; }}
  .card .value {{ font-size:22px; font-weight:800; margin-top:6px; }}
  .chart {{ background:#fff; border-radius:14px; padding:14px; margin:16px 0;
           box-shadow:0 1px 4px rgba(0,0,0,.06); overflow-x:auto; }}
  .chart svg {{ width:100%; max-width:820px; height:auto; display:block; margin:0 auto; }}
  h2 {{ font-size:16px; margin:26px 0 12px; color:#333; }}
  table {{ width:100%; border-collapse:collapse; background:#fff; border-radius:12px;
          overflow:hidden; box-shadow:0 1px 4px rgba(0,0,0,.06); font-size:13px; }}
  th {{ background:#f0f2fa; text-align:left; padding:9px 12px; }}
  td {{ padding:8px 12px; border-top:1px solid #f0f0f0; }}
  .inc {{ color:#2f9e44; font-weight:600; }}
  .exp {{ color:#e8684a; font-weight:600; }}
  tr.new td {{ background:#f0fbf4; }}
  tr.dup td {{ background:#fafafa; color:#999; }}
</style></head>
<body>
<header><h1>📒 智能记账助手</h1><p>生成时间：{today} ｜ 数据源：支付记录长截图 OCR + 智能解析</p></header>
<main>{''.join(blocks)}
<p style="text-align:center;color:#aaa;font-size:12px;margin-top:30px">accounting_agent · LangGraph Workflow</p>
</main></body></html>"""

    out_dir = Path(cfg.report_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = out_dir / f"report_{today}_{ts}.html"
    out.write_text(html_doc, encoding="utf-8")
    return str(out)


def _card(label: str, value: str, color: str) -> str:
    return (f'<div class="card"><div class="label">{_esc(label)}</div>'
            f'<div class="value" style="color:{color}">{_esc(value)}</div></div>')
