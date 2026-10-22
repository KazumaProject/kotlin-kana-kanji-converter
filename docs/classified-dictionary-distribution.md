# 分類辞書の生成と配布

既存の Web・Person・Place・Neologd・wiki の5辞書は、47種類の意味カテゴリ辞書へ置き換えます。追加の漢方・医療2カテゴリを合わせ、計49カテゴリを配布します。[専門辞書の入力と条件](specialist-dictionaries.md) を参照してください。元の5辞書のテキストは、分類結果との照合と品詞・コストの復元に使用します。

一般語・専門用語の `term` は親ディレクトリです。`term/general/` に一般語5分類、`term/specialist/` に専門語10分類を置きます。15分類すべてに収録する用語はGemini 3.5 Flash-Liteの無料枠で `generateContent` APIを並列利用して分類し、読み・表記ごとに最も適合する分類を1つ選びます。分類結果と無料枠の実行情報は固定データに保存し、候補・応答・途中経過はリポジトリ外に置きます。結果は未独立検証のGemini分類として扱います。

分類階層は `src/main/classification/term-taxonomy.json`、固定した読み・表記ごとの分類は `term-classifications.tsv.gz` に保存します。生成時に `term` を15の葉カテゴリへ置き換え、各葉の読み・表記・品詞・コストを従来の配布TSVへ出力します。構造上の親 `term` 自体には辞書バイナリを作りません。

イベント辞書は `src/main/classification/event-taxonomy.json` で「催し・行事」「事件・事故・災害」「歴史的出来事」の3群に分類します。配布するのは催し・行事、記念日・啓発日、試験・検定、自然災害、社会問題・騒動・訴訟、歴史的紛争・政変の6カテゴリです。現在の配布データには合計7,660組を収録し、各カテゴリの件数は[収録一覧](classified-dictionary-catalog/index.md)に掲載しています。犯罪事件・テロ事件・事故は分類用ラベルだけを定義し、該当する読み・表記ペアを分類結果、候補、判断台帳、カタログ、配布データに保存しません。分類はGemini 3.5 Flash-Liteの無料枠を2ワーカーで利用し、候補語と応答本文は保存しません。途中の分類結果は読み・表記と切り離した数値ID・カテゴリIDとしてリポジトリ外の作業領域に一時保存し、完了後に削除します。進捗ではカテゴリ別件数を報告します。無料枠の利用上限に達した場合は処理を停止し、未完了分を再開します。元の広域辞書テキストは分類の入力として維持します。

## 固定入力

`src/main/classification/categories.json` は配布カテゴリの一覧、`term-taxonomy.json` は用語の親カテゴリと15の葉カテゴリ、`event-taxonomy.json` はイベントの3群と分類ラベルの定義です。`term-classifications.tsv.gz` と `event-classifications.tsv.gz` は配布可能なカテゴリに分類された読み・表記ペアのGemini分類結果を固定します。イベントの分類専用ラベルに該当するペアは分類結果にも保存しません。`distribution-decisions.tsv.gz` は読み・表記ごとの最終分類、分類元、収録状態を保存します。分類取得失敗は `no_result` として未分類と区別し、バイナリには収録しません。`distribution-candidates.tsv.gz` はカテゴリ・読み・左品詞ID・右品詞ID・コスト・表記の6列で、元辞書のレコードを保持します。TSVはUTF-8、ヘッダーなしです。

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

`src/main/classification/person-additions/` に、確認済みの名簿をUTF-8 JSONLで保存します。各行に `reading`、`surface`、`left_id`、`right_id`、`cost`、`source_url`、`source_surface`、`source_reading`、`checked_on`（YYYY-MM-DD）を記録し、人物の区分として `sport` または `category_id` のどちらか一方を指定します。`sport` は `person-taxonomy.json` の `sport_subcategories` にあるIDを使い、`category_id` は標準配布が有効な人物カテゴリを使います（`sports` は `sport` で指定します）。名簿には確認箇所を記録し、取得できたページのSHA-256も保存しています。ページ本文はGitへ保存せず、出典は各行のURLで参照します。

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

2026-10-22には、人物辞書全体と固定分類履歴を照合し、未収録・未除外のお笑い芸人17人を `comedian` に追加しました。コンビ名・ユニット名は加えず、公式プロフィールで芸人として確認できる個人を収録しています。候補のうち大東翔生、田中ショータイム、谷口理、楢原真樹には既存の明示的な除外判断があるため、今回追加していません。読み・表記・区分・出典URL・確認箇所は[初回名簿](../src/main/classification/person-additions/comedian-2026-10-22.jsonl)と[追加名簿](../src/main/classification/person-additions/comedian-followup-2026-10-22.jsonl)に記録しています。

## 配布しない人物カテゴリとAI分類

`person-taxonomy.json` で `standard_enabled: false` とした成人向け作品出演者、成人向け作品制作者、宗教関係者、犯罪・非行、諜報、テロ、組織犯罪の各カテゴリは、定義と集計件数だけを保持します。人物名・読み・出典URLを個人単位でリポジトリに保存しません。成人関連保留も個人候補を保存せず、集計のみです。軍事関係者と思想・哲学カテゴリも標準辞書の対象外とし、分類済み候補データとカタログから個人レコードを除きます。成人向け作品の制作者は出演者と分けて `adult_work_creator` に分類し、漫画家カテゴリには混ぜません。成人関連カテゴリはいずれも辞書として配布しません。

Gemini分類器は標準配布が無効なカテゴリを選択肢から外し、軍事関係者や思想・哲学、出演者・制作者など手動確認が必要なコードも受け付けません。成人関連項目は公開資料による手動確認を行い、個人名はリポジトリに残しません。Gemini実行には、リポジトリ外に置いた候補の許可リストと、制限カテゴリまたはメタデータ専用の成人関連保留に属する候補キーを示す除外リストの両方が必要です。除外JSONLは候補キーのSHA-256とカテゴリIDだけを含めます（例：`{"candidate_key":"<64桁SHA-256>","category_id":"adult_related_hold"}`）。コードは分類記録で確認済みの出演者・制作者・成人関連保留候補のハッシュがすべて除外リストにあり、送信候補から外れていることを確認します。未知の成人関連候補が外部の確認記録にない場合までは検出できません。候補名を含む分類ワークスペースとAI応答もリポジトリ外に置きます。過去の一括Gemini実行では候補許可・除外リストを使った記録を確認できなかったため、成人候補を除外していたとは確認できません。この確認強化は今回以降の実行を対象にします。

通常の `v*` リリースでも、汎用 `person` を削除し、`standard_enabled: true` の人物細分類22カテゴリに置き換えた配布ZIPを作成します。既存の非人物カテゴリ48件を含め、ZIPの配布カテゴリは合計70件です。`person-dictionaries-v*` タグは同じ置換ZIPを専用プレリリース添付物としても公開します。軍事関係者・思想・哲学カテゴリの候補は人物分類辞書とカタログに含めません。元の人名・Web・Wiki・Neologd各入力コーパスは変更しません。

2026-10-21の追加調査では、JOC東京2020公式TEAM JAPAN名鑑の18競技168プロフィールを確認しました。明示的な除外判断と衝突した3組は変更せず、残る165組を競技別名簿に記録しました。115組は既存の人物辞書に収録済みで、新規追加は50組です。新規追加の内訳はアーティスティックスイミング4、バドミントン2、カヌー5、飛込4、フェンシング2、射撃8、セーリング6、卓球3、水球11、重量挙げ3、アーチェリー1、スケートボード1です。ゴルフ・近代五種・ローイング・スポーツクライミング・サーフィン・トライアスロンは確認した名簿候補が既に辞書にあったため、追加していません。公式名鑑は[JOC東京2020 TEAM JAPAN](https://www.joc.or.jp/games/olympic/tokyo/japan/)で確認できます。全165組の読み・表記・競技・プロフィールURL・確認箇所・取得ページSHA-256は [joc-tokyo2020-2026-10-21.jsonl](../src/main/classification/person-additions/joc-tokyo2020-2026-10-21.jsonl) に記録しています。

舞台・伝統芸能では、落語芸術協会の現役協会員プロフィールで芸名・読み・芸種を照合できた7組を追加で分類しました（例：かつらこすみ → 桂小すみ、たまがわだいふく → 玉川太福、かがみみちよ → 鏡味味千代）。協会の[公式プロフィール一覧](https://www.geikyo.com/profile/index?disp=99)と個別プロフィールを出典にしています。候補語と読みが一致する公式プロフィールを確認できないものは追加していません。

漫画家・イラストレーターでは、[日本漫画家協会の会員一覧](https://nihonmangakakyokai.or.jp/member)に表記があり、国立国会図書館典拠またはWikidataでも名前と読みが一致する候補のうち、既存の別分類と衝突しない39組を追加しました（例：かしまちあき → 嘉島ちあき、かのうあゆみ → 狩野アユミ、へびぞう → 蛇蔵）。会員一覧だけで読みを推定せず、読みの裏付けがない候補は見送っています。

2026-10-14の名簿は490組（MMA 61組・キックボクシング91組・ボクシング338組）です。人数による上限を設けず、今回取得した[UFC](https://jp.ufc.com/athletes)、[K-1](https://www.k-1.co.jp/fighter)、[大橋ジム](https://www.ohashi-gym.com/boxers/)、[帝拳](https://www.teiken.com/profile/index.html)の公式資料で確認できた候補を収録しています。帝拳の戦績は「対戦相手」列のみを採用し、「試合会場」の地名を混入させません。姓だけ・愛称だけ・読み未確認の候補は追加していません。同じ選手の中黒位置違いである「シーサケット・ソールンビサイ」は重ねて収録せず、「シーサケット・ソー・ルンビサイ」の1表記を採用しました。「組」は読み・表記の件数であり、別表記を人数として数えるものではありません。

人名名簿からの追加は490組・492レコードと東京2020名簿の50組・50レコードで、元人名辞書への追加は489行です。イベント分類では、配布しない犯罪・テロ・事故の1,509組をイベント分類データ、候補、判断履歴、カタログから除きました。現在の固定データは741,698組・758,226レコードで、personレコードは267,976行です。実IMEでの候補表示・順位は未確認です。

## 配布物

`release_zips/japanese_keyboard_dictionary_assets.zip` の各カテゴリは `app/src/main/assets/categories/<カテゴリID>/` に配置し、`yomi.dat.zip`、`tango.dat.zip`、`token.dat.zip` を格納します。内側ZIPには対応する `.dat` が1ファイル入ります。旧5辞書の15ファイルは含みません。他の辞書と共通の `pos_table.dat`、`connectionId.dat.zip`、`id.def` は同じ配布ZIPに含まれます。

共通品詞表は基本辞書・英語辞書・分類辞書の品詞組を含めて一度生成します。その品詞表から全バイナリを生成し、配布ZIPを再読込して、各カテゴリの読み・表記・品詞・コストと余分・欠落のないレコード数を照合します。

[収録一覧](classified-dictionary-catalog/index.md)では、全レコードの読み・表記・左右品詞ID・コスト・分類元をカテゴリ別に掲載します。品詞名は一覧内の対応表で確認できます。大きなカテゴリはGitHub上で閲覧できるサイズに分割します。一覧はリポジトリの文書として保存し、配布ZIPやRelease添付ファイルには含めません。`python3 scripts/write_classified_dictionary_catalog.py` で再生成し、`--check` で固定入力との一致を確認します。

[不採用語と判断理由](classified-dictionary-catalog/excluded/index.md)には、固定判断台帳の `excluded` 全件を読み順で掲載します。PR #141の実効不採用理由と、PR #142を含む後続レビューの最終理由を使用し、モデル判断とユーザー明示判断を区別します。個別のLuna理由を含む不採用一覧の完全な再生成・照合にはローカル台帳が必要です。古い処理で除外され固定判断台帳に読み・表記が残っていない候補、および専門辞書の形式不正・重複による見送りは対象外です。

PR #141の分類台帳と後続レビューは、元のスナップショット→Lunaの実効判断→後続レビューの順に検証します。両PRの配布用TSVを単純に上書きせず、`python3 scripts/classified_distribution.py apply-reviews --commit` で統合し、既存辞書一覧・専門辞書・カタログを再生成します。原スナップショット・台帳・レビューのハッシュを保持し、対象外の判断変更は検証で拒否します。

配布は既存の [GitHub Actions](https://github.com/KazumaProject/kotlin-kana-kanji-converter/actions/workflows/build-and-release.yml) を使用します。手動実行ではビルド・検証後にActions成果物を保存し、`v*` タグのpushでは同じ検証後にGitHubのプレリリースへ辞書ZIP・配布マニフェスト・SHA-256・ライセンスを添付します。閲覧用一覧の固定データとの一致も配布前に検証します。

既存Actionsを手動実行すると、人物細分類済みZIPと `dictionary-distribution-manifest.json`、`DICTIONARY-SHA256SUMS`、`DICTIONARY-LICENSES.txt` を成果物として取得できます。`v*` タグでは通常リリースまたはバージョン付きプレリリースに4ファイルを添付し、通常リリースをLatestに設定します。最新5プレリリースを保持し、通常リリースとそのタグは削除対象に含めません。

利用側IMEは旧5辞書の固定パスを49カテゴリの読み込みへ変更する必要があります。用語カテゴリは `categories/term/general/<分類ID>/` と `categories/term/specialist/<分類ID>/`、イベントカテゴリは `categories/event/<群>/<分類ID>/` の下へ配置します。辞書バイナリの読み戻し検証と、実IMEの候補表示・順位の検証は別です。

## 人物細分類への置換配布

`person-dictionaries-v*` タグでは、通常の49カテゴリから汎用 `person` を除き、`person-taxonomy.json` の `standard_enabled: true` の22人物細分類に置き換えます。未分類の候補を受け入れる辞書は作りません。追加調査でも分類できない候補と、IME候補としての形式条件を満たさない候補は配布元データから除きます。プレリリースZIPは合計70カテゴリ（既存49から `person` を除いた48カテゴリと、人物細分類22カテゴリ）です。カテゴリ別の収録数と全収録語は[最終プレリリースの配布カテゴリ一覧](classified-dictionary-catalog/index.md)にまとめています。新しい人物バイナリは他辞書と共通のPOSテーブルを使います。通常の v* タグのリリースにも同じ置換ZIPを添付します。

`person-dictionary-candidates.tsv.gz` には許可カテゴリの読み・表記・品詞・コスト・競技タグだけを保存します。未分類候補は、再分類できた項目だけを既存カテゴリに移し、なお確定できない項目は出力しません。空の読み・表記、空白・制御文字を含む候補、かな以外の読み、文字を含まない表記も除外します。根拠データと分類作業用キャッシュはリポジトリ外に置き、`scripts/export_person_dictionary_source.py` は許可22カテゴリの行だけを書き出します。成人制作者は `adult_work_creator` として漫画カテゴリから分けますが、出演者・制作者・成人関連保留を含む候補は個人データをリポジトリにも配布用データにも入れません。成人関連の候補キーはリポジトリ外の除外JSONLにハッシュだけを保持し、今後のGemini候補送信前にも網羅を検査します。置換ZIPには汎用 `person` の辞書ファイルを含めません。

置換ZIPの人物辞書は `app/src/main/assets/categories/person/<カテゴリID>/` の下に配置します。`person/` は親ディレクトリで、各サブディレクトリに `yomi.dat.zip`、`tango.dat.zip`、`token.dat.zip` を格納します。他の48カテゴリは `categories/<カテゴリID>/` に置きます。

ZIPルートの `dictionary-distribution-manifest.json` は機械可読の分類メタデータです。人物細分類それぞれに `parentCategoryId: "person"` とカテゴリID、表示名、収録件数、辞書ファイルのパスを記録し、`replacesCategory: "person"` で置換関係を示します。個々の候補名や除外候補はマニフェストに含めません。GitHub Releaseには辞書ZIP、同じマニフェスト、チェックサム、ライセンス表示を添付します。

ダウンロードした置換ZIPから、指定カテゴリの辞書をCLIで使う例です。`--base` には同じコミットから生成した置換前の通常アセットZIPを指定します。

```sh
./gradlew convertPersonCandidates --args='--archive /path/to/person-replacement.zip --base /path/to/japanese_keyboard_dictionary_assets.zip --category sports --count 10 ほりごめゆうと'
```

このCLIは指定した分類別辞書と共通の接続行列・品詞テーブルを置換ZIPから読み込みます。これはこのリポジトリの `KanaKanjiEngine` による確認であり、JapaneseKeyboardアプリへの統合や実端末上の候補順位を検証した結果ではありません。

## 2026-10-14: うずまきボルトの修正

ユーザー確認に基づき、読み「うずまきぼると」、表記「うずまきボルト」を character に登録します（左右品詞1851、コスト8400）。先に報告された「うずまき → UZUMAKI／うず巻／淋蒔」は除外します。判断は `src/main/classification/reviews/` に保存し、`python3 scripts/classified_distribution.py apply-reviews --commit` で固定データへ反映します。`freeze` でも判断履歴を再適用します。

この変更の確認範囲は固定辞書データです。実アプリの候補表示・順位や配布ZIPの更新は含みません。
