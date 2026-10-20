"""The HTML parsers against markup captured from the portal."""

import pytest
from fixtures import (
    CAPPED_PAGE,
    DETAIL_PAGE,
    FORM_PAGE,
    NO_HIT_PAGE,
    RESULT_PAGE,
    VALIDATION_ERROR_PAGE,
)

from procure_info_disclosure_mcp_server.portal import (
    PortalError,
    alerts,
    csrf_token,
    form_defaults,
    parse_detail_page,
    parse_result_rows,
    result_count,
)
from procure_info_disclosure_mcp_server.text import (
    html_to_text,
    iso_to_portal_date,
    wareki_to_iso,
)


def test_form_defaults_take_checked_and_hidden_fields_only():
    fields = form_defaults(FORM_PAGE)
    assert fields["_csrf"] == ["7c68b3a0-e69d-43c5-8620-29141b80a1f9"]
    assert fields["searchConditionBean.cla"] == ["01"]
    assert fields["searchConditionBean.synonymClassification"] == ["01"]
    assert fields["searchConditionBean.articleNm"] == [""]
    assert fields["_searchConditionBean.itemClassifcationBean.itemClassifcation"] == ["on", "on"]
    assert "searchConditionBean.procurementClaBean.procurementImplementNotice" not in fields
    assert "searchConditionBean.caseDivision" not in fields  # disabled
    assert "OAA0102" not in fields
    assert csrf_token(FORM_PAGE) == "7c68b3a0-e69d-43c5-8620-29141b80a1f9"


def test_result_rows_carry_every_notice_with_its_stage_and_date():
    rows = parse_result_rows(RESULT_PAGE)
    assert [row["procurement_item_no"] for row in rows] == [
        "0000000000000331517",
        "0000000000000541596",
    ]
    first = rows[0]
    assert first["title"].startswith("恩給事務総合システム")
    assert first["agency"] == "総務省" and first["prefecture"] == "東京都"
    assert first["notices"] == [
        {
            "stage": "意見招請",
            "kind": "公示本文",
            "notice_id": "375436",
            "date": "2022-07-29",
            "status": "公開終了",
            "ended": True,
        },
        {
            "stage": "調達実施案件公示",
            "kind": "公示本文",
            "notice_id": "388707",
            "date": "2022-10-28",
            "status": "公開開始",
            "ended": False,
        },
    ]
    second = rows[1]
    assert second["title"] == "07-0049-0199 ICTスタートアップ & エコシステム調査の請負"
    assert [(n["stage"], n["kind"], n["notice_id"]) for n in second["notices"]] == [
        ("調達実施案件公示", "公示本文", "476954"),
        ("調達実施案件公示", "訂正公告", "482666"),
        ("落札公示", "公示本文", "500687"),
    ]


def test_result_count_and_cap_notice():
    assert result_count(RESULT_PAGE) == (2, False)
    assert result_count(CAPPED_PAGE) == (500, True)


def test_alerts_distinguish_no_hit_from_validation_errors():
    errors, infos = alerts(NO_HIT_PAGE)
    assert len(errors) == 1 and "合致する調達案件情報がありません" in errors[0] and infos == []
    errors, _ = alerts(VALIDATION_ERROR_PAGE)
    assert errors == ["公開開始日(自)は存在する日付をYYYY/MM/DDの形式で入力してください。"]
    assert alerts(RESULT_PAGE) == ([], [])


def test_detail_page_fields_dates_text_and_documents():
    detail = parse_detail_page(DETAIL_PAGE)
    assert detail["procurement_item_no"] == "0000000000000289982"
    assert detail["notice_type"] == "一般競争入札の入札公告（WTO対象外）"
    assert detail["category"] == "物品・役務"
    assert detail["public_start"] == "2021-11-24" and detail["public_end"] == "2026-11-23"
    assert detail["agency"] == "総務省" and detail["agency_location"] == "東京都"
    assert detail["notice_text"].startswith("　　　　　入　札　公　告\n\n下記のとおり")
    assert "恩給事務総合システム & 移行" in detail["notice_text"]
    assert detail["documents"] == [
        {
            "name": "調達資料１ダウンロードURL",
            "url": "https://www.geps.go.jp/biz-contract/UKB06/OKB06_M01_B01.do?PRM=zCMIdca6Bd1s%3D",
        }
    ]


def test_form_defaults_fail_loudly_without_the_form():
    with pytest.raises(PortalError):
        form_defaults("<html></html>")


def test_text_helpers():
    assert wareki_to_iso("令和03年11月24日公開開始") == "2021-11-24"
    assert wareki_to_iso("平成31年4月1日") == "2019-04-01"
    assert wareki_to_iso("令和６年１月１５日") == "2024-01-15"
    assert wareki_to_iso("-") is None
    assert iso_to_portal_date("2026-10-01") == "2026/10/01"
    with pytest.raises(ValueError):
        iso_to_portal_date("2026/10/01")
    assert html_to_text("a<br />b<br /><br /><br />c &amp; d") == "a\nb\n\nc & d"
