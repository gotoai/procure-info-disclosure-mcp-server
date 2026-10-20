# procure-info-disclosure-mcp-server

An MCP server for the public procurement information of
[調達ポータル](https://www.p-portal.go.jp/), the Japanese government's procurement
portal: search tender and award notices of national agencies, read a notice in full,
and list successful-bid records from the portal's open data.

調達ポータルの調達情報公開機能を使って、国の機関の入札公告・調達情報の検索と公告内容の
閲覧、落札実績オープンデータの取得ができる MCP サーバーです。

> **Unofficial.** This project is not affiliated with or endorsed by the Digital Agency
> (デジタル庁), which operates 調達ポータル and 政府電子調達 (GEPS).

## What the "API" is

The e-Gov API catalog lists [調達情報等公開機能](https://api-catalog.e-gov.go.jp/info/ja/apicatalog/view/42)
(統一資格者情報 and 調達情報 as CSV/XML) and points at the former GEPS site
`chotatujoho.geps.go.jp`, whose 2015 notice offered the specification on request from
the help desk. That site has since been merged into 調達ポータル, and no machine-readable
search API is published there. This server therefore uses what the portal does publish:

- **調達情報公開機能** — the public search (`/pps-web-biz/UAA01/OAA0101`) and notice pages.
  The search is an HTML form with server-side session state; the server replays the form
  exactly as a browser would, one short-lived session per search, and parses the result
  table. A search is capped at 500 items by the portal.
- **落札実績オープンデータ** — the documented download API on `api.p-portal.go.jp`
  (操作マニュアル「調達ポータル 使い方編」5.2.2): one JSON file per month of awards
  (from April 2019) or per day of additions (about the last two months), with the fields
  of 「落札実績オープンデータ ファイル仕様」.

The portal's HTML may change without notice; the parsers are written against markup
captured on 2026-10-20 and fail loudly rather than return partial rows.

## Tools

| Tool | What it does |
|---|---|
| `load_guideline` | The usage guideline for the whole tool set: search strategy, notices, award data, what the portal covers, and the conditions of use. It takes no arguments and always returns the whole guideline. |
| `search_procurements` | Search notices by keywords (AND) and filters: notice type, category, agency, agency prefecture, item classification, publication dates, procurement number; sortable, paged, capped at 500. Each item lists its notices with a `notice_id`. |
| `get_procurement_notice` | One notice in full: procurement number, type, title, publication dates, agency, the notice body (公告内容), procurement document URLs and `portal_url`. |
| `search_award_records` | Successful-bid records for one month or one day from the open data, filtered by keyword, ministry, bidding method or corporate number; paged. |

The server follows a *skill-style* layout. Its MCP `instructions` are one sentence
saying what the tools are for and to call `load_guideline` first. Everything that
concerns the tool set as a whole — including the conditions of use — lives in the
guideline, and each tool's description covers only that tool. Agents that load many MCP
servers keep only a short entry per server in their prompt, and read the guideline when
they need it.

## Run

Python 3.11 or later.

```bash
pip install -e .
procure-info-disclosure-mcp-server --host 127.0.0.1 --port 8000   # Streamable HTTP at /mcp
procure-info-disclosure-mcp-server --transport stdio             # for clients that start it themselves
```

Behind a reverse proxy, accept the public host name as well; otherwise the server's DNS
rebinding protection rejects requests whose `Host` is not localhost:

```bash
procure-info-disclosure-mcp-server --host 127.0.0.1 --port 8000 --allowed-host demo.mcp.gotoai.com
```

When bound to a non-loopback address (for example `--host 0.0.0.0` on a LAN), that
protection is off; restrict access with a firewall or a proxy.

### In Kari

Add a custom extension of type **Streamable HTTP** with the URL `http://<host>:<port>/mcp`.
Give it an ASCII name such as `p-portal` — the name becomes part of every tool name the
agent sees.

## Conditions of use

These are in the guideline the agent reads; they apply to anyone presenting the results:

- Credit the source as 「出典：調達ポータル（https://www.p-portal.go.jp/）」, and say so
  when the information has been edited or aggregated.
- Treat the information as a reference; confirm the latest notice and documents on the
  notice's official page (`portal_url`) before taking part in a tender.
- Avoid excessive repeated access to the portal.

The portal's own terms are at
[ご利用にあたって](https://www.p-portal.go.jp/pps-web-biz/resources/app/html/sitepolicy.html)
(content reuse, in the style of the Government Standard Terms of Use) and the
[利用規約](https://www.p-portal.go.jp/pps-web-biz/resources/app/pdf/riyoukiyaku.pdf);
they apply to whoever runs this server. Each search costs the portal three or four page
requests, so keep the access pattern that of a person using the site.

## Development

```bash
pip install -e ".[dev]"
pytest                    # offline tests
PROCURE_LIVE=1 pytest     # also the live tests against the real portal and open-data API
ruff check src tests
```

## License

MIT — see [LICENSE](LICENSE).
