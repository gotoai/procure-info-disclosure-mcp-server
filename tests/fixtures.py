"""HTML fixtures modelled on the portal's real markup (captured 2026-10-20)."""

FORM_PAGE = """
<html><body>
<form id="tri_WAA0101FM01" novalidate="true" action="/pps-web-biz/UAA01/OAA0100" method="post">
<input id="searchConditionBean.caseDivision1" name="searchConditionBean.caseDivision" disabled="disabled" type="radio" value="0" checked="checked"/>
<input id="procurementCla" name="searchConditionBean.procurementCla" type="hidden" value=""/>
<input id="searchConditionBean.cla1" name="searchConditionBean.cla" type="radio" value="01" checked="checked"/>
<input id="searchConditionBean.cla2" name="searchConditionBean.cla" type="radio" value="02"/>
<input id="start-date-from" name="searchConditionBean.publicStartDateFrom" type="text" class="date" value="" maxlength="10"/>
<input id="searchConditionBean.synonymClassification1" name="searchConditionBean.synonymClassification" type="radio" value="01" checked="checked"/>
<input id="case-name" name="searchConditionBean.articleNm" type="text" value="" maxlength="254"/>
<input id="x1" name="searchConditionBean.procurementClaBean.procurementImplementNotice" type="checkbox" value="05"/>
<input type="hidden" name="_searchConditionBean.procurementClaBean.procurementImplementNotice" value="on"/>
<input type="hidden" name="_searchConditionBean.itemClassifcationBean.itemClassifcation" value="on"/>
<input type="hidden" name="_searchConditionBean.itemClassifcationBean.itemClassifcation" value="on"/>
<input class="button-orange" id="OAA0102" name="OAA0102" type="submit" value="検索" />
<input type="hidden" name="_csrf" value="7c68b3a0-e69d-43c5-8620-29141b80a1f9" />
</form>
<form id="emptyForm" action="/pps-web-biz/UAA01/OAA0101" method="post">
<input type="hidden" name="_csrf" value="7c68b3a0-e69d-43c5-8620-29141b80a1f9" />
</form>
</body></html>
"""

_ROW_TEMPLATE = """
<tr class="highlight">
    <td id="tri_WAA0101FM01/procurementResultListBean/procurementItemNo">{no}</td>
    <td class="replace" id="tri_WAA0101FM01/procurementResultListBean/articleNm">{title}</td>
    <td id="tri_WAA0101FM01/procurementResultListBean/procurementOrgan">{agency}</td>
    <td id="tri_WAA0101FM01/procurementResultListBean/receiptAddress">{pref}</td>
    <td id="tri_WAA0101FM01/procurementResultListBean/requestSubmissionMaterialsBean">
    </td>
    <td id="tri_WAA0101FM01/procurementResultListBean/requestCommentBean">
        {comment}
    </td>
    <td id="tri_WAA0101FM01/procurementResultListBean/procurementImplementNoticeBean">
        {implement}
    </td>
    <td id="tri_WAA0101FM01/procurementResultListBean/successfulBidNoticeBean">
        {award}
    </td>
</tr>
"""

_NOTICE = """<table><tbody>
    <pre></pre>
    <a class="{cls} info-button" tabindex="4107"
        href="javascript:doSubmitParams(this, [{{name:'procurementItemInfoId', value:'{id}'}},{{name:'SyFromFlg', value:1}}],'/pps-web-biz/UAA01/OAA0104')">{label}</a>
    <br>
    {date}
</tbody></table>"""

_BID_BUTTON = """<table><tbody>
    <pre></pre>
    <a class="info-button keiyaku" onclick="javascript:window.open('https://www.nyusatsu.geps.go.jp/OMP/Accepter/index.jsp?PRM=0000000000000331517','n','w');" target="_blank">入札</a>
</tbody></table>"""


def notice(cls, id_, label, date):
    return _NOTICE.format(cls=cls, id=id_, label=label, date=date)


ROW_1 = _ROW_TEMPLATE.format(
    no="0000000000000331517",
    title="恩給事務総合システムのガバメントクラウドへの移行に係る作業の請負",
    agency="総務省",
    pref="東京都",
    comment=notice("torikesi-end", "375436", "公示本文", "令和04年07月29日公開終了"),
    implement=notice("koukoku", "388707", "公示本文", "令和04年10月28日公開開始") + _BID_BUTTON,
    award="",
)
ROW_2 = _ROW_TEMPLATE.format(
    no="0000000000000541596",
    title="07-0049-0199 ICTスタートアップ &amp; エコシステム調査の請負",
    agency="総務省",
    pref="東京都",
    comment="",
    implement=notice("koukoku", "476954", "公示本文", "令和07年08月08日公開開始")
    + notice("teisei", "482666", "訂正公告", "令和08年08月22日公開終了"),
    award=notice("koukoku", "500687", "公示本文", "令和08年03月01日公開開始"),
)


def result_page(rows: str, count: int, alerts: str = "") -> str:
    return f"""
<html><body>
<form id="tri_WAA0101FM01" novalidate="true" action="/pps-web-biz/UAA01/OAA0100" method="post">
{alerts}
<div class="alert message-error input-error-list" ></div>
<input type="hidden" name="_csrf" value="c57a878d-b880-4598-a76c-2e62774f3458" />
<h3 class="search-result table-title">検索結果</h3>
<p class="result-number">
<strong>{count}</strong>件見つかりました。
</p>
<select id="sortConditionBean.koumokuName" name="sortConditionBean.koumokuName"></select>
<table class="main-summit-info">
<thead><tr><th id="tri_WAA0101FM01/procurementResultListBean/procurementItemNo_th">調達案件番号</th></tr></thead>
<tbody>
{rows}
</tbody>
</table>
</form>
</body></html>
"""


RESULT_PAGE = result_page(ROW_1 + ROW_2, 2)
CAPPED_PAGE = result_page(
    ROW_1,
    500,
    '<div class="alert message-info"><ul><li>検索結果が500件を超えたため、先頭の500件を表示します。</li></ul></div>',
)
NO_HIT_PAGE = """
<html><body>
<form id="tri_WAA0101FM01" action="/pps-web-biz/UAA01/OAA0100" method="post">
<div class="alert message-error input-error-list" ><ul><li>指定された検索条件に合致する調達案件情報がありません。検索条件を見直し、再度検索してください。</li></ul></div>
<input type="hidden" name="_csrf" value="x" />
</form>
</body></html>
"""
VALIDATION_ERROR_PAGE = """
<html><body>
<form id="tri_WAA0101FM01" action="/pps-web-biz/UAA01/OAA0100" method="post">
<div class="alert message-error input-error-list" ><ul><li>公開開始日(自)は存在する日付をYYYY/MM/DDの形式で入力してください。</li></ul></div>
<input type="hidden" name="_csrf" value="x" />
</form>
</body></html>
"""

DETAIL_PAGE = """
<html><body>
<form id="tri_WAB0102FM01" action="/pps-web-biz/UAA01/OAA0100" method="post">
<table>
<tr>
<th>調達案件番号</th>
<td colspan="5">0000000000000289982</td>
</tr>
<tr id="tri_WAB0102FM01/procurementInformationDetailBean/procurementCla">
<th>調達種別</th>
<td colspan="5">一般競争入札の入札公告（WTO対象外）</td>
</tr>
<tr id="tri_WAB0102FM01/procurementInformationDetailBean/cla">
<th>分類</th>
<td colspan="5">物品・役務</td>
</tr>
<tr id="tri_WAB0102FM01/procurementInformationDetailBean/articleNm">
<th>調達案件名称</th>
<td colspan="5">恩給事務総合システムの移行要件定義等作成作業の請負</td>
</tr>
<tr class="info-date" id="tri_WAB0102FM01/procurementInformationDetailBean/publicStartDate">
<th>公開開始日</th>
<td>
 令和03年11月24日
</td>
<th>公開終了日</th>
<td> 令和08年11月23日</td>
</tr>
<tr id="tri_WAB0102FM01/procurementInformationDetailBean/procurementOragan">
<th>調達機関</th>
<td colspan="5">総務省</td>
</tr>
<tr id="tri_WAB0102FM01/procurementInformationDetailBean/procurementOraganLocation">
<th>調達機関所在地</th>
<td colspan="5">東京都</td>
</tr>
<tr id="tri_WAB0102FM01/procurementInformationDetailBean/publicNoticeContent">
<th>公告内容</th>
<td colspan="5">　　　　　入　札　公　告<br /><br />下記のとおり一般競争入札に付します。<br />１　契約担当官等の官職及び氏名<br />(1) 件　名　恩給事務総合システム &amp; 移行<br /></td>
</tr>
<tr id="tri_WAB0102FM01/procurementInformationDetailBean/procurementDocumentDownloadUrl1">
<th>調達資料１</th>
<td colspan="5">
<a class="text-link" tabindex="1000" href="https://www.geps.go.jp/biz-contract/UKB06/OKB06_M01_B01.do?PRM=zCMIdca6Bd1s%3D" target="_blank">調達資料１ダウンロードURL</a>
</td>
</tr>
<tr id="tri_WAB0102FM01/procurementInformationDetailBean/procurementDocumentDownloadUrl2">
<th>調達資料２</th>
<td colspan="5">
-
</td>
</tr>
</table>
<input type="hidden" name="_csrf" value="d0949b22" />
</form>
</body></html>
"""

NOT_FOUND_PAGE = """
<html><body><form id="tri_WAB0102FM01"><p>該当する調達案件情報が存在しません。</p>
<tr><th>調達案件番号</th><td>-</td></tr>
</form></body></html>
"""
