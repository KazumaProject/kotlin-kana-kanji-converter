# Open dictionary-candidate issue review (2026-11-01)

対象は2026-11-01時点でopenだった「IME適合候補」issue 26件。候補表58組について、過去の同種issue、分類済み辞書ソース、候補別の公式出典を照合した。

## 重複確認

GitHub検索で見つかった同種issue 73件（今回のopen 26件と過去47件、過去候補91組）を比較。表記をUnicode NFKC・大小文字・空白・句読点で正規化しても、今回の58組と過去候補の間に同一表記の重複はなかった。open候補同士にも同一読み・同一表記、同一読みの表記違いはなかった。したがって重複を理由に閉じるissueはない。

58組は`distribution-candidates.tsv.gz`および`distribution-decisions.tsv.gz`に完全一致の組がなく、既存の一般分類ソースには未収録だった。各追加記録の一次出典は同じ行のJSONLに保持した。

## 判断

候補issue本文の公式資料で標準表記と読み、または読みを組み立てる各要素を確認でき、専用カテゴリで継続的な入力が見込める57組を辞書へ追加する。Issue #257の Echo Time は公式資料で英字商品名は確認できたが、読み「エコータイム」を公式資料で確認できなかったため保留。読みを推測で登録しない。

| Issue | 件数 | 候補 |
| --- | ---: | --- |
| [#275](https://github.com/KazumaProject/kotlin-kana-kanji-converter/issues/275) | 1 | ことね → kotone (product) |
| [#272](https://github.com/KazumaProject/kotlin-kana-kanji-converter/issues/272) | 1 | となりえくりはまぱーく → トナリエ久里浜パーク (facility/commercial/shopping) |
| [#271](https://github.com/KazumaProject/kotlin-kana-kanji-converter/issues/271) | 2 | ことばる → KOTOBAL (product)<br>べりみー → VeriMe (product) |
| [#270](https://github.com/KazumaProject/kotlin-kana-kanji-converter/issues/270) | 2 | ぷらぐまた → PRAGMATA (work_game)<br>うるとらくしょん → ULTRActi:on (work_music) |
| [#269](https://github.com/KazumaProject/kotlin-kana-kanji-converter/issues/269) | 1 | がんだむあっせんぶる → GUNDAM ASSEMBLE (product) |
| [#266](https://github.com/KazumaProject/kotlin-kana-kanji-converter/issues/266) | 2 | たびじあ → TABISIA (facility/commercial/shopping)<br>あじよん → ASIYONG (facility/commercial/shopping) |
| [#265](https://github.com/KazumaProject/kotlin-kana-kanji-converter/issues/265) | 1 | ふれぼる → FleBOL (product) |
| [#264](https://github.com/KazumaProject/kotlin-kana-kanji-converter/issues/264) | 2 | しゅたいんずげーとりぶーと → STEINS;GATE RE:BOOT (work_game)<br>さいれんとひるたうんふぉーる → SILENT HILL: Townfall (work_game) |
| [#262](https://github.com/KazumaProject/kotlin-kana-kanji-converter/issues/262) | 2 | ばんどぼっくすそろ → BandBox Solo (product)<br>ばんどぼっくすとりお → BandBox Trio (product) |
| [#260](https://github.com/KazumaProject/kotlin-kana-kanji-converter/issues/260) | 1 | あくあげーとせんじゅおおかわばた → AQUA GATE 千住大川端 (place) |
| [#259](https://github.com/KazumaProject/kotlin-kana-kanji-converter/issues/259) | 1 | あれくさぷらす → Alexa+ (product) |
| [#258](https://github.com/KazumaProject/kotlin-kana-kanji-converter/issues/258) | 3 | すらいでぃん → Slidin (work_music)<br>ぶるーのゔぁ → B.L.U.E. NOVA (work_game)<br>ぷりま → PRIMA (work_music) |
| [#257](https://github.com/KazumaProject/kotlin-kana-kanji-converter/issues/257) | 1 | えこーたいむ → Echo Time (保留: 読み未確認) |
| [#255](https://github.com/KazumaProject/kotlin-kana-kanji-converter/issues/255) | 3 | まーゔうらやす → M'av浦安 (facility/commercial/shopping)<br>えくぼけいせいしんかまがや → ekubo京成 新鎌ケ谷 (facility/commercial/shopping)<br>くおーつしんさいばし → QUARTZ SHINSAIBASHI (facility/residential/mixed_use_building) |
| [#254](https://github.com/KazumaProject/kotlin-kana-kanji-converter/issues/254) | 3 | えーじぇんとあい → Agent i (product)<br>らいんかれんだー → LINEカレンダー (product)<br>しんくみー → SyncMe (product) |
| [#253](https://github.com/KazumaProject/kotlin-kana-kanji-converter/issues/253) | 2 | びーすとおぶりんかねーしょん → Beast of Reincarnation (work_game)<br>さるふぁー → SULFUR (work_game) |
| [#252](https://github.com/KazumaProject/kotlin-kana-kanji-converter/issues/252) | 4 | みにえゔぉつー → mini Evo 2 (product)<br>すくえあつー → SQUARE 2 (product)<br>そふとへいず → SOFT HAZE (product)<br>ぱるつー → Pal 2 (product) |
| [#249](https://github.com/KazumaProject/kotlin-kana-kanji-converter/issues/249) | 2 | りんくすいけぶくろ → LINKS IKEBUKURO (facility/commercial/shopping)<br>ひびやくろすぱーく → HIBIYA CROSSPARK (facility/residential/mixed_use_building) |
| [#248](https://github.com/KazumaProject/kotlin-kana-kanji-converter/issues/248) | 2 | せかんどりていりんぐ → 2nd RETAILING (organization)<br>れみの → Lemino (product) |
| [#245](https://github.com/KazumaProject/kotlin-kana-kanji-converter/issues/245) | 3 | らぷそでぃいんすかーれっと → Rhapsody in Scarlet (work_game)<br>ゆーれい → UREI (work_music)<br>ちゅーじんみー → Choosin’ Me (work_music) |
| [#241](https://github.com/KazumaProject/kotlin-kana-kanji-converter/issues/241) | 4 | きゅーれぼつーぷろ → Qrevo 2 Pro (product)<br>ぜんぷろでぃーてん → Zen Pro D10 (product)<br>おーるうぇいずゆー → Always You (product)<br>ふぁつぃお → Fazzio (product) |
| [#239](https://github.com/KazumaProject/kotlin-kana-kanji-converter/issues/239) | 3 | はえら → HAERA (facility/commercial/shopping)<br>ことえはしもと → COTOE橋本 (facility/commercial/shopping)<br>てがらやまへいわこうえんえき → 手柄山平和公園駅 (station) |
| [#238](https://github.com/KazumaProject/kotlin-kana-kanji-converter/issues/238) | 3 | えーじぇんてぃっくすたー → AGENTIC STAR (product)<br>りでうぇるねす → Re・De Wellness (product)<br>あいとりあ → Aitria (organization) |
| [#237](https://github.com/KazumaProject/kotlin-kana-kanji-converter/issues/237) | 2 | あめにてぃ → AMENITY (work_music)<br>ねーむれす → nameless (work_music) |
| [#232](https://github.com/KazumaProject/kotlin-kana-kanji-converter/issues/232) | 3 | すーぱーわん → Super-ONE (product)<br>ふりーくりっぷつーえす → FreeClip 2 S (product)<br>うぉっちじーてぃーせぶんぷろ → WATCH GT 7 Pro (product) |
| [#229](https://github.com/KazumaProject/kotlin-kana-kanji-converter/issues/229) | 4 | おおいまちとらっくす → OIMACHI TRACKS (facility/residential/mixed_use_building)<br>もんたかなわ → MoN Takanawa (facility/cultural/museum)<br>しぶやらぶず → Shibuya LOVEZ (facility/entertainment/live_venue)<br>しんつなしまみっか → 新綱島MICCA (facility/commercial/shopping) |

## 検証範囲

このレビューは候補表、配布元ソース、および当該issueに引用された公式資料の記載を確認したもの。JapaneseKeyboard実アプリの全候補順位、学習、予測を含むアプリ全体の互換性を主張するものではない。リリース後は実際に配布されたZIP内の各カテゴリ資産とSHA-256を照合する。
