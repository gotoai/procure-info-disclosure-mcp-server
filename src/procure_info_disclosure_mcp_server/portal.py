"""調達ポータル's public 調達情報公開機能, as this server uses it.

The portal has no JSON search API; its public search is an HTML form whose
state lives in a server-side session:

1. ``GET  /pps-web-biz/UAA01/OAA0101`` — the search form; sets the session cookie
   and carries the CSRF token.
2. ``POST /pps-web-biz/UAA01/OAA0100`` — the form, with every field it renders
   (the portal rejects partial submissions); redirects to the first result page.
3. ``POST /pps-web-biz/UAA01/OAA0100`` again with ``sortConditionBean.*`` and the
   sort button — reorders the results and sets 100 rows per page.
4. ``GET  /pps-web-biz/UAA01/OAA0106?page=N&size=100`` — further pages.

A search is capped at 500 rows by the portal. Each search here runs in its own
session, so concurrent calls do not share result state.

One notice's page, ``GET /pps-web-biz/UAA01/OAA0104?procurementItemInfoId=N``,
needs no session.
"""

from __future__ import annotations

import html
import re
from collections import defaultdict
from typing import Any

import httpx

from .codes import NOTICE_STAGES, SORT_FIELDS, SORT_ORDERS
from .text import clean_text, html_to_text, wareki_to_iso

PORTAL_BASE = "https://www.p-portal.go.jp"
SEARCH_FORM_PATH = "/pps-web-biz/UAA01/OAA0101"
SEARCH_ACTION_PATH = "/pps-web-biz/UAA01/OAA0100"
RESULT_PAGE_PATH = "/pps-web-biz/UAA01/OAA0106"
DETAIL_PATH = "/pps-web-biz/UAA01/OAA0104"
DETAIL_URL = PORTAL_BASE + DETAIL_PATH + "?procurementItemInfoId={id}"

PAGE_SIZE = 100
RESULT_CAP = 500
SEARCH_FORM_ID = "tri_WAA0101FM01"
RESULT_CELL_PREFIX = "tri_WAA0101FM01/procurementResultListBean/"
DETAIL_FORM_ID = "tri_WAB0102FM01"

NO_HIT_MESSAGE = "合致する調達案件情報がありません"
CAPPED_MESSAGE = "500件を超えた"
NOT_FOUND_MESSAGE = "該当する調達案件情報が存在しません"
INVALID_SESSION_MESSAGE = "不正な操作が行われました"

USER_AGENT = (
    "procure-info-disclosure-mcp-server (+https://github.com/gotoai/procure-info-disclosure-mcp-server)"
)

_FORM = re.compile(rf'<form id="{SEARCH_FORM_ID}".*?</form>', re.DOTALL)
_INPUT = re.compile(r"<input\b[^>]*>")
_ATTR = {
    name: re.compile(rf'\b{name}="([^"]*)"') for name in ("name", "type", "value", "id")
}
_CSRF = re.compile(r'name="_csrf"\s+value="([^"]*)"')
_RESULT_COUNT = re.compile(r'class="result-number">\s*<strong>(\d+)</strong>')
_ALERT = re.compile(r'<div class="alert (message-error|message-info)[^"]*"[^>]*>(.*?)</div>', re.DOTALL)
_LIST_ITEM = re.compile(r"<li[^>]*>(.*?)</li>", re.DOTALL)
_ROW_START = re.compile(rf'id="{RESULT_CELL_PREFIX}procurementItemNo"')
_NOTICE_LINK = re.compile(
    r"<a\s+class=\"([^\"]*)\"[^>]*procurementItemInfoId'\s*,\s*value:\s*'(\d+)'[^>]*>(.*?)</a>(.*?)(?=<a\s|$)",
    re.DOTALL,
)
_NOTICE_DATE = re.compile(r"((?:令和|平成|昭和)\d{1,2}年\d{1,2}月\d{1,2}日)(公開開始|公開終了)")
_DETAIL_FORM = re.compile(rf'<form id="{DETAIL_FORM_ID}".*?</form>', re.DOTALL)
# Label/value pairs of the detail table. The first row has no id and the two dates
# share one row, so rows are not the unit; th/td pairs are.
_DETAIL_PAIR = re.compile(r"<th>(.*?)</th>\s*<td[^>]*>(.*?)</td>", re.DOTALL)
_LINK = re.compile(r'<a\s[^>]*href="([^"]*)"[^>]*>(.*?)</a>', re.DOTALL)

_DETAIL_FIELDS = {
    "調達案件番号": "procurement_item_no",
    "調達種別": "notice_type",
    "分類": "category",
    "調達案件名称": "title",
    "公開開始日": "public_start",
    "公開終了日": "public_end",
    "調達機関": "agency",
    "調達機関所在地": "agency_location",
    "公告内容": "notice_text",
}
_DATE_FIELDS = {"public_start", "public_end"}


class PortalError(Exception):
    """A failure worth telling the model about in plain words."""


class PortalClient:
    def __init__(self, base_url: str = PORTAL_BASE, timeout: float = 60.0) -> None:
        self._base_url = base_url
        self._timeout = timeout

    def _http(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            follow_redirects=False,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "ja"},
        )

    async def search(
        self,
        criteria: dict[str, list[str]],
        sort_field: str,
        sort_order: str,
        offset: int,
        limit: int,
    ) -> dict[str, Any]:
        """One search: ``criteria`` are form fields (name -> values) laid over the
        form's defaults. Returns total_count, capped and the rows at offset/limit."""
        first_page = offset // PAGE_SIZE
        last_page = (offset + limit - 1) // PAGE_SIZE
        async with self._http() as http:
            form_page = await self._request(http, "GET", SEARCH_FORM_PATH)
            data = form_defaults(form_page.text)
            for name, values in criteria.items():
                data[name] = list(values)
            data["OAA0102"] = ["検索"]
            response = await self._request(
                http, "POST", SEARCH_ACTION_PATH, data=data, referer=SEARCH_FORM_PATH
            )
            page = await self._follow(http, response)

            errors, infos = alerts(page.text)
            if any(NO_HIT_MESSAGE in message for message in errors + infos):
                return {"total_count": 0, "capped": False, "rows": []}
            if errors:
                raise PortalError("調達ポータルが検索条件を受け付けませんでした: " + " / ".join(errors))

            sort_data = {
                "_csrf": [csrf_token(page.text)],
                "sortConditionBean.koumokuName": [SORT_FIELDS[sort_field]],
                "sortConditionBean.order": [SORT_ORDERS[sort_order]],
                "sortConditionBean.displayNo": ["03"],  # 100 rows per page
                "OAA0103": ["並び替え"],
            }
            response = await self._request(
                http, "POST", SEARCH_ACTION_PATH, data=sort_data, referer=RESULT_PAGE_PATH
            )
            page = await self._follow(http, response)
            total, capped = result_count(page.text)
            pages = {0: parse_result_rows(page.text)}
            for number in range(max(first_page, 1), last_page + 1):
                if number * PAGE_SIZE >= total:
                    break
                more = await self._request(
                    http, "GET", RESULT_PAGE_PATH, params={"page": number, "size": PAGE_SIZE}
                )
                pages[number] = parse_result_rows(more.text)
        rows: list[dict[str, Any]] = []
        for number in range(first_page, last_page + 1):
            rows.extend(pages.get(number, []))
        start = offset - first_page * PAGE_SIZE
        return {"total_count": total, "capped": capped, "rows": rows[start : start + limit]}

    async def detail(self, notice_id: str) -> dict[str, Any]:
        async with self._http() as http:
            response = await self._request(
                http, "GET", DETAIL_PATH, params={"procurementItemInfoId": notice_id}
            )
        if NOT_FOUND_MESSAGE in response.text:
            raise PortalError(f"調達ポータルに notice_id {notice_id} の調達情報はありません。")
        detail = parse_detail_page(response.text)
        if not detail.get("procurement_item_no"):
            raise PortalError("調達ポータルの詳細ページを読み取れませんでした。")
        detail["notice_id"] = notice_id
        detail["portal_url"] = DETAIL_URL.format(id=notice_id)
        return detail

    async def _request(
        self,
        http: httpx.AsyncClient,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, list[str]] | None = None,
        referer: str | None = None,
    ) -> httpx.Response:
        headers = {}
        if referer:
            headers["Referer"] = self._base_url + referer
            headers["Origin"] = self._base_url
        try:
            response = await http.request(method, path, params=params, data=data, headers=headers)
        except httpx.TimeoutException as error:
            raise PortalError("調達ポータルが時間内に応答しませんでした。") from error
        except httpx.HTTPError as error:
            raise PortalError(f"調達ポータルに接続できませんでした: {error}") from error
        if response.status_code >= 400:
            raise PortalError(f"調達ポータルが HTTP {response.status_code} を返しました。")
        if INVALID_SESSION_MESSAGE in response.text:
            raise PortalError("調達ポータルが検索セッションを受け付けませんでした。もう一度検索してください。")
        return response

    async def _follow(self, http: httpx.AsyncClient, response: httpx.Response) -> httpx.Response:
        if response.status_code in (301, 302, 303):
            location = response.headers.get("location", "")
            location = location.removeprefix(self._base_url)
            return await self._request(http, "GET", location)
        return response


# --- parsing -----------------------------------------------------------------


def form_defaults(page: str) -> dict[str, list[str]]:
    """Every enabled field of the search form as the browser would submit it
    untouched: hidden and text values, checked radios and checkboxes."""
    match = _FORM.search(page)
    if not match:
        raise PortalError("調達ポータルの検索フォームが見つかりませんでした。")
    fields: dict[str, list[str]] = defaultdict(list)
    for tag in _INPUT.findall(match.group(0)):
        name = _attr(tag, "name")
        if not name or "disabled" in tag:
            continue
        kind = _attr(tag, "type") or "text"
        if kind in ("submit", "button"):
            continue
        if kind in ("checkbox", "radio") and "checked" not in tag:
            continue
        fields[name].append(html.unescape(_attr(tag, "value") or ""))
    return dict(fields)


def csrf_token(page: str) -> str:
    match = _CSRF.search(page)
    if not match:
        raise PortalError("調達ポータルのページからトークンを読み取れませんでした。")
    return match.group(1)


def alerts(page: str) -> tuple[list[str], list[str]]:
    """(error messages, info messages) shown at the top of a page."""
    errors: list[str] = []
    infos: list[str] = []
    for kind, body in _ALERT.findall(page):
        items = [clean_text(item) for item in _LIST_ITEM.findall(body)] or [clean_text(body)]
        (errors if kind == "message-error" else infos).extend(item for item in items if item)
    return errors, infos


def result_count(page: str) -> tuple[int, bool]:
    _, infos = alerts(page)
    capped = any(CAPPED_MESSAGE in info for info in infos)
    match = _RESULT_COUNT.search(page)
    if not match:
        if capped:
            return RESULT_CAP, True
        raise PortalError("調達ポータルの検索結果を読み取れませんでした。")
    return int(match.group(1)), capped


def parse_result_rows(page: str) -> list[dict[str, Any]]:
    starts = [m.start() for m in _ROW_START.finditer(page)]
    rows = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(page)
        rows.append(_parse_row(page[start:end]))
    return rows


def _parse_row(chunk: str) -> dict[str, Any]:
    cells = {
        name: _cell(chunk, name)
        for name in ("procurementItemNo", "articleNm", "procurementOrgan", "receiptAddress")
    }
    notices = []
    for cell_name, stage in NOTICE_STAGES.items():
        for link_class, notice_id, label, trailing in _NOTICE_LINK.findall(_cell(chunk, cell_name) or ""):
            date_match = _NOTICE_DATE.search(trailing)
            notices.append(
                {
                    "stage": stage,
                    "kind": clean_text(label),
                    "notice_id": notice_id,
                    "date": wareki_to_iso(date_match.group(1)) if date_match else None,
                    "status": date_match.group(2) if date_match else None,
                    "ended": link_class.split()[0].endswith("-end"),
                }
            )
    return {
        "procurement_item_no": clean_text(cells["procurementItemNo"]),
        "title": clean_text(cells["articleNm"]),
        "agency": clean_text(cells["procurementOrgan"]),
        "prefecture": clean_text(cells["receiptAddress"]),
        "notices": notices,
    }


def _cell(chunk: str, name: str) -> str | None:
    match = re.search(rf'id="{RESULT_CELL_PREFIX}{name}"[^>]*>(.*?)</td>', chunk, re.DOTALL)
    return match.group(1) if match else None


def parse_detail_page(page: str) -> dict[str, Any]:
    detail: dict[str, Any] = {key: None for key in _DETAIL_FIELDS.values()}
    documents = []
    form = _DETAIL_FORM.search(page)
    for label, body in _DETAIL_PAIR.findall(form.group(0) if form else page):
        label = clean_text(label)
        if label.startswith("調達資料"):
            for href, text in _LINK.findall(body):
                documents.append({"name": clean_text(text), "url": html.unescape(href)})
            continue
        key = _DETAIL_FIELDS.get(label)
        if key is None:
            continue
        if key == "notice_text":
            detail[key] = html_to_text(body)
        elif key in _DATE_FIELDS:
            detail[key] = wareki_to_iso(body) or clean_text(body) or None
        else:
            detail[key] = clean_text(body) or None
    detail["documents"] = documents
    return detail


def _attr(tag: str, name: str) -> str | None:
    match = _ATTR[name].search(tag)
    return match.group(1) if match else None
