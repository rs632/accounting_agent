"""统计：周/月/日/趋势汇总。"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from accounting_agent.models import MonthStats, Transaction


def _month_key(d: date) -> str:
    return d.strftime("%Y-%m")


def _tx_date(t: Transaction) -> date | None:
    """返回交易日期；缺失/非法日期返回 None（统计时跳过）。"""
    if not t.date:
        return None
    try:
        return t.date_obj
    except ValueError:
        return None


def _iso_week(d: date) -> tuple[int, int]:
    return d.isocalendar()[:2]


def weekly_pie(txs: list[Transaction]) -> dict:
    """本周支出/收入按类别占比（含具体数值）。"""
    today = date.today()
    year, week = _iso_week(today)
    items = [t for t in txs if (d := _tx_date(t)) and _iso_week(d) == (year, week)]
    return _category_breakdown(items)


def monthly_pie(txs: list[Transaction]) -> dict:
    """本月支出/收入按类别占比。"""
    cur = _month_key(date.today())
    items = [t for t in txs if (d := _tx_date(t)) and _month_key(d) == cur]
    return _category_breakdown(items)


def _category_breakdown(items: list[Transaction]) -> dict:
    expense, income = defaultdict(float), defaultdict(float)
    for t in items:
        (expense if t.type == "expense" else income)[t.category] += t.amount
    return {
        "count": len(items),
        "expense": {"total": round(sum(expense.values()), 2),
                    "by_category": {k: round(v, 2) for k, v in sorted(expense.items(), key=lambda x: -x[1])}},
        "income": {"total": round(sum(income.values()), 2),
                   "by_category": {k: round(v, 2) for k, v in sorted(income.items(), key=lambda x: -x[1])}},
    }


def daily_bar(txs: list[Transaction]) -> dict:
    """本月每日消费（支出）柱状图数据。"""
    today = date.today()
    cur = _month_key(today)
    days_in_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    daily = defaultdict(float)
    for t in txs:
        d = _tx_date(t)
        if t.type == "expense" and d and _month_key(d) == cur:
            daily[d.day] += t.amount
    return {
        "month": cur,
        "days": [{"day": d, "value": round(daily.get(d, 0.0), 2)} for d in range(1, days_in_month.day + 1)],
    }


def monthly_trend(txs: list[Transaction], months: int = 6) -> dict:
    """近 N 个月收支趋势。"""
    today = date.today()
    keys = []
    y, m = today.year, today.month
    for _ in range(months):
        keys.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    keys.reverse()
    inc, exp = defaultdict(float), defaultdict(float)
    for t in txs:
        d = _tx_date(t)
        if not d:
            continue
        k = _month_key(d)
        if k in keys:
            (inc if t.type == "income" else exp)[k] += t.amount
    return {"months": keys,
            "income": [round(inc[k], 2) for k in keys],
            "expense": [round(exp[k], 2) for k in keys]}


def monthly_stats(txs: list[Transaction]) -> list[MonthStats]:
    """按月份汇总统计。"""
    by_month: dict[str, list[Transaction]] = defaultdict(list)
    for t in txs:
        d = _tx_date(t)
        if d:
            by_month[_month_key(d)].append(t)
    stats = []
    for month in sorted(by_month, reverse=True):
        items = by_month[month]
        expense_cat = defaultdict(float)
        income_total = expense_total = 0.0
        daily = defaultdict(float)
        for t in items:
            d = _tx_date(t)
            if t.type == "expense":
                expense_total += t.amount
                expense_cat[t.category] += t.amount
                if d:
                    daily[d.day] += t.amount
            else:
                income_total += t.amount
        top = [{"category": k, "amount": round(v, 2)}
               for k, v in sorted(expense_cat.items(), key=lambda x: -x[1])]
        stats.append(MonthStats(
            month=month,
            total_income=round(income_total, 2),
            total_expense=round(expense_total, 2),
            net=round(income_total - expense_total, 2),
            tx_count=len(items),
            top_categories=top[:8],
            daily_expense=[{"day": d, "amount": round(v, 2)} for d, v in sorted(daily.items())],
        ))
    return stats
