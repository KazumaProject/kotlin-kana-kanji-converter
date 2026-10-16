# 分類辞書の収録一覧

30カテゴリ、全体で **515,440組**、カテゴリ別に **528,787レコード**を収録しています。

「組」は読み・表記の重複を除いた件数、「レコード」は品詞・コストの違いも保持したバイナリへの収録件数です。複数カテゴリへの所属があるため、カテゴリ別の組数の合計は全体の組数と一致しません。

一覧は配布対象の固定データから全件生成しています。Geminiとassistantの暫定分類・未確認の読みを含みます。既存28カテゴリのコストと品詞は元辞書の値です。漢方・医療は提供元の読みと空欄へのGemini推定読み（未確認）を採用し、品詞とコストを本プロジェクトで設定しています。分類取得失敗・未分類・除外候補はこの一覧には含めません。

[品詞IDと品詞名](pos.md) · [生成・配布手順](../classified-dictionary-distribution.md) · [漢方・医療の出典記録](../specialist-dictionaries.md)

| カテゴリ | 読み・表記の組 | 読み数 | レコード数 |
|---|---:|---:|---:|
| [人物・人名](person/index.md) | 49,666 | 43,784 | 50,627 |
| [架空キャラクター](character/index.md) | 5,281 | 5,232 | 5,342 |
| [神話・伝承の存在](mythological_figure/index.md) | 2,686 | 2,510 | 2,687 |
| [地名](place/index.md) | 35,160 | 33,545 | 36,859 |
| [住所](address/index.md) | 147,915 | 147,445 | 152,177 |
| [駅・停留所](station/index.md) | 6,311 | 6,245 | 6,313 |
| [施設](facility/index.md) | 22,158 | 21,068 | 22,165 |
| [交通路線](transport_route/index.md) | 2,486 | 2,463 | 2,487 |
| [組織](organization/index.md) | 29,499 | 29,063 | 29,555 |
| [家系・氏族](lineage/index.md) | 1,773 | 1,739 | 1,773 |
| [商品・サービス](product/index.md) | 8,382 | 8,209 | 8,384 |
| [車両・船舶](vehicle/index.md) | 2,101 | 2,076 | 2,101 |
| [イベント・事件](event/index.md) | 6,613 | 6,533 | 6,613 |
| [賞](award/index.md) | 636 | 626 | 636 |
| [条約・協定](agreement/index.md) | 380 | 377 | 380 |
| [事業・キャンペーン](initiative/index.md) | 943 | 937 | 943 |
| [一般語・専門用語](term/index.md) | 90,500 | 87,129 | 90,522 |
| [作品シリーズ](work_franchise/index.md) | 670 | 663 | 670 |
| [漫画作品](work_manga/index.md) | 1,032 | 1,021 | 1,033 |
| [アニメ作品](work_anime/index.md) | 659 | 649 | 659 |
| [映画作品](work_film/index.md) | 1,448 | 1,439 | 1,448 |
| [番組](work_program/index.md) | 1,854 | 1,842 | 1,854 |
| [書籍作品](work_book/index.md) | 3,843 | 3,816 | 3,843 |
| [ゲーム作品](work_game/index.md) | 1,406 | 1,357 | 1,406 |
| [音楽作品](work_music/index.md) | 2,047 | 2,016 | 2,047 |
| [舞台作品](work_stage/index.md) | 397 | 391 | 397 |
| [定期刊行物](work_periodical/index.md) | 957 | 939 | 958 |
| [媒体未特定の作品・美術作品](work_other/index.md) | 1,621 | 1,613 | 1,621 |
| [漢方・生薬](kampo/index.md) | 440 | 426 | 440 |
| [医療](medical/index.md) | 92,847 | 89,629 | 92,847 |

元データSHA-256: `8dbb6ecbe57750f50539d0cf84c46c5aa88444528f98d44c79f93d56552fbb9b`

再生成: `python3 scripts/write_classified_dictionary_catalog.py`
整合確認: `python3 scripts/write_classified_dictionary_catalog.py --check`
