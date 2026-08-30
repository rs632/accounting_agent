"""数据模型：结构化账单 / 统计数据。"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# 常见类别关键词 -> 规范类别
CATEGORY_RULES: dict[str, list[str]] = {
    "餐饮": ["餐", "火锅", "奶茶", "咖啡", "外卖", "食堂", "面", "饭", "烧烤", "肯德基", "麦当劳", "瑞幸", "星巴克", "美团", "饿了么"],
    "交通": ["地铁", "公交", "滴滴", "出租", "打车", "高铁", "火车", "机票", "油", "停车", "自行车", "出行", "12306", "顺风车"],
    "购物": ["淘宝", "京东", "拼多多", "天猫", "商城", "超市", "便利店", "商场", "百货", "购物", "店"],
    "娱乐": ["电影", "游戏", "网吧", "KTV", "演出", "演唱会", "会员", "视频", "音乐", "腾讯视频", "爱奇艺", "优酷", "Steam", "B站"],
    "医疗": ["医院", "药", "诊所", "挂号", "门诊", "体检", "药店", "健康"],
    "居住": ["房租", "物业", "水电", "燃气", "宽带", "维修", "装修", "话费", "电费", "水费"],
    "工资": ["工资", "薪资", "奖金", "补助", "补贴", "劳务", "报销"],
    "转账": ["转账", "红包", "收款", "还款", "借", "还款到账", "付款给"],
    "其他": [],
}

# 类别关键词表顺序即类别名
CATEGORY_ORDER = list(CATEGORY_RULES.keys())


class Transaction(BaseModel):
    """一条结构化账单记录。"""

    date: str = Field(description="交易日期，格式 YYYY-MM-DD")
    time: Optional[str] = Field(default=None, description="交易时间 HH:MM:SS，可选")
    amount: float = Field(description="交易金额，正数为收入，负数为支出")
    category: str = Field(default="其他", description="消费类别")
    merchant: str = Field(default="", description="商户/交易对方")
    type: Literal["income", "expense"] = Field(default="expense", description="收支类型")
    note: Optional[str] = Field(default=None, description="原始文本或备注")
    raw_text: Optional[str] = Field(default=None, description="OCR 原始行文本，用于溯源")

    @field_validator("amount")
    @classmethod
    def _amount(cls, v: float) -> float:
        return round(float(v), 2)

    @model_validator(mode="after")
    def _sync_type(self) -> "Transaction":
        # 仅当调用方未显式指定 type 时，才由金额符号推导收支方向。
        # （amount 存储时恒为正数，序列化回读时必须保留显式的 type）
        if "type" not in self.model_fields_set or not self.type:
            if self.amount >= 0:
                self.type = "income"
            else:
                self.type = "expense"
                self.amount = abs(self.amount)
        else:
            self.amount = abs(self.amount)
        return self

    def fingerprint(self) -> tuple:
        """用于去重的指纹。"""
        return (self.date, self.time, round(self.amount, 2), self.merchant)

    @property
    def signed_amount(self) -> float:
        return self.amount if self.type == "income" else -self.amount

    @property
    def date_obj(self) -> date:
        return date.fromisoformat(self.date)


def classify(merchant: str, note: str = "") -> str:
    """根据商户/备注文本分类。"""
    text = f"{merchant} {note}".lower()
    for cat, keywords in CATEGORY_RULES.items():
        if cat == "其他":
            continue
        for kw in keywords:
            if kw.lower() in text:
                return cat
    return "其他"


class MonthStats(BaseModel):
    """月度统计。"""

    month: str
    total_income: float = 0.0
    total_expense: float = 0.0
    net: float = 0.0
    tx_count: int = 0
    top_categories: list[dict] = Field(default_factory=list)
    daily_expense: list[dict] = Field(default_factory=list)


class ParseResult(BaseModel):
    """解析结果：交易列表 + 无法识别/疑似漏识的原始文本。"""

    transactions: list[Transaction] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list, description="未识别的 OCR 行")

    @property
    def income(self) -> float:
        return sum(t.amount for t in self.transactions if t.type == "income")

    @property
    def expense(self) -> float:
        return sum(t.amount for t in self.transactions if t.type == "expense")


def parse_datetime(value: str) -> tuple[str, Optional[str]]:
    """把 '2024-06-05 12:30' / '2024/6/5 08:00' / '06-05 12:30' / '2024年6月5日' 转成 (date, time)。"""
    value = value.strip().replace("年", "-").replace("月", "-").replace("日", "")
    value = re.sub(r"[./\\]", "-", value)
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?$", value)
    if m:
        year, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        dt = datetime(year, mo, d)
        if m.group(4):
            dt = dt.replace(hour=int(m.group(4)), minute=int(m.group(5)),
                            second=int(m.group(6) or 0))
            return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S")
        return dt.strftime("%Y-%m-%d"), None
    # MM-DD（缺少年份 → 补当前年份）
    m2 = re.match(r"^(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?$", value)
    if m2:
        year = datetime.now().year
        dt = datetime(year, int(m2.group(1)), int(m2.group(2)))
        if m2.group(3):
            dt = dt.replace(hour=int(m2.group(3)), minute=int(m2.group(4)),
                            second=int(m2.group(5) or 0))
            return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S")
        return dt.strftime("%Y-%m-%d"), None
    return "", None
