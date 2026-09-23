import json
import os
from datetime import date
from functools import lru_cache

HOLIDAYS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "holidays")


@lru_cache(maxsize=None)
def get_holidays(year: int) -> dict[date, str]:
    """讀取中華民國政府行政機關辦公日曆表中，該年度有名稱的假日（國定假日、補假等）。
    資料來源：行政院人事行政總處全球資訊網公告的辦公日曆表 CSV。
    若該年度尚無資料檔，回傳空字典（不影響日曆正常顯示，只是不標示假日）。
    """
    path = os.path.join(HOLIDAYS_DIR, f"{year}.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return {date.fromisoformat(k): v for k, v in raw.items()}


def has_holiday_data(year: int) -> bool:
    """該年度是否已有下載整理好的政府行政機關辦公日曆表資料。"""
    return os.path.exists(os.path.join(HOLIDAYS_DIR, f"{year}.json"))
