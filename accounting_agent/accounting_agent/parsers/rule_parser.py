"""规则解析器：零依赖、离线，从 OCR 文本抽取结构化账单。

支持常见支付截图文本形态：
  2024-06-05 12:30  -¥45.00  美团外卖  餐饮
  06-05 08:00  收款 - 工资  +¥12000.00
  ¥123.45 支出 星巴克咖啡
"""
from __future__ import annotations

import re

from accounting_agent.models import ParseResult, Transaction, classify, parse_datetime

INCOME_HINTS = re.compile(r"(收入|收款|到账|工资|奖金|红包|退款|报销|转入|入账)", re.I)
EXCLUDE_HINTS = re.compile(r"(余额|可用|明细|合计|本月|已还|账单|还款金额|优惠|满减|支付成功|付款成功|交易成功|免密|已到账|当前|时间|金额|商户|类别)", re.I)

DATE_RE = re.compile(r"(\d{4}[-/年.]\d{1,2}[-/月.]\d{1,2}|\d{1,2}[-/月]\d{1,2})"
                     r"[ T]?(\d{1,2}:\d{2}(?::\d{2})?)?")
# 带符号或货币符号的金额
SIGNED_AMOUNT_RE = re.compile(r"[+-]\s*[¥￥]?\s*[\d,]+(?:\.\d{1,2})?|[¥￥]\s*[\d,]+(?:\.\d{1,2})?")
# 纯数字金额（两位小数优先）
PLAIN_AMOUNT_RE = re.compile(r"(?<![\d./-])(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})|\d+\.\d{1,2}|(?<!-)\d{1,3}(?:,\d{3})*)(?![\d])")


def _to_float(raw: str) -> float:
    return float(raw.replace(",", "").replace("¥", "").replace("￥", "").replace(" ", "").strip("+"))


def parse_amount(text: str) -> float | None:
    """返回带符号金额：支出为负，收入为正。找不到返回 None。"""
    # 先剔除日期，避免把 "06-05" 当金额
    cleaned = DATE_RE.sub(" ", text)

    for m in SIGNED_AMOUNT_RE.finditer(cleaned):
        raw = m.group(0)
        val = _to_float(raw)
        is_income = raw.lstrip().startswith("+") or bool(INCOME_HINTS.search(text))
        if not raw.lstrip().startswith(("+", "-")):
            is_income = bool(INCOME_HINTS.search(text))
        return abs(val) if is_income else -abs(val)

    for m in PLAIN_AMOUNT_RE.finditer(cleaned):
        raw = m.group(1)
        # 忽略太短的纯整数（如序号、页码），但要保留 "8.88" 这类红包
        if "." not in raw and len(raw) <= 2:
            continue
        val = _to_float(raw)
        return abs(val) if INCOME_HINTS.search(text) else -abs(val)
    return None


def parse_text(text: str) -> ParseResult:
    """把整段 OCR 文本按行解析成交易记录。"""
    result = ParseResult()
    seen_fingerprints: set = set()

    for raw_line in _merge_lines(text.splitlines()):
        line = raw_line.strip()
        if not line:
            continue
        tx = _parse_line(line)
        if tx is None:
            result.skipped.append(raw_line)
            continue
        fp = tx.fingerprint()
        if fp in seen_fingerprints:
            continue
        seen_fingerprints.add(fp)
        result.transactions.append(tx)

    result.transactions.sort(key=lambda t: (t.date, t.time or ""))
    return result


def _merge_lines(lines: list[str]) -> list[str]:
    """把拆开的商户/金额/日期合并到同一行，还原一笔完整交易。

    支持两类常见 OCR 顺序：
      ['美团外卖', '-32.50', '2026-08-05 00:00']   → '美团外卖 -32.50 2026-08-05 00:00'
      ['美团外卖', '2026-08-05 00:00', '-32.50']   → '美团外卖 2026-08-05 00:00 -32.50'
    """
    merged: list[str] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        has_amt = parse_amount(line) is not None
        has_date = bool(DATE_RE.search(line))
        if has_amt:
            if merged and not _has_amount(merged[-1]):
                # 上一行是纯文本(商户)或纯日期行 → 追加到该行
                merged[-1] = f"{merged[-1]} {line}"
                # 形如 [商户, 日期, 金额]：把刚合并的"日期 金额"再吸回商户行
                if (len(merged) >= 2 and not _has_amount(merged[-2])
                        and not DATE_RE.search(merged[-2])
                        and DATE_RE.search(merged[-1])):
                    merged[-2] = f"{merged[-2]} {merged[-1]}"
                    merged.pop()
            else:
                merged.append(line)
        elif has_date and merged and _has_amount(merged[-1]) and not DATE_RE.search(merged[-1]):
            # 上一行已有金额但缺日期 → 附上日期
            merged[-1] = f"{merged[-1]} {line}"
        else:
            merged.append(line)
    return merged


def _has_amount(line: str) -> bool:
    """行内是否含金额。"""
    return parse_amount(line) is not None


def _parse_line(line: str) -> Transaction | None:
    # 排除只有数字没有业务语义的行
    if EXCLUDE_HINTS.search(line):
        return None

    amount = parse_amount(line)
    if amount is None:
        return None

    date_str, time_str = "", None
    m = DATE_RE.search(line)
    if m:
        date_str, time_str = parse_datetime(m.group(0))

    # 去掉日期、时间与金额后的剩余文本作为商户/备注
    residue = DATE_RE.sub(" ", line)
    residue = SIGNED_AMOUNT_RE.sub(" ", residue)
    residue = re.sub(r"[：:；;|｜·\s]+", " ", residue).strip()
    merchant = residue

    tx = Transaction(
        date=date_str or "",
        time=time_str,
        amount=amount,
        merchant=merchant,
        note=line[:120],
        raw_text=line,
    )
    if merchant:
        tx.category = classify(merchant, line)
    return tx
