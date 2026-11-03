# 新語候補Issueレビュー（2026-11-02）

## 判定

未処理だった候補Issue #277、#278、#279、#280、#281、#284、#286、#287の16語を確認した。14語を既存の分類へ追加し、2語を保留する。Issue #257「Echo Time」は前回レビューの保留を維持し、今回確認対象に含めた合計は17語。Issue内で既出・見送りとされた候補は再登録しない。

レビュー前のclassified候補データには、今回の16組すべての読み・表記ペアが存在しなかった。これはその分類ファイル内の不在だけを示し、system辞書やconsumer全体で出力できないことの証拠ではない。実際、#279と#280の保留語は公式v1.7.283配布ZIPを使ったsystem CLIで出力されたため、追加を保留した。

| Issue | 読み | 表記 | 分類・判断 |
| --- | --- | --- | --- |
| #277 | くらいむらいと | CRYMELIGHT | 作品／ゲーム・追加 |
| #278 | そのぼ | SonoVo | 商品・サービス・追加 |
| #279 | れいりあかすがばる | レイリア春日原 | 施設／商業施設・保留（v1.7.283簡易CLI rank 5） |
| #280 | しーばむ | CBAM | 専門語／法律・政治・追加 |
| #280 | さふ | SAF | 専門語／交通・安全・防衛・追加 |
| #280 | しーしーえす | CCS | 専門語／地球・環境・資源・追加 |
| #280 | くらいおせいけん | クライオ生検 | 専門語／医療・生命科学・保留（v1.7.283簡易CLI rank 7） |
| #281 | みらいぶろーどらいばー | MIRAI BlowDry BAR | 商品・サービス・追加 |
| #284 | ふぁいあーえむぶれむばんしせんこう | ファイアーエムブレム 万紫千紅 | 作品／ゲーム・追加 |
| #284 | まふつしん | 真経津晨 | 架空人物／キャラクター・青年向け・追加 |
| #284 | みたらいあきら | 御手洗暉 | 架空人物／キャラクター・青年向け・追加 |
| #286 | にゅーと | NEWT | 商品・サービス・追加 |
| #286 | ねすかふぇ | NESCAFÉ | 商品・サービス・追加 |
| #286 | ぽっぷまーと | POP MART | 商品・サービス／ブランド・追加 |
| #287 | じーえむおーありーなさいたま | GMOアリーナさいたま | 施設／スポーツ競技場・追加 |
| #287 | やんまーはなさかすたじあむ | YANMAR HANASAKA STADIUM | 施設／スポーツ競技場・追加 |

## 候補別の根拠と判断

- **#277 CRYMELIGHT:** [フリュー公式作品ページ](https://www.cs.furyu.jp/crymelight/)と[発売元の発表](https://www.furyu.jp/news/2026/04/crymelight/)で日本語名・英字名の対応と発売予定日を確認。2026-11-05発売予定。
- **#278 SonoVo:** [NTTソノリティの発表](https://ntt-sonority.com/blogs/news/260602)が「SonoVo（ソノボ）」を直接併記し、後続の[公式製品発表](https://ntt-sonority.com/blogs/news/260715)でもブランドとして継続使用。
- **#279 レイリア春日原:** [施設公式](https://rairia-kasugabaru.com/)と[西鉄の開業発表](https://www.nishitetsu.co.jp/ja/news/news20260428.html)で施設名・場所・営業開始を確認。全体のひらがな読みは公式資料に連続表記されていない。簡易CLIで表記がrank 5に出ることは、経路が一ノードである証拠ではない。全体表記がすでに候補出力にあるため、重複登録を保留する。
- **#280 CBAM / SAF / CCS / クライオ生検:** [欧州委員会](https://taxation-customs.ec.europa.eu/carbon-border-adjustment-mechanism_en)と[JETRO](https://www.jetro.go.jp/biz/areareports/special/2026/0901/55984d0e75711c6c.html)でCBAMの制度と国内影響を確認。「シーバム」の読みは[国内専門解説](https://www.qualikeep.com/blog/cbam-tanso-kokkyo-chosei)に基づき、一次資料の読みではないと記録した。SAFは[経済産業省](https://www.meti.go.jp/shingikai/energy_environment/saf/008.html)の政策資料と[NTTファシリティーズ](https://www.ntt-f.co.jp/column/0232.html)の「SAF（サフ）」表記を確認。CCSは[NRI用語解説](https://www.nri.com/jp/knowledge/glossary/ccs_ccus.html)を確認。クライオ生検は[日本肺癌学会](https://www.haigan.gr.jp/public/guidebook/2024/2024/Q6.html)と[国立がん研究センター](https://www.ncc.go.jp/jp/information/pr_release/2026/0817/index.html)で実在を確認し、簡易CLIでrank 7のため保留する。
- **#281 MIRAI BlowDry BAR:** [提供元の発表](https://prtimes.jp/main/html/rd/p/000000027.000089743.html)で製品名を確認。法人名を候補へ付け足さない。
- **#284 万紫千紅 / 真経津晨 / 御手洗暉:** [任天堂の公式発表](https://www.nintendo.com/jp/topics/article/96a406b3-fa89-44f4-97ff-44fbc0a7aecf)で作品名と「ばんしせんこう」を確認。[公式アニメサイト](https://junketbank-anime.com/news/72/)は人物名とローマ字表記（Shin Mafutsu / Akira Mitarai）を対応づける。人物2名のかな読みはローマ字から転写したもので、公式のかな表記を直接確認したものではない。[週刊ヤングジャンプ公式作品ページ](https://youngjump.jp/manga/junketbank/)と[集英社の公式誌紹介](https://www.shueisha.co.jp/pickup/22698/)で、原作漫画の掲載誌と青年漫画誌という対象層を確認し、taxonomyに従いキャラクター2名へ青年向けタグを付ける。
- **#286 NEWT / NESCAFÉ / POP MART:** [令和トラベル](https://www.reiwatravel.co.jp/product)は「NEWT（ニュート）」、[ネスレ日本](https://www.nestle.co.jp/media/pressreleases/20261001_nescafe_1)は新アプリ「NESCAFÉ（ネスカフェ）」と公開日、[POP MART JAPANの発表](https://prtimes.jp/main/html/rd/p/000000043.000062707.html)は「POP MART（ポップマート）」と明記。飲料ブランドの発売年と新アプリの公開日、予定店舗の開店状況を混同しない。
- **#287 GMOアリーナさいたま / YANMAR HANASAKA STADIUM:** [施設運営者の資料](https://www.saitama-arena.co.jp/news/wp-content/uploads/sites/3/2026/05/04_salessheet.pdf)はGMOアリーナの正式名称と読みを明記。[セレッソ大阪](https://www.cerezo.jp/news/2026-0306-1100/)はYANMAR HANASAKA STADIUMの名称全体と「ヤンマーハナサカスタジアム」を併記。両方とも新設施設でなく既存施設の新愛称として扱う。
- **#257 Echo Time:** [Amazon公式発表](https://press.aboutamazon.com/jp/2026/10/amazon-unveils-echo-time-and-echo-dot-designed-for-its-generative-ai-powered-alexa)で商品名は確認できるが、同発表は日本語の読みを示していない。公式の商品ページ原本で「エコータイム」を再確認できていないため、前回どおり保留する。

## 配布アセットとconsumer経路の照合範囲

似た名前の古い作業コピーをconsumerの証拠にせず、公式KazumaProject/JapaneseKeyboardのdev checkout（revision 5b74c8c471bc009279bf26217d907f23eacd2cc7）と、その実行時の辞書経路を確認した。consumerのFindPath.ktは通常unigramを候補経路上の各ノードで照合する。一方、standalone条件は元入力全体に一致する一ノード経路に限定される。よって、ノードの一致を候補全体・入力全体の一致とは読み替えない。

比較基準のconverter v1.7.283公式アーカイブSHA-256は 2c13311ce86c3dbec45c8b6a8f8fad7200dcfdaac24aab9f93a9e0fb1656f724。consumerのマニフェストの値と一致し、ZIP展開検証も通過した。consumer checkout内のカテゴリ辞書ZIP 429件は、公式アーカイブの同名バイナリと429一致、欠落0、不一致0。system runtime資産のハッシュは次の通り。

- system/tango.dat.zip: 5fbaf9bbd620d2766b46cd247d1d862f83bf012d988900361970e988b7d62965
- system/token.dat.zip: 02c560fb0e1a39bfa9bba09d4453416c3d0232a0e8380466351cd0401d44945f
- system/yomi.dat.zip: 716297c927aaeeb6630f50b371953ae0343b5126bfdd512240e5310e1cbfa74a
- ngram/system_ngram.dat: 8d47adb7934ea687cae8254760623a40de1e009d5a028bf8d2f377fd39b71a0b
- ngram/system_ngram_unigram.dat: 3619430157ec6b58f0d0801a7e73e9a7567e3d6aa6bb34ac53ad4f52da9b7480
- ngram/system_ngram_standalone_unigram.dat: b3ccd95031ad8e32181a6d1e068acea9774a12dfb4f3f99cf93f41bfec52ab61

この照合はconsumerのソース経路と既配布ファイルの一致、およびconverter CLIの出力を確認したもの。Androidアプリ全体の起動・ユーザー辞書統合・実機順位は確認しておらず、CLIのrankをアプリ挙動や一ノード経路の証拠とはしない。

## 回帰確認

既存の確認対象である「しろ」「しろい」「しろくろ」「しろあり」を同じv1.7.283配布ZIPで照合し、「しろ + 医」の既存回帰ケースを維持する。新規テストは追加せず、既存のテストとビルド時検証を使う。
