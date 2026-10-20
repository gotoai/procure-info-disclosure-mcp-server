"""落札実績オープンデータ (successful-bid open data), the one documented download
API of 調達ポータル.

From 「調達ポータル 使い方編」 5.2.2 (https://www.p-portal.go.jp/pps-web-biz/resources/app/pdf/pphowtouse.pdf):

- JSON: ``https://api.p-portal.go.jp/pps-web-biz/UAB03/OAB0302?fileversion=v001&filename=<name>``
  with ``successful_bid_record_info_all_[YYYYMM].json`` (one month of awards) or
  ``successful_bid_record_info_diff_[YYYYMMDD].json`` (one day's additions).
- CSV (zipped): ``.../UAB03/OAB0301?...`` with ``..._all_[YYYY].zip`` (one fiscal year)
  or ``..._diff_[YYYYMMDD].zip``.

Record fields follow 「落札実績オープンデータ ファイル仕様 令和8年3月版」 2.3.
Monthly JSON files exist from April 2019; daily files for roughly the last two months.
The current month's file grows as awards are published.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from .codes import BIDDING_METHODS, MINISTRIES

OPENDATA_JSON_URL = "https://api.p-portal.go.jp/pps-web-biz/UAB03/OAB0302"
OPENDATA_CSV_URL = "https://api.p-portal.go.jp/pps-web-biz/UAB03/OAB0301"
FILE_VERSION = "v001"
PORTAL_DOWNLOAD_PAGE = "https://www.p-portal.go.jp/pps-web-biz/UAB02/OAB0201"

CACHE_SIZE = 12
CACHE_SECONDS = 3600


class OpenDataError(Exception):
    """A failure worth telling the model about in plain words."""


def monthly_filename(year: int, month: int) -> str:
    return f"successful_bid_record_info_all_{year:04d}{month:02d}.json"


def daily_filename(year: int, month: int, day: int) -> str:
    return f"successful_bid_record_info_diff_{year:04d}{month:02d}{day:02d}.json"


class OpenDataClient:
    def __init__(self, url: str = OPENDATA_JSON_URL, timeout: float = 60.0) -> None:
        self._url = url
        self._timeout = timeout
        self._http: httpx.AsyncClient | None = None
        self._files: OrderedDict[str, tuple[float, list[dict[str, Any]]]] = OrderedDict()

    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(
                timeout=self._timeout,
                headers={"User-Agent": "procure-info-disclosure-mcp-server"},
            )
        return self._http

    async def records(self, filename: str) -> list[dict[str, Any]]:
        now = time.monotonic()
        cached = self._files.get(filename)
        if cached and now - cached[0] < CACHE_SECONDS:
            self._files.move_to_end(filename)
            return cached[1]
        try:
            response = await self._client().get(
                self._url, params={"fileversion": FILE_VERSION, "filename": filename}
            )
        except httpx.TimeoutException as error:
            raise OpenDataError("落札実績オープンデータのAPIが時間内に応答しませんでした。") from error
        except httpx.HTTPError as error:
            raise OpenDataError(f"落札実績オープンデータのAPIに接続できませんでした: {error}") from error
        if response.status_code != 200:
            raise OpenDataError(_error_message(response, filename))
        try:
            payload = response.json()
        except ValueError as error:
            raise OpenDataError(f"{filename} はJSONとして読めませんでした。") from error
        records = [record_from_api(item) for item in payload.get("successfulBidRecordInfo") or []]
        self._files[filename] = (now, records)
        self._files.move_to_end(filename)
        while len(self._files) > CACHE_SIZE:
            self._files.popitem(last=False)
        return records


def record_from_api(item: dict[str, Any]) -> dict[str, Any]:
    ministry_code = item.get("ministryCd") or ""
    method_code = item.get("biddingMethodCd") or ""
    return {
        "procurement_item_no": item.get("procurementItemNo"),
        "title": item.get("procurementItemNm"),
        "award_date": item.get("successfulBidDate"),
        "price_yen": _yen(item.get("successfulBidPrice")),
        "ministry_code": ministry_code,
        "ministry": MINISTRIES.get(ministry_code, ministry_code),
        "bidding_method_code": method_code,
        "bidding_method": BIDDING_METHODS.get(method_code, method_code),
        "company": item.get("tradeNameKanji"),
        "corporation_no": item.get("corporationNo") or None,
    }


def _yen(value: Any) -> int | float | None:
    if value in (None, ""):
        return None
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        return None
    return int(amount) if amount == amount.to_integral_value() else float(amount)


def _error_message(response: httpx.Response, filename: str) -> str:
    try:
        message = response.json().get("message")
    except ValueError:
        message = None
    if message and "存在しません" in message:
        return (
            f"{filename} は提供されていません。月別ファイルは2019年4月以降、日別ファイルは"
            "直近約2か月分のみです。"
        )
    return message or f"落札実績オープンデータのAPIが HTTP {response.status_code} を返しました。"
