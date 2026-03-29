"""自选股管理服务 - 使用 JSON 文件存储"""
import json
import os
from typing import List

WATCHLIST_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'watchlist.json')


def _ensure_data_dir():
    os.makedirs(os.path.dirname(WATCHLIST_FILE), exist_ok=True)
    if not os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f)


def get_watchlist() -> List[dict]:
    _ensure_data_dir()
    with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def add_to_watchlist(code: str, name: str, market: str = "A") -> List[dict]:
    lst = get_watchlist()
    for item in lst:
        if item["code"] == code:
            return lst
    lst.append({"code": code, "name": name, "market": market})
    _save(lst)
    return lst


def remove_from_watchlist(code: str) -> List[dict]:
    lst = get_watchlist()
    lst = [item for item in lst if item["code"] != code]
    _save(lst)
    return lst


def _save(lst):
    _ensure_data_dir()
    with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
        json.dump(lst, f, ensure_ascii=False, indent=2)
