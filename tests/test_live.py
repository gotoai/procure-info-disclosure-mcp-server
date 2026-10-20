"""Against the real 調達ポータル. Run with PROCURE_LIVE=1."""

import datetime as dt
import json
import os

import pytest
from mcp import Client

from procure_info_disclosure_mcp_server.server import mcp

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(os.environ.get("PROCURE_LIVE") != "1", reason="set PROCURE_LIVE=1"),
]


def structured(result):
    assert not result.is_error, result.content
    return json.loads(result.content[0].text)


async def test_search_and_notice_end_to_end():
    async with Client(mcp) as client:
        found = structured(
            await client.call_tool(
                "search_procurements",
                {"keywords": "システム", "notice_types": ["一般競争入札の入札公告（WTO対象）", "一般競争入札の入札公告（WTO対象外）"]},
            )
        )
        assert found["total_count"] > 0 and found["items"]
        dates = [
            n["date"]
            for item in found["items"]
            for n in item["notices"]
            if n["stage"] == "調達実施案件公示" and n["status"] == "公開開始"
        ]
        assert dates == sorted(dates, reverse=True), "default sort is newest implement notice first"
        notice = next(n for item in found["items"] for n in item["notices"] if n["notice_id"])
        detail = structured(await client.call_tool("get_procurement_notice", {"notice_id": notice["notice_id"]}))
        assert detail["procurement_item_no"] and detail["title"] and detail["notice_text"]
        assert detail["portal_url"].startswith("https://www.p-portal.go.jp/pps-web-biz/UAA01/OAA0104?")
        if found["total_count"] > 120:
            later = structured(
                await client.call_tool("search_procurements", {"keywords": "システム", "offset": 98, "limit": 5})
            )
            assert len(later["items"]) == 5
            assert later["items"][0]["procurement_item_no"] != found["items"][0]["procurement_item_no"]


async def test_no_hit_and_filters():
    async with Client(mcp) as client:
        none = structured(await client.call_tool("search_procurements", {"keywords": "zzzzqqqqxxxx"}))
        assert none["total_count"] == 0 and none["items"] == []
        osaka = structured(
            await client.call_tool(
                "search_procurements",
                {"keywords": "工事", "agencies": ["国土交通省"], "agency_prefectures": ["大阪府"], "limit": 50},
            )
        )
        assert osaka["items"] and {item["prefecture"] for item in osaka["items"]} == {"大阪府"}
        assert {item["agency"] for item in osaka["items"]} == {"国土交通省"}


async def test_award_records_last_month():
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date()
    last_month = (today.replace(day=1) - dt.timedelta(days=1)).strftime("%Y-%m")
    async with Client(mcp) as client:
        records = structured(await client.call_tool("search_award_records", {"month": last_month, "limit": 5}))
        assert records["total_count"] > 0 and len(records["records"]) == 5
        record = records["records"][0]
        assert record["award_date"].startswith(last_month) and record["price_yen"] is not None
        missing = await client.call_tool("search_award_records", {"month": "2013-04"})
        assert (missing.is_error and "提供されていません" in missing.content[0].text) or structured(missing)["total_count"] == 0
