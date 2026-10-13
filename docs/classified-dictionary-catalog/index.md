# 分類辞書の収録一覧

28カテゴリ、全体で **733,494組**、カテゴリ別に **767,274レコード**を収録しています。

「組」は読み・表記の重複を除いた件数、「レコード」は品詞・コストの違いも保持したバイナリへの収録件数です。複数カテゴリへの所属があるため、カテゴリ別の組数の合計は全体の組数と一致しません。

一覧は配布対象の固定データから全件生成しています。Geminiとassistantの暫定分類・未確認の読みを含みます。コストと品詞は元辞書の値です。分類取得失敗・未分類・除外候補はこの一覧には含めません。

[品詞IDと品詞名](pos.md) · [生成・配布手順](../classified-dictionary-distribution.md)

| カテゴリ | 読み・表記の組 | 読み数 | レコード数 |
|---|---:|---:|---:|
| [人物・人名](person/index.md) | 270,397 | 201,075 | 276,536 |
| [架空キャラクター](character/index.md) | 8,801 | 8,652 | 8,870 |
| [神話・伝承の存在](mythological_figure/index.md) | 3,629 | 3,447 | 3,629 |
| [地名](place/index.md) | 78,941 | 76,456 | 85,399 |
| [住所](address/index.md) | 121,789 | 121,672 | 122,248 |
| [駅・停留所](station/index.md) | 6,816 | 6,732 | 6,816 |
| [施設](facility/index.md) | 28,668 | 27,191 | 28,669 |
| [交通路線](transport_route/index.md) | 3,211 | 3,182 | 3,211 |
| [組織](organization/index.md) | 47,117 | 46,163 | 47,185 |
| [家系・氏族](lineage/index.md) | 2,986 | 2,940 | 2,986 |
| [商品・サービス](product/index.md) | 13,626 | 13,389 | 13,629 |
| [車両・船舶](vehicle/index.md) | 3,403 | 3,376 | 3,403 |
| [イベント・事件](event/index.md) | 9,953 | 9,832 | 9,955 |
| [賞](award/index.md) | 1,004 | 988 | 1,004 |
| [条約・協定](agreement/index.md) | 1,744 | 1,734 | 1,744 |
| [事業・キャンペーン](initiative/index.md) | 1,540 | 1,528 | 1,540 |
| [一般語・専門用語](term/index.md) | 127,736 | 123,071 | 127,770 |
| [作品シリーズ](work_franchise/index.md) | 270 | 267 | 270 |
| [漫画作品](work_manga/index.md) | 1,003 | 987 | 1,003 |
| [アニメ作品](work_anime/index.md) | 642 | 628 | 642 |
| [映画作品](work_film/index.md) | 1,179 | 1,170 | 1,180 |
| [番組](work_program/index.md) | 2,380 | 2,341 | 2,381 |
| [書籍作品](work_book/index.md) | 5,352 | 5,307 | 5,353 |
| [ゲーム作品](work_game/index.md) | 1,506 | 1,450 | 1,506 |
| [音楽作品](work_music/index.md) | 3,785 | 3,726 | 3,789 |
| [舞台作品](work_stage/index.md) | 354 | 352 | 354 |
| [定期刊行物](work_periodical/index.md) | 1,028 | 1,006 | 1,029 |
| [媒体未特定の作品・美術作品](work_other/index.md) | 5,168 | 5,141 | 5,173 |

元データSHA-256: `82e10eef85dccc9e981a841eac4d719b658b31128f4d73f8f52942eb4382e9b3`

再生成: `python3 scripts/write_classified_dictionary_catalog.py`
整合確認: `python3 scripts/write_classified_dictionary_catalog.py --check`
