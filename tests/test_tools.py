"""Tool behaviour with the portal and the open-data API replaced by canned answers."""

import json

import pytest
from mcp import Client

from procure_info_disclosure_mcp_server import server
from procure_info_disclosure_mcp_server.opendata import record_from_api
from procure_info_disclosure_mcp_server.portal import PortalError

ROWS = [
    {
        "procurement_item_no": f"00000000000006{n:05d}",
        "title": f"案件{n}",
        "agency": "総務省",
        "prefecture": "東京都",
        "notices": [
            {
                "stage": "調達実施案件公示",
                "kind": "公示本文",
                "notice_id": str(600000 + n),
                "date": "2026-10-01",
                "status": "公開開始",
                "ended": False,
            }
        ],
    }
    for n in range(7)
]

API_RECORDS = [
    {
        "biddingMethodCd": "8002040",
        "procurementItemNm": "統計研修用LANシステムの借入れ等の請負",
        "successfulBidDate": "2026-10-16",
        "successfulBidPrice": "168500000.00",
        "procurementItemNo": "0000000000000605030",
        "tradeNameKanji": "三菱電機ソフトウエア株式会社",
        "ministryCd": "K1",
        "corporationNo": "9010401028746",
    },
    {
        "biddingMethodCd": "8004020",
        "procurementItemNm": "庁舎清掃業務",
        "successfulBidDate": "2026-10-02",
        "successfulBidPrice": "1234567.50",
        "procurementItemNo": "0000000000000605031",
        "tradeNameKanji": "株式会社クリーン",
        "ministryCd": "S1",
        "corporationNo": "",
    },
]


class FakePortal:
    def __init__(self):
        self.searches = []
        self.fail_with = None

    async def search(self, criteria, sort_field, sort_order, offset, limit):
        self.searches.append((criteria, sort_field, sort_order, offset, limit))
        if self.fail_with:
            raise PortalError(self.fail_with)
        return {"total_count": len(ROWS), "capped": False, "rows": ROWS[offset : offset + limit]}

    async def detail(self, notice_id):
        if notice_id != "600001":
            raise PortalError(f"調達ポータルに notice_id {notice_id} の調達情報はありません。")
        return {
            "procurement_item_no": "00000000000000001",
            "title": "案件1",
            "notice_text": "入札公告",
            "documents": [],
            "notice_id": notice_id,
            "portal_url": f"https://www.p-portal.go.jp/pps-web-biz/UAA01/OAA0104?procurementItemInfoId={notice_id}",
        }


class FakeOpenData:
    def __init__(self):
        self.filenames = []

    async def records(self, filename):
        self.filenames.append(filename)
        return [record_from_api(item) for item in API_RECORDS]


@pytest.fixture
def fake(monkeypatch):
    portal = FakePortal()
    monkeypatch.setattr(server, "_portal", portal)
    return portal


@pytest.fixture
def fake_opendata(monkeypatch):
    opendata = FakeOpenData()
    monkeypatch.setattr(server, "_opendata", opendata)
    return opendata


def structured(result):
    assert not result.is_error, result.content
    return json.loads(result.content[0].text)


async def test_search_maps_arguments_to_form_fields_and_pages(fake):
    async with Client(server.mcp) as client:
        first = structured(
            await client.call_tool(
                "search_procurements",
                {
                    "keywords": "システム 保守",
                    "notice_types": ["一般競争入札の入札公告（WTO対象）", "公募型プロポーザル情報", "落札者等の公示（随意契約）"],
                    "category": "物品・役務",
                    "agencies": ["総務省", "デジタル庁"],
                    "agency_prefectures": ["東京都", "大阪府", "北海道"],
                    "item_classifications": ["027.コンピュータ・サービス"],
                    "public_start_from": "2026-04-01",
                    "procurement_item_no": "605030",
                    "limit": 5,
                },
            )
        )
        last = structured(
            await client.call_tool("search_procurements", {"keywords": "システム", "offset": 5, "limit": 5})
        )
    assert first["total_count"] == 7 and len(first["items"]) == 5 and first["next_offset"] == 5
    assert first["capped_at_500"] is False
    assert first["items"][0]["notices"][0]["notice_id"] == "600000"
    assert len(last["items"]) == 2 and last["next_offset"] is None
    criteria, sort_field, sort_order, offset, limit = fake.searches[0]
    assert criteria["searchConditionBean.articleNm"] == ["システム 保守"]
    assert criteria["searchConditionBean.synonymClassification"] == ["01"]
    assert criteria["searchConditionBean.cla"] == ["02"]
    assert criteria["searchConditionBean.procurementClaBean.procurementImplementNotice"] == ["05", "13"]
    assert criteria["searchConditionBean.procurementClaBean.successfulBidNotice"] == ["16"]
    assert criteria["searchConditionBean.govementProcurementOraganBean.procurementOrgNm"] == ["012", "027"]
    assert criteria["searchConditionBean.govementProcurementOraganBean.prefecture_3"] == ["13"]
    assert criteria["searchConditionBean.govementProcurementOraganBean.prefecture_5"] == ["27"]
    assert criteria["searchConditionBean.govementProcurementOraganBean.prefecture_1"] == ["01"]
    assert criteria["searchConditionBean.itemClassifcationBean.itemClassifcation"] == ["027"]
    assert criteria["searchConditionBean.publicStartDateFrom"] == ["2026/04/01"]
    assert criteria["searchConditionBean.procurementItemNo"] == ["605030"]
    assert (sort_field, sort_order, offset, limit) == ("implement_notice_date", "desc", 0, 5)


async def test_search_rejects_bad_dates_and_multi_word_synonym_search_before_calling_the_portal(fake):
    async with Client(server.mcp) as client:
        bad_date = await client.call_tool("search_procurements", {"public_start_from": "2026/04/01"})
        synonyms = await client.call_tool(
            "search_procurements", {"keywords": "システム 保守", "use_synonyms": True}
        )
        bad_enum = await client.call_tool("search_procurements", {"agencies": ["港区"]})
    assert bad_date.is_error and "YYYY-MM-DD" in bad_date.content[0].text
    assert synonyms.is_error and "single term" in synonyms.content[0].text
    assert bad_enum.is_error
    assert fake.searches == []


async def test_search_passes_the_portal_error_through(fake):
    fake.fail_with = "調達ポータルが検索条件を受け付けませんでした: 公開開始日(自)は…"
    async with Client(server.mcp) as client:
        result = await client.call_tool("search_procurements", {"keywords": "x"})
    assert result.is_error and "公開開始日" in result.content[0].text


async def test_detail_returns_the_notice_and_explains_a_missing_id(fake):
    async with Client(server.mcp) as client:
        found = structured(await client.call_tool("get_procurement_notice", {"notice_id": "600001"}))
        missing = await client.call_tool("get_procurement_notice", {"notice_id": "1"})
        bad = await client.call_tool("get_procurement_notice", {"notice_id": "abc"})
    assert found["portal_url"].endswith("procurementItemInfoId=600001")
    assert missing.is_error and "600001" not in missing.content[0].text
    assert bad.is_error and fake.searches == []


async def test_award_records_pick_the_file_and_filter(fake_opendata):
    async with Client(server.mcp) as client:
        month = structured(
            await client.call_tool("search_award_records", {"month": "2026-10", "keyword": "システム 三菱"})
        )
        day = structured(
            await client.call_tool(
                "search_award_records",
                {"date": "2026-10-02", "ministry": "国土交通省", "bidding_method": "随意契約方式・特定業者"},
            )
        )
        corp = structured(
            await client.call_tool("search_award_records", {"month": "2026-10", "corporation_no": "9010401028746"})
        )
        default = structured(await client.call_tool("search_award_records", {}))
        both = await client.call_tool("search_award_records", {"month": "2026-10", "date": "2026-10-02"})
        bad = await client.call_tool("search_award_records", {"month": "2026-13"})
    assert fake_opendata.filenames[:2] == [
        "successful_bid_record_info_all_202610.json",
        "successful_bid_record_info_diff_20261002.json",
    ]
    assert month["source_file"] == "successful_bid_record_info_all_202610.json"
    assert month["total_count"] == 1 and month["records"][0]["price_yen"] == 168500000
    assert month["records"][0]["ministry"] == "総務省"
    assert month["records"][0]["bidding_method"] == "一般競争入札・総合評価"
    assert day["total_count"] == 1 and day["records"][0]["price_yen"] == 1234567.5
    assert day["records"][0]["corporation_no"] is None
    assert corp["total_count"] == 1
    assert default["total_count"] == 2 and default["source_file"].startswith("successful_bid_record_info_all_")
    assert both.is_error and bad.is_error
