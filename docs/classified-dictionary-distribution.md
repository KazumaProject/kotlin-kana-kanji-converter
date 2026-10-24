# 分類辞書の生成と配布

既存の Web・Person・Place・Neologd・wiki の5辞書は、55種類の意味カテゴリ辞書へ置き換えます。追加の漢方・医療2カテゴリを合わせ、計57カテゴリを配布します。[専門辞書の入力と条件](specialist-dictionaries.md) を参照してください。元の5辞書のテキストは、分類結果との照合と品詞・コストの復元に使用します。

一般語・専門用語の `term` は親ディレクトリです。`term/general/` に一般語5分類、`term/specialist/` に専門語10分類を置きます。15分類すべてに収録する用語はGemini 3.5 Flash-Liteの無料枠で `generateContent` APIを並列利用して分類し、読み・表記ごとに最も適合する分類を1つ選びます。分類結果と無料枠の実行情報は固定データに保存し、候補・応答・途中経過はリポジトリ外に置きます。結果は未独立検証のGemini分類として扱います。

分類階層は `src/main/classification/term-taxonomy.json`、固定した読み・表記ごとの分類は `term-classifications.tsv.gz` に保存します。生成時に `term` を15の葉カテゴリへ置き換え、各葉の読み・表記・品詞・コストを従来の配布TSVへ出力します。構造上の親 `term` 自体には辞書バイナリを作りません。

イベント辞書は `src/main/classification/event-taxonomy.json` で「催し・行事」「事件・事故・災害」「歴史的出来事」の3群に分類します。配布するのは催し・行事、記念日・啓発日、試験・検定、自然災害、社会問題・騒動・訴訟、歴史的紛争・政変の6カテゴリです。現在の配布データには合計7,660組を収録し、各カテゴリの件数は[収録一覧](classified-dictionary-catalog/index.md)に掲載しています。犯罪事件・テロ事件・事故は分類用ラベルだけを定義し、該当する読み・表記ペアを分類結果、候補、判断台帳、カタログ、配布データに保存しません。分類はGemini 3.5 Flash-Liteの無料枠を2ワーカーで利用し、候補語と応答本文は保存しません。途中の分類結果は読み・表記と切り離した数値ID・カテゴリIDとしてリポジトリ外の作業領域に一時保存し、完了後に削除します。進捗ではカテゴリ別件数を報告します。無料枠の利用上限に達した場合は処理を停止し、未完了分を再開します。元の広域辞書テキストは分類の入力として維持します。

アニメ・漫画作品と架空キャラクターの分類は `src/main/classification/media-demographic-taxonomy.json` で定義します。配布ラベルは少年向け・青年向け・少女向け・女性向け（Josei）・子ども向け（Kids）・対象層の指定なし／一般向けの6種類です。複数対象層はレビュー用の中間ラベルとして残し、配布前に最も近い単一対象層へ割り当てます。出典未確認・対象層未確定は照合時点の作業状態として定義し、今回の配布辞書には残しません。MyAnimeListは二次的なコミュニティ編集データで、Geminiの判定も個別出典の確認ではありません。アニメは出典が漫画と記録され同名の原作漫画を照合できる場合に限り対象層を継承します。架空キャラクターは出典作品の対象層を継承し、設定年齢では分類しません。公開資料で成人向けと明示された作品、MyAnimeListのHentai／Rx - Hentaiタグが付く作品、またはGeminiが成人向けと判定した作品・キャラクターは全配布カテゴリから除外します。Geminiの成人判定にも誤りがあり得るため、成人向け作品を完全に検出できるとは保証しません。

2026-10-23時点で対象層レビューがある12,708組のうち、成人ラベル103組を除く12,605組を6つの配布カテゴリに収録しました。少年向け4,107組（4,118レコード）、青年向け1,730組（1,731レコード）、少女向け822組（826レコード）、女性向け349組（355レコード）、子ども向け546組（549レコード）、対象層の指定なし／一般向け5,051組（5,099レコード）です。`mixed`、出典未確認、対象層未確定の配布件数はすべて0組・0レコード、辞書全体の `unclassifiedPairs` と `noResultPairs` も0です。

複数対象層だった54組（56レコード）は、出典タグが複数だった38組とGeminiが複数対象層とした16組を、保存済みの `nearest-single-demographic-v1` レビューで一つに決めました。割り当て先は少年向け12組、青年向け17組、少女向け5組、女性向け7組、子ども向け11組、対象層の指定なし2組です。この54組の単一カテゴリ選択はassistantのベストフィット判断で、Gemini APIによる追加分類や独立した出典確認は行っていません。成人向けと判定した34組は公開資料で確認済みの69組と合わせた103組すべてが配布対象外です。PSYREN（さいれん）はMyAnimeList由来のHentaiラベルによる成人誤判定を公式の[少年ジャンプ作品情報](https://www.viz.com/psyren)で訂正し、漫画作品・少年向けとして収録しました。Geminiを用いた8,197組の最善推定は独立した出典確認ではなく、対象層や成人判定の誤りが残る可能性があります。
公開スナップショット照合の10,329件は `src/main/classification/reviews/2026-10-23-media-demographics-complete.jsonl` に、`source_unverified` だった8,197件のモデル再分類は `src/main/classification/reviews/2026-10-23-media-demographics-gemini.jsonl` に保存しました。再生成用のKaggle/Hugging Face CSVはリポジトリに含めません。`scripts/generate_media_demographic_reviews.py` はローカルCSVを標準ライブラリで照合し、外部APIを呼びません。Gemini判定のモデル名、プロンプト・入力ハッシュ、件数、トークン使用量は `src/main/classification/media-demographic-gemini-manifest.json` に記録し、候補名・応答本文・APIキーは含めません。各レビューに応答ハッシュとマニフェストハッシュを保存します。出典と帰属表示は [LICENSE-DATA.md](../LICENSE-DATA.md) を参照してください。

```sh
python3 scripts/generate_media_demographic_reviews.py \
  --anime-csv /path/to/anime_dataset.csv \
  --manga-csv /path/to/manga_dataset.csv \
  --characters-csv /path/to/anime-characters-dataset.csv \
  --write
```

書き込み前は `--write` を省略して件数だけ確認できます。曖昧なタイトル一致、未付与のdemographics、Josei・Kidsタグは少年・青年・少女へ推定変換しません。Hentai／Rx - Hentaiタグが読者層タグと同じレコードに併記される場合は、成人向けを優先して除外します。出典未確認カテゴリは、照合不能・複数一致・異なる対象層の食い違いを明示します。

## 固定入力

`src/main/classification/categories.json` は配布カテゴリの一覧、`term-taxonomy.json` は用語の親カテゴリと15の葉カテゴリ、`event-taxonomy.json` はイベントの3群と分類ラベル、`media-demographic-taxonomy.json` は作品・キャラクターの対象層、出典未確認状態、成人除外ラベルを定義します。`term-classifications.tsv.gz` と `event-classifications.tsv.gz` は配布可能なカテゴリに分類された読み・表記ペアのGemini分類結果を固定します。イベントの分類専用ラベルと成人向けラベルは配布カテゴリに含めません。成人向けラベルを持つレビューは全カテゴリからの除外として検証します。`distribution-decisions.tsv.gz` は読み・表記ごとの最終分類、分類元、収録状態を保存します。分類取得失敗は `no_result` として未分類と区別し、バイナリには収録しません。`distribution-candidates.tsv.gz` はカテゴリ・読み・左品詞ID・右品詞ID・コスト・表記の6列で、元辞書のレコードを保持します。TSVはUTF-8、ヘッダーなしです。

詳細なLuna再分類台帳はGitへ含めず、`.gitignore` 対象の `build/luna-classification/ledger/results.jsonl.gz` にローカル保存します。台帳がない環境でも固定済み配布データとカテゴリ別カタログを検証できますが、Luna応答からの再現監査はスキップされます。カタログの `--check` は不採用理由ページとその要約の照合をスキップし、完全な照合と再生成にはローカル台帳が必要です。

分類の優先順位は、資料で確認した分類、assistantによる4,901件の再分類、保存済みのGemini成功結果の順です。確認済みの分類は、元の採用証明書に加えて、保存済みレビューでカテゴリと独立した読みの両方が確認された候補を含みます。Gemini履歴には最新の保存済み成功結果を使用し、Qwenの結果は使用しません。再分類結果の未分類指定は、その候補のGemini分類を取り消します。明示的な除外指定は分類元にかかわらず収録しません。

分類済みの暫定候補も収録しています。分類の確度や読みの確認状態を一律に保証するデータではありません。出典別件数とハッシュは `distribution-manifest.json` に保存しています。固定時点の収録件数はマニフェストに記録します。同じレコードはカテゴリ内で重複排除し、同じ読み・表記でも品詞やコストの異なる元レコードは保持します。

元辞書、分類ファイル、`id.def` の変更は検証エラーになります。更新時は保存済みの分類結果を再確認して固定入力を作り直します。ActionsがAIや外部の分類資料を取得し直すことはありません。

未分類・元の保留・分類取得失敗をGPT-5.6 Luna Maxで再判定する手順は、[未解決候補の再分類](luna-reclassification.md)を参照してください。再判定結果はカテゴリ付きの採用か理由付きの不採用で保存し、通信エラーや応答欠落は判定済み件数へ含めません。

```sh
python3 scripts/classified_distribution.py freeze \
  --accepted /path/to/accepted-candidates.tsv.gz \
  --dispositions /path/to/candidate-dispositions.tsv.gz \
  --database /path/to/ai-run.sqlite3 \
  --manual /path/to/classifications.jsonl \
  --taxonomy /path/to/categories.json
python3 scripts/classified_distribution.py verify
python3 -m unittest discover -s scripts -p 'test_classified_distribution.py' -v
./gradlew buildDictionaryDistributionManifest test check
```

freezeはSQLiteを読み取り専用の一つのトランザクションで読み、進捗DBや元の分類結果を更新しません。Gitに保存するのは固定した圧縮データ、マニフェスト、必要なコードだけです。

## 一般語の追加

辞書原資料にない一般語は `src/main/classification/term-additions.tsv` に1行ずつ追加します。列は読み・左品詞ID・右品詞ID・コスト・表記・出典URL・確認日（YYYY-MM-DD）です。各行は独立した読みと表記が確認できる辞書・語彙資料を出典にし、配布時は15の用語葉カテゴリのいずれかへ収録します。追加語も固定されたGemini分類に含めてから配布データを再生成します。品詞とコストはMozc形式で指定します。

```text
どぱがき	1851	1851	8400	ドパガキ	https://example.org/dictionary-entry	2026-10-15
```

`freeze` はこの入力を出典確認済みの用語分類として取り込みます。重複行、無効な品詞ID・URL・日付、既存の別分類や除外判断との衝突は拒否します。出典URLと確認日は入力ファイルのハッシュとともに記録されます。

## 公式資料で確認した人名の追加

`src/main/classification/person-additions/` に、確認済みの名簿をUTF-8 JSONLで保存します。各行に `reading`、`surface`、`sport`、`left_id`、`right_id`、`cost`、`source_url`、`source_surface`、`source_reading`、`checked_on`（YYYY-MM-DD）を記録します。`sport` は `person-taxonomy.json` の `sport_subcategories` にあるIDを使用します。今回の名簿には、確認したページのSHA-256と確認箇所も保存しています。ページ本文はGitへ保存せず、出典は各行のURLで参照します。

2026-10-21のJOCパリ2024名鑑は20競技135人を確認しました。既存のperson収録81組に競技タグを付与し、過去の除外2組を出典付きで戻し、未収録52組を追加します。名簿の全行にJOC公式プロフィールURL、氏名・読み、競技、確認箇所、取得ページのSHA-256を保存します。

読みは公式のカナ・ふりがなから、カタカナをひらがなへ変換して空白・中黒・引用符（“”「」）を除去します。長音は保持します。外国人名は公式日本語カタカナ表記を使い、英字名から読みを推定しません。表記は公式名・リングネームの姓名間の空白を除き、中黒などは保持します。競技の区分は名簿の整理用で、過去に別競技へ出場した選手も含みます。

```sh
python3 scripts/classified_distribution.py add-person-names \
  --entries src/main/classification/person-additions/fighters-2026-10-14.jsonl
python3 scripts/classified_distribution.py verify
python3 scripts/write_classified_dictionary_catalog.py
python3 scripts/write_classified_dictionary_catalog.py --check
./gradlew buildDictionaryDistributionManifest test check
```

取り込み前と、一時領域に作成した更新後の固定データを検証してから元人名辞書・固定データ・マニフェストを更新します。既存のperson収録は変更せず、既存の別分類・未分類・取得失敗・除外の判断と衝突する候補はエラーにします。分類判断自体がない既存の元辞書レコードは、公式資料で確認した場合に限り、元の品詞・コストを保持してpersonへ収録します。新しい元人名辞書レコードは左右品詞ID 1851（名詞,一般）・コスト8400です。同じ組に複数の元レコードがある場合、追加人数より配布レコードの増加数が多くなります。

新規判断の分類元は `verified` とし、元の分類履歴を保持したまま、名簿のハッシュ・新規の組・配布レコード数・元辞書への追加行数を `provenance.personAdditions` へ記録します。`verify` はその名簿と配布レコードの一致も確認し、外部サイトを取得しません。同じ名簿を再実行しても重複追加しません。後続の追加には別の名簿ファイルを使用します。`freeze` を改めて実行する場合は、その後に保存済みの追加名簿を取り込み直してください。

## 配布制限のある人物カテゴリとAI分類

`person-taxonomy.json` で `standard_enabled: false` とした成人向け作品出演者、成人向け作品制作者、宗教関係者、犯罪・非行、諜報、テロ、組織犯罪の各カテゴリは、定義と集計件数だけを保持します。人物名・読み・出典URLを個人単位でリポジトリに保存しません。成人関連保留も個人候補を保存せず、集計のみです。軍事関係者は標準辞書に配布せず、人物名を含む候補データとカタログから除きます。哲学者・思想家は配布可能にしましたが、典拠資料で表記と読み、職業・著作資料で分類を確認した手動追加だけを収録します。過去の未確認候補はまとめて復元しません。成人向け作品の制作者は出演者と分けて `adult_work_creator` に分類し、漫画家カテゴリには混ぜません。成人関連カテゴリはいずれも辞書として配布しません。

Gemini分類器は標準配布が無効なカテゴリを選択肢から外し、軍事関係者や哲学者・思想家、出演者・制作者など手動確認が必要なコードも受け付けません。成人関連項目は公開資料による手動確認を行い、個人名はリポジトリに残しません。Gemini実行には、リポジトリ外に置いた候補の許可リストと、制限カテゴリまたはメタデータ専用の成人関連保留に属する候補キーを示す除外リストの両方が必要です。除外JSONLは候補キーのSHA-256とカテゴリIDだけを含めます（例：`{"candidate_key":"<64桁SHA-256>","category_id":"adult_related_hold"}`）。コードは分類記録で確認済みの出演者・制作者・成人関連保留候補のハッシュがすべて除外リストにあり、送信候補から外れていることを確認します。未知の成人関連候補が外部の確認記録にない場合までは検出できません。候補名を含む分類ワークスペースとAI応答もリポジトリ外に置きます。過去の一括Gemini実行では候補許可・除外リストを使った記録を確認できなかったため、成人候補を除外していたとは確認できません。この確認強化は今回以降の実行を対象にします。

通常の `v*` リリースでも、汎用 `person` を削除し、`standard_enabled: true` の人物細分類29カテゴリに置き換えた配布ZIPを作成します。既存の非人物カテゴリ56件を含め、ZIPの配布カテゴリは合計85件です。`person-dictionaries-v*` タグは専用プレリリースとして公開しません。軍事関係者は配布対象外です。姓・名・姓名の由来分類は暫定的で一部のみ出典を再確認しています。哲学者・思想家は、典拠資料で表記と読みを、職業・著作資料で分類を個別に確認した追加だけを収録します。元の人名・Web・Wiki・Neologd各入力コーパスは変更しません。

2026-10-21の追加調査では、JOC東京2020公式TEAM JAPAN名鑑の18競技168プロフィールを確認しました。明示的な除外判断と衝突した3組は変更せず、残る165組を競技別名簿に記録しました。115組は既存の人物辞書に収録済みで、新規追加は50組です。新規追加の内訳はアーティスティックスイミング4、バドミントン2、カヌー5、飛込4、フェンシング2、射撃8、セーリング6、卓球3、水球11、重量挙げ3、アーチェリー1、スケートボード1です。ゴルフ・近代五種・ローイング・スポーツクライミング・サーフィン・トライアスロンは確認した名簿候補が既に辞書にあったため、追加していません。公式名鑑は[JOC東京2020 TEAM JAPAN](https://www.joc.or.jp/games/olympic/tokyo/japan/)で確認できます。全165組の読み・表記・競技・プロフィールURL・確認箇所・取得ページSHA-256は [joc-tokyo2020-2026-10-21.jsonl](../src/main/classification/person-additions/joc-tokyo2020-2026-10-21.jsonl) に記録しています。

舞台・伝統芸能では、落語芸術協会の現役協会員プロフィールで芸名・読み・芸種を照合できた7組を追加で分類しました（例：かつらこすみ → 桂小すみ、たまがわだいふく → 玉川太福、かがみみちよ → 鏡味味千代）。協会の[公式プロフィール一覧](https://www.geikyo.com/profile/index?disp=99)と個別プロフィールを出典にしています。候補語と読みが一致する公式プロフィールを確認できないものは追加していません。

漫画家・イラストレーターでは、[日本漫画家協会の会員一覧](https://nihonmangakakyokai.or.jp/member)に表記があり、国立国会図書館典拠またはWikidataでも名前と読みが一致する候補のうち、既存の別分類と衝突しない39組を追加しました（例：かしまちあき → 嘉島ちあき、かのうあゆみ → 狩野アユミ、へびぞう → 蛇蔵）。会員一覧だけで読みを推定せず、読みの裏付けがない候補は見送っています。

2026-10-14の名簿は490組（MMA 61組・キックボクシング91組・ボクシング338組）です。人数による上限を設けず、今回取得した[UFC](https://jp.ufc.com/athletes)、[K-1](https://www.k-1.co.jp/fighter)、[大橋ジム](https://www.ohashi-gym.com/boxers/)、[帝拳](https://www.teiken.com/profile/index.html)の公式資料で確認できた候補を収録しています。帝拳の戦績は「対戦相手」列のみを採用し、「試合会場」の地名を混入させません。姓だけ・愛称だけ・読み未確認の候補は追加していません。同じ選手の中黒位置違いである「シーサケット・ソールンビサイ」は重ねて収録せず、「シーサケット・ソー・ルンビサイ」の1表記を採用しました。「組」は読み・表記の件数であり、別表記を人数として数えるものではありません。

人名名簿からの追加は490組・492レコードと東京2020名簿の50組・50レコードで、元人名辞書への追加は489行です。哲学者・思想家には出典を確認した255組を追加しました。イベント分類では、配布しない犯罪・テロ・事故の1,509組をイベント分類データ、候補、判断履歴、カタログから除きました。現在の固定データは741,945組・758,473レコードで、personレコードは268,223行です。実IMEでの候補表示・順位は未確認です。

## 配布物

`release_zips/japanese_keyboard_dictionary_assets.zip` の各カテゴリは `app/src/main/assets/categories/<カテゴリID>/` に配置し、`yomi.dat.zip`、`tango.dat.zip`、`token.dat.zip` を格納します。内側ZIPには対応する `.dat` が1ファイル入ります。旧5辞書の15ファイルは含みません。他の辞書と共通の `pos_table.dat`、`connectionId.dat.zip`、`id.def` は同じ配布ZIPに含まれます。

共通品詞表は基本辞書・英語辞書・分類辞書の品詞組を含めて一度生成します。その品詞表から全バイナリを生成し、配布ZIPを再読込して、各カテゴリの読み・表記・品詞・コストと余分・欠落のないレコード数を照合します。

[収録一覧](classified-dictionary-catalog/index.md)では、全レコードの読み・表記・左右品詞ID・コスト・分類元をカテゴリ別に掲載します。アニメ作品・漫画作品・架空キャラクターの各目次には、少年向け・青年向け・少女向け・女性向け・子ども向け・一般向けの収録数と、対象層ごとの全単語一覧へのリンクを掲載します。品詞名は一覧内の対応表で確認できます。大きなカテゴリはGitHub上で閲覧できるサイズに分割します。一覧はリポジトリの文書として保存し、配布ZIPやRelease添付ファイルには含めません。`python3 scripts/write_classified_dictionary_catalog.py` で再生成し、`--check` で固定入力との一致を確認します。

[不採用語と判断理由](classified-dictionary-catalog/excluded/index.md)には、固定判断台帳の `excluded` 全件を読み順で掲載します。PR #141の実効不採用理由と、PR #142を含む後続レビューの最終理由を使用し、モデル判断とユーザー明示判断を区別します。個別のLuna理由を含む不採用一覧の完全な再生成・照合にはローカル台帳が必要です。古い処理で除外され固定判断台帳に読み・表記が残っていない候補、および専門辞書の形式不正・重複による見送りは対象外です。

PR #141の分類台帳と後続レビューは、元のスナップショット→Lunaの実効判断→後続レビューの順に検証します。両PRの配布用TSVを単純に上書きせず、`python3 scripts/classified_distribution.py apply-reviews --commit` で統合し、既存辞書一覧・専門辞書・カタログを再生成します。原スナップショット・台帳・レビューのハッシュを保持し、対象外の判断変更は検証で拒否します。

PRでは [`Build classified dictionary for PR`](../.github/workflows/build-classified-dictionary.yml) が実行され、PRの固定分類から辞書ZIPを生成します。Geminiなどの分類APIは呼び出しません。カタログと固定データの一致、辞書バイナリの生成・読み戻し、配布マニフェストを検証し、辞書ZIP・配布マニフェスト・SHA-256・ライセンスを14日間Actions成果物として保存します。PRのChecksから該当実行を開くとArtifactsからダウンロードできます。入力はMozcコミット `c4b2aef7c65e61be394bacadaec200eb5b97f91c` とJapaneseCorpusリリース `v2026.1019.20` に固定します。上流辞書を更新するときは両方の入力と専門辞書の重複除外データを一緒に更新します。

通常配布は既存の [GitHub Actions](https://github.com/KazumaProject/kotlin-kana-kanji-converter/actions/workflows/build-and-release.yml) を使用します。手動実行ではビルド・検証後にActions成果物を保存し、`vX.Y.Z` タグのpushでは同じ検証後に通常版GitHub Releaseを作成して、辞書ZIP・配布マニフェスト・SHA-256・ライセンスを添付します。今回の作品・キャラクター対象層辞書もこの手順で配布します。閲覧用一覧の固定データとの一致も配布前に検証します。

既存Actionsを手動実行すると、人物細分類済みZIPと `dictionary-distribution-manifest.json`、`DICTIONARY-SHA256SUMS`、`DICTIONARY-LICENSES.txt` を成果物として取得できます。安定版 `vX.Y.Z` タグでは通常リリースに4ファイルを添付し、最新リリースをLatestに設定します。タグ実行後は、すべてのプレリリースと関連タグを削除し、通常版辞書リリースと関連タグを新しい順に5件だけ残します。古い通常版とタグも削除します。

2026-10-23に [v1.7.270](https://github.com/KazumaProject/kotlin-kana-kanji-converter/releases/tag/v1.7.270) を安定版として公開しました。実行結果は[GitHub Actions run 39980585048](https://github.com/KazumaProject/kotlin-kana-kanji-converter/actions/runs/39980585048)で確認できます。公開後に保持している安定版は v1.7.270、v1.7.268、v1.7.266、v1.7.265、v1.7.262 の5件で、プレリリースはありません。ハイフン付き `v*` タグおよび `person-dictionaries-v*` タグではReleaseを公開しません。

利用側IMEは固定辞書パスではなく、`distribution-manifest.json` に列挙されたカテゴリIDを読み込みます。用語カテゴリは `categories/term/general/<分類ID>/` と `categories/term/specialist/<分類ID>/`、イベントカテゴリは `categories/event/<群>/<分類ID>/`、施設カテゴリは `categories/facility/<大分類>/<中分類>/`、対象層カテゴリは `categories/media_demographic/audience/<分類ID>/` の下へ配置します。成人向けラベルに該当する候補は配布データへ作成しません。辞書バイナリの読み戻し検証と、実IMEの候補表示・順位の検証は別です。

## 施設辞書の用途別分類

施設辞書は16大分類と59葉カテゴリで配布します。分類の正本、境界基準、無料枠Geminiによる再開可能な分類手順、検証方法は[施設分類ドキュメント](facility-classification.md)に記録しています。施設カテゴリには `other` や `unclassified` を設けず、元の35,063読み・表記ペアすべてを一つの葉へ分類しました。現在は35,131読み・表記ペア、35,138レコードです。飲食店の葉カテゴリには542レコードを収録し、東京23店、大阪7店、京都7店、奈良5店の42ペアを追加しました。また新語候補issue全12件から未収録の36ペアを加え、このうち3件が施設カテゴリです。前回までの25店の調査例を含む地域別の店舗名と根拠URLは[施設分類ドキュメント](facility-classification.md)に記録しています。

## 人物細分類への置換配布

人物細分類の置換辞書は、通常版 `vX.Y.Z` リリースに含まれます。配布カテゴリから汎用 `person` を除き、`person-taxonomy.json` の `standard_enabled: true` の29人物細分類に置き換えます。未分類の候補を受け入れる辞書は作りません。追加調査でも分類できない候補と、IME候補としての形式条件を満たさない候補は配布元データから除きます。哲学者・思想家カテゴリはGeminiの自動分類対象にせず、出典付きの人名追加だけを受け入れます。姓・名・姓名の由来ラベルは暫定的で、一部を対象とした再確認のみです。置換後のZIPのカテゴリ数は分類マニフェストに記録します。カテゴリ別の収録数と全収録語は[配布カテゴリ一覧](classified-dictionary-catalog/index.md)にまとめています。新しい人物バイナリは他辞書と共通のPOSテーブルを使います。

`person-dictionary-candidates.tsv.gz` には許可カテゴリの読み・表記・品詞・コスト・競技タグだけを保存します。未分類候補は、再分類できた項目だけを既存カテゴリに移し、なお確定できない項目は出力しません。空の読み・表記、空白・制御文字を含む候補、かな以外の読み、文字を含まない表記も除外します。根拠データと分類作業用キャッシュはリポジトリ外に置き、`scripts/export_person_dictionary_source.py` は許可29カテゴリの行だけを書き出します。由来未確認の候補は、固定済みの暫定分類を反映して由来別カテゴリへ移しますが、元の人名・Web・Wiki・Neologd各入力コーパスは変更しません。人物追加行は読み・表記の典拠URLと原資料の読み・表記を記録し、哲学者・思想家の場合は分類根拠のURLと確認箇所も記録します。成人制作者は `adult_work_creator` として漫画カテゴリから分けますが、出演者・制作者・成人関連保留を含む候補は個人データをリポジトリにも配布用データにも入れません。成人関連の候補キーはリポジトリ外の除外JSONLにハッシュだけを保持し、今後のGemini候補送信前にも網羅を検査します。置換ZIPには汎用 `person` の辞書ファイルを含めません。

置換ZIPの人物辞書は `app/src/main/assets/categories/person/<カテゴリID>/` の下に配置します。`person/` は親ディレクトリで、各サブディレクトリに `yomi.dat.zip`、`tango.dat.zip`、`token.dat.zip` を格納します。その他のカテゴリは `categories/<カテゴリID>/` に置きます。

ZIPルートの `dictionary-distribution-manifest.json` は機械可読の分類メタデータです。人物細分類それぞれに `parentCategoryId: "person"` とカテゴリID、表示名、収録件数、辞書ファイルのパスを記録し、`replacesCategory: "person"` で置換関係を示します。個々の候補名や除外候補はマニフェストに含めません。GitHub Releaseには辞書ZIP、同じマニフェスト、チェックサム、ライセンス表示を添付します。

ダウンロードした置換ZIPから、指定カテゴリの辞書をCLIで使う例です。`--base` には同じコミットから生成した置換前の通常アセットZIPを指定します。

```sh
./gradlew convertPersonCandidates --args='--archive /path/to/person-replacement.zip --base /path/to/japanese_keyboard_dictionary_assets.zip --category sports --count 10 ほりごめゆうと'
```

このCLIは指定した分類別辞書と共通の接続行列・品詞テーブルを置換ZIPから読み込みます。これはこのリポジトリの `KanaKanjiEngine` による確認であり、JapaneseKeyboardアプリへの統合や実端末上の候補順位を検証した結果ではありません。

## 2026-10-14: うずまきボルトの修正

ユーザー確認に基づき、読み「うずまきぼると」、表記「うずまきボルト」を character に登録します（左右品詞1851、コスト8400）。先に報告された「うずまき → UZUMAKI／うず巻／淋蒔」は除外します。判断は `src/main/classification/reviews/` に保存し、`python3 scripts/classified_distribution.py apply-reviews --commit` で固定データへ反映します。`freeze` でも判断履歴を再適用します。

この変更の確認範囲は固定辞書データです。実アプリの候補表示・順位や配布ZIPの更新は含みません。
