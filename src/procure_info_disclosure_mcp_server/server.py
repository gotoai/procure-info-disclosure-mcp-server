"""A skill-style MCP server for 調達ポータル's public procurement information.

Built to Kari's skill-style MCP contract
(kari/docs/design_skill-style-mcp-server.md in the Kari repo): a one-sentence
`instructions`, a `load_guideline` tool carrying everything that concerns the
tool set as a whole — conditions of use included — and tool-specific
descriptions on the other tools.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
from importlib.metadata import version
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp_types import ToolAnnotations
from pydantic import Field

from .codes import (
    AGENCIES,
    BIDDING_METHOD_CODES,
    CATEGORIES,
    ITEM_CLASSIFICATIONS,
    MINISTRY_CODES,
    NOTICE_TYPES,
    PREFECTURES,
    Agency,
    BiddingMethod,
    Category,
    ItemClassification,
    Ministry,
    NoticeType,
    Prefecture,
    SortField,
    SortOrder,
)
from .guideline import GUIDELINE
from .opendata import OpenDataClient, OpenDataError, daily_filename, monthly_filename
from .portal import RESULT_CAP, PortalClient, PortalError
from .text import iso_to_portal_date, normalize_for_match

SERVER_NAME = "procure-info-disclosure"

INSTRUCTIONS = (
    "調達ポータル（政府電子調達）で国の機関の入札公告・調達情報を検索・閲覧し、落札実績"
    "オープンデータを取得するツール群です。官公庁の入札や落札を調べるときに使い、最初に "
    "load_guideline を呼んでください。"
)

DEFAULT_LIMIT = 20
MAX_LIMIT = 100
JST = dt.timezone(dt.timedelta(hours=9))

_MONTH = re.compile(r"^(\d{4})-(\d{2})$")
_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")

mcp = MCPServer(
    SERVER_NAME,
    title="調達ポータル調達情報検索",
    description=(
        "Unofficial MCP server for 調達ポータル, Japan's government procurement portal. "
        "Not affiliated with the Digital Agency."
    ),
    version=version("procure-info-disclosure-mcp-server"),
    instructions=INSTRUCTIONS,
)

_portal = PortalClient()
_opendata = OpenDataClient()

_READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=True)


@mcp.tool(
    description=(
        "Usage guideline for the 調達ポータル tools: how to search notices, read a notice, "
        "use the award open data, what the portal covers, and the conditions of use. "
        "Read it before your first search."
    ),
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False),
)
async def load_guideline() -> str:
    return GUIDELINE


@mcp.tool(
    description=(
        "Search procurement notices published on 調達ポータル by national agencies: tender "
        "announcements, RFIs, RFCs, proposal calls, open counters and award notices. Returns one "
        "page of procurement items, each with its notices (notice_id, date, status); total_count "
        "and next_offset tell whether more pages exist. The portal caps one search at 500 items."
    ),
    annotations=_READ_ONLY,
)
async def search_procurements(
    keywords: Annotated[
        str | None,
        Field(
            description=(
                "Terms the procurement title must contain, separated by spaces (all must match). "
                "With use_synonyms, exactly one term."
            ),
            max_length=254,
        ),
    ] = None,
    use_synonyms: Annotated[
        bool, Field(description="Match synonyms and width/case variants of a single keyword.")
    ] = False,
    notice_types: Annotated[
        list[NoticeType] | None, Field(description="Notice types to include, any of.")
    ] = None,
    category: Annotated[Category, Field(description="Goods and services, or simple public works.")] = "全て",
    agencies: Annotated[list[Agency] | None, Field(description="Procuring agencies, any of.")] = None,
    agency_prefectures: Annotated[
        list[Prefecture] | None, Field(description="Prefectures of the procuring office, any of.")
    ] = None,
    item_classifications: Annotated[
        list[ItemClassification] | None, Field(description="Item classifications, any of.")
    ] = None,
    public_start_from: Annotated[
        str | None, Field(description="Earliest publication start date, YYYY-MM-DD.")
    ] = None,
    public_start_to: Annotated[
        str | None, Field(description="Latest publication start date, YYYY-MM-DD.")
    ] = None,
    public_end_from: Annotated[
        str | None, Field(description="Earliest publication end date, YYYY-MM-DD.")
    ] = None,
    public_end_to: Annotated[
        str | None, Field(description="Latest publication end date, YYYY-MM-DD.")
    ] = None,
    procurement_item_no: Annotated[
        str | None,
        Field(description="Procurement item number, partial match; leading zeros may be omitted.", max_length=19),
    ] = None,
    sort_by: Annotated[SortField, Field(description="Sort key.")] = "implement_notice_date",
    order: SortOrder = "desc",
    limit: Annotated[int, Field(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    offset: Annotated[int, Field(ge=0, lt=RESULT_CAP)] = 0,
) -> dict[str, Any]:
    criteria: dict[str, list[str]] = {}
    if keywords is not None:
        keywords = keywords.strip()
    if keywords:
        if use_synonyms and any(c.isspace() for c in keywords):
            raise ToolError("With use_synonyms=true, keywords must be a single term without spaces.")
        criteria["searchConditionBean.articleNm"] = [keywords]
    criteria["searchConditionBean.synonymClassification"] = ["02" if use_synonyms else "01"]
    criteria["searchConditionBean.cla"] = [CATEGORIES[category]]
    for notice_type in notice_types or []:
        field, code = NOTICE_TYPES[notice_type]
        criteria.setdefault(f"searchConditionBean.procurementClaBean.{field}", []).append(code)
    if agencies:
        criteria["searchConditionBean.govementProcurementOraganBean.procurementOrgNm"] = [
            AGENCIES[name] for name in agencies
        ]
    for prefecture in agency_prefectures or []:
        area, code = PREFECTURES[prefecture]
        criteria.setdefault(
            f"searchConditionBean.govementProcurementOraganBean.prefecture_{area}", []
        ).append(code)
    if item_classifications:
        criteria["searchConditionBean.itemClassifcationBean.itemClassifcation"] = [
            ITEM_CLASSIFICATIONS[label] for label in item_classifications
        ]
    for argument, field, value in (
        ("public_start_from", "publicStartDateFrom", public_start_from),
        ("public_start_to", "publicStartDateTo", public_start_to),
        ("public_end_from", "publicEndDateFrom", public_end_from),
        ("public_end_to", "publicEndDateTo", public_end_to),
    ):
        if value:
            try:
                criteria[f"searchConditionBean.{field}"] = [iso_to_portal_date(value)]
            except ValueError as error:
                raise ToolError(f"{argument}: {error}") from error
    if procurement_item_no:
        if not procurement_item_no.strip().isdigit():
            raise ToolError("procurement_item_no must be digits only.")
        criteria["searchConditionBean.procurementItemNo"] = [procurement_item_no.strip()]

    try:
        found = await _portal.search(criteria, sort_by, order, offset, limit)
    except PortalError as error:
        raise ToolError(str(error)) from error

    total = found["total_count"]
    next_offset = offset + limit if offset + limit < total else None
    return {
        "total_count": total,
        "capped_at_500": found["capped"],
        "offset": offset,
        "next_offset": next_offset,
        "items": found["rows"],
    }


@mcp.tool(
    description=(
        "Get one notice from 調達ポータル by notice_id (from search_procurements): procurement "
        "number, notice type, title, publication dates, agency, the full notice text (公告内容), "
        "procurement document URLs and portal_url."
    ),
    annotations=_READ_ONLY,
)
async def get_procurement_notice(
    notice_id: Annotated[str, Field(description="The notice_id from search_procurements.", max_length=12)],
) -> dict[str, Any]:
    notice_id = notice_id.strip()
    if not notice_id.isdigit():
        raise ToolError("notice_id must be the numeric id from search_procurements.")
    try:
        return await _portal.detail(notice_id)
    except PortalError as error:
        raise ToolError(str(error)) from error


@mcp.tool(
    description=(
        "List successful-bid records (落札実績) from 調達ポータル's open data for one month "
        "(YYYY-MM, from 2019-04) or one day (YYYY-MM-DD, last ~2 months), optionally filtered by "
        "keyword, ministry, bidding method or corporation number. Paged; total_count and "
        "next_offset tell whether more exist."
    ),
    annotations=_READ_ONLY,
)
async def search_award_records(
    month: Annotated[str | None, Field(description="Award month, YYYY-MM. Default: this month.")] = None,
    date: Annotated[str | None, Field(description="Award date, YYYY-MM-DD; instead of month.")] = None,
    keyword: Annotated[
        str | None,
        Field(description="Terms the title or company name must contain, space-separated (all must match)."),
    ] = None,
    ministry: Annotated[Ministry | None, Field(description="Procuring ministry or agency.")] = None,
    bidding_method: Annotated[BiddingMethod | None, Field(description="Bidding/contract method.")] = None,
    corporation_no: Annotated[
        str | None, Field(description="13-digit corporate number, exact match.", max_length=13)
    ] = None,
    limit: Annotated[int, Field(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    offset: Annotated[int, Field(ge=0)] = 0,
) -> dict[str, Any]:
    if month and date:
        raise ToolError("Give either month or date, not both.")
    if date:
        match = _DATE.match(date.strip())
        if not match:
            raise ToolError("date must be YYYY-MM-DD.")
        filename = daily_filename(*(int(part) for part in match.groups()))
    else:
        if month:
            match = _MONTH.match(month.strip())
            if not match:
                raise ToolError("month must be YYYY-MM.")
            year, month_number = (int(part) for part in match.groups())
        else:
            today = dt.datetime.now(JST).date()
            year, month_number = today.year, today.month
        if not 1 <= month_number <= 12:
            raise ToolError("month must be YYYY-MM.")
        filename = monthly_filename(year, month_number)

    try:
        records = await _opendata.records(filename)
    except OpenDataError as error:
        raise ToolError(str(error)) from error

    terms = [normalize_for_match(term) for term in (keyword or "").split()]
    ministry_code = MINISTRY_CODES[ministry] if ministry else None
    method_code = BIDDING_METHOD_CODES[bidding_method] if bidding_method else None
    corporation = corporation_no.strip() if corporation_no else None
    matched = [
        record
        for record in records
        if (ministry_code is None or record["ministry_code"] == ministry_code)
        and (method_code is None or record["bidding_method_code"] == method_code)
        and (corporation is None or record["corporation_no"] == corporation)
        and all(
            term in normalize_for_match(f"{record['title'] or ''} {record['company'] or ''}")
            for term in terms
        )
    ]
    page = matched[offset : offset + limit]
    return {
        "source_file": filename,
        "total_count": len(matched),
        "offset": offset,
        "next_offset": offset + limit if offset + limit < len(matched) else None,
        "records": page,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="調達ポータル skill-style MCP server")
    parser.add_argument("--transport", choices=["streamable-http", "stdio"], default="streamable-http")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--allowed-host",
        action="append",
        default=[],
        metavar="HOST[:PORT]",
        help="Host header to accept, e.g. demo.mcp.gotoai.com behind a reverse proxy. Repeatable.",
    )
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run("stdio")
        return

    security = None
    if args.allowed_host:
        security = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=args.allowed_host,
            allowed_origins=[],
        )
    mcp.run(
        "streamable-http",
        host=args.host,
        port=args.port,
        transport_security=security,
    )


if __name__ == "__main__":
    main()
