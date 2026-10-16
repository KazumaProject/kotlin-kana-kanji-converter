# 分類辞書の収録一覧

30カテゴリ、全体で **1,148,658組**、カテゴリ別に **1,185,626レコード**を収録しています。

「組」は読み・表記の重複を除いた件数、「レコード」は品詞・コストの違いも保持したバイナリへの収録件数です。複数カテゴリへの所属があるため、カテゴリ別の組数の合計は全体の組数と一致しません。

一覧は配布対象の固定データから全件生成しています。Geminiとassistantの暫定分類・未確認の読みを含みます。既存28カテゴリのコストと品詞は元辞書の値です。漢方・医療は提供元の読みと空欄へのGemini推定読み（未確認）を採用し、品詞とコストを本プロジェクトで設定しています。分類取得失敗・未分類・除外候補はこの一覧には含めません。

[品詞IDと品詞名](pos.md) · [生成・配布手順](../classified-dictionary-distribution.md) · [漢方・医療の出典記録](../specialist-dictionaries.md)

| カテゴリ | 読み・表記の組 | 読み数 | レコード数 |
|---|---:|---:|---:|
| [人物・人名](person/index.md) | 488,067 | 380,630 | 495,195 |
| [架空キャラクター](character/index.md) | 10,320 | 10,128 | 10,400 |
| [神話・伝承の存在](mythological_figure/index.md) | 4,378 | 4,131 | 4,378 |
| [地名](place/index.md) | 87,158 | 84,289 | 93,629 |
| [住所](address/index.md) | 122,480 | 122,354 | 122,945 |
| [駅・停留所](station/index.md) | 13,261 | 12,860 | 13,261 |
| [施設](facility/index.md) | 41,572 | 39,511 | 41,573 |
| [交通路線](transport_route/index.md) | 4,955 | 4,914 | 4,955 |
| [組織](organization/index.md) | 65,024 | 63,564 | 65,115 |
| [家系・氏族](lineage/index.md) | 3,232 | 3,175 | 3,232 |
| [商品・サービス](product/index.md) | 15,125 | 14,841 | 15,128 |
| [車両・船舶](vehicle/index.md) | 3,881 | 3,845 | 3,881 |
| [イベント・事件](event/index.md) | 12,057 | 11,906 | 12,059 |
| [賞](award/index.md) | 1,535 | 1,510 | 1,535 |
| [条約・協定](agreement/index.md) | 1,789 | 1,778 | 1,789 |
| [事業・キャンペーン](initiative/index.md) | 1,669 | 1,655 | 1,669 |
| [一般語・専門用語](term/index.md) | 145,827 | 139,944 | 145,866 |
| [作品シリーズ](work_franchise/index.md) | 449 | 445 | 449 |
| [漫画作品](work_manga/index.md) | 5,114 | 5,066 | 5,114 |
| [アニメ作品](work_anime/index.md) | 1,087 | 1,067 | 1,087 |
| [映画作品](work_film/index.md) | 6,240 | 6,209 | 6,242 |
| [番組](work_program/index.md) | 9,838 | 9,735 | 9,840 |
| [書籍作品](work_book/index.md) | 9,175 | 9,100 | 9,177 |
| [ゲーム作品](work_game/index.md) | 3,251 | 3,153 | 3,251 |
| [音楽作品](work_music/index.md) | 12,073 | 11,870 | 12,080 |
| [舞台作品](work_stage/index.md) | 532 | 528 | 532 |
| [定期刊行物](work_periodical/index.md) | 1,882 | 1,832 | 1,883 |
| [媒体未特定の作品・美術作品](work_other/index.md) | 6,231 | 6,198 | 6,237 |
| [漢方・生薬](kampo/index.md) | 432 | 418 | 432 |
| [医療](medical/index.md) | 92,692 | 89,492 | 92,692 |

元データSHA-256: `11015f0d527a6de0056238177f3f33ae543b2854f59ec4a9c44472aed2199f56`

再生成: `python3 scripts/write_classified_dictionary_catalog.py`
整合確認: `python3 scripts/write_classified_dictionary_catalog.py --check`
