"""The guideline `load_guideline` returns: how the tools work together, and the
conditions of use. It is the one place for everything that is not specific to a
single tool, per Kari's skill-style MCP contract."""

from __future__ import annotations

SECTIONS: dict[str, str] = {
    "search": """\
## 検索の進め方（search_procurements）

- 調達ポータル（https://www.p-portal.go.jp/）に公開中の、国の機関の調達情報を検索します。
  keywords は調達案件名称の部分一致です。スペース区切りで複数語を指定すると、すべての語を
  含む案件に絞られます（AND）。use_synonyms=true にすると類義語や全角・半角の違いも拾いますが、
  語は1つしか指定できません。
- 広い語で始めて絞り込みます。目安：「システム」「保守」「調査」「業務」「工事」など。
  0件なら別の語を試し、500件を超えたら（capped_at_500=true）語を足すか、公開開始日
  （public_start_from）や調達機関（agencies）、調達種別（notice_types）で絞ってください。
- 入札に参加できる案件を探すときは notice_types に「一般競争入札の入札公告（WTO対象）」
  「一般競争入札の入札公告（WTO対象外）」「公募型プロポーザル情報」「オープンカウンタへの
  参加募集情報」などを指定します。落札結果を知りたいときは「落札者等の公示（WTO対象）」
  「落札者等の公示（WTO対象外）」「落札者等の公示（随意契約）」です。
- 既定の並びは調達実施案件公示の公開開始日の降順（新しい順）です。古い案件は公開期間が
  続く限り結果に出るので、直近の案件だけ見たいときは public_start_from を指定してください。
- 1件の調達案件（procurement_item_no）には、資料提供招請→意見招請→調達実施案件公示→落札公示
  という段階ごとの公示と、訂正公告・取消公告がぶら下がります。notices の各要素が1つの
  公示で、それぞれ notice_id を持ちます。date は公開開始日または公開終了日（status）です。
- 結果は既定で20件ずつです。total_count と next_offset を見て、必要なら offset で続きを
  取得してください。1回の検索で取得できるのは最大500件です。""",
    "detail": """\
## 公示の内容（get_procurement_notice）

- 候補が絞れたら、調達実施案件公示などの notice_id で get_procurement_notice を呼び、
  公告内容（notice_text）を読みます。入札書の提出期限、開札日、参加資格（統一資格の等級・
  地域）、問い合わせ先、電子調達の可否はここに書かれています。
- documents は入札説明書・仕様書などの調達資料で、政府電子調達（GEPS）のダウンロード
  ページへのURLです。このツールでは中身を読めないので、利用者にURLを案内してください。
- 回答には必ず portal_url（調達ポータルの公式ページ）を添えてください。URLを自分で
  組み立てないでください。""",
    "awards": """\
## 落札実績（search_award_records）

- 調達ポータルの落札実績オープンデータから、落札日が month（YYYY-MM）または date
  （YYYY-MM-DD）に当たる落札結果を返します。月別は2019年4月以降、日別は直近約2か月分です。
  どちらも省略すると当月分です。当月分は日々追加されます。
- keyword は案件名と落札事業者名の部分一致（スペース区切りでAND）、ministry は府省名、
  bidding_method は入札方式、corporation_no は法人番号（13桁、完全一致）で絞れます。
- price_yen は落札価格（円）です。オープンカウンタ（少額）のうち個人事業主の落札は
  含まれません。
- 落札公示（search_procurements の「落札者等の公示」）は公示文そのもの、落札実績オープン
  データは構造化された一覧です。事業者別・府省別の集計や金額の確認には後者が向きます。""",
    "coverage": """\
## 収録範囲

- 調達ポータルに載るのは、府省庁・国会・裁判所など国の機関の物品・役務の調達と、一部の
  簡易な公共事業です。本格的な公共工事（地方整備局の工事など）、独立行政法人や地方公共
  団体の多くの入札は載っていません。
- 見つからないときは、調達ポータルに無いことを伝え、発注機関の公式サイトや官公需情報
  ポータルサイト（https://www.kkj.go.jp/）で確認するよう案内してください。""",
    "terms": """\
## 利用条件（必ず守ってください）

- 出典表示：取得した情報を回答・公開するときは「出典：調達ポータル（https://www.p-portal.go.jp/）」
  と明記します。要約や集計など加工した情報には、加工したことも書き添えてください。
- 情報の扱い：内容は参考情報です。入札に参加する前に、公式ページ（portal_url）で最新の
  公告と調達資料を確認するよう利用者に伝えてください。
- アクセス：同じ検索を短時間に繰り返す、全件を機械的に取得するなど、調達ポータルへの
  過度な連続アクセスは避けてください。
- 本サーバーはデジタル庁とは関係のない非公式のツールです。""",
}

HEADER = "# 調達ポータル ツールの使い方\n"

# Always served whole: an agent that read one section would miss the conditions of use.
GUIDELINE = HEADER + "\n\n".join(SECTIONS.values())
