# Categorized dictionary sources

This package contains selected, normalized entries from the supplemental inputs
committed to KazumaProject/kotlin-kana-kanji-converter: names.txt, place.txt.zip,
only_wiki.txt.zip, only_neologd.txt.zip and wiki_neologd_common.txt.zip.
Their exact hashes are recorded in manifest.json. This notice does not replace
upstream licenses or grant additional rights to third-party names or text.

- Mozc reading/POS evidence: https://github.com/google/mozc (BSD-3-Clause).
- MozcUT source project: https://github.com/utuhiro78/merge-ut-dictionaries
- NEologd source project: https://github.com/neologd/mecab-ipadic-neologd
  (see that project's Apache-2.0 license and source notices).
- Wiki-derived source entries: https://ja.wikipedia.org/ . Consult Wikimedia's
  applicable reuse terms; retain attribution where required. The committed
  supplemental files do not include page/revision-level lineage.
- Wikidata reduced structured facts: https://www.wikidata.org/wiki/Wikidata:Licensing
  (CC0). QIDs and entity revisions are retained in the metadata snapshot.
- Japan Post UTF-8 postal address/readings:
  https://www.post.japanpost.jp/service/search/zipcode/download/utf-zip.html
  https://www.post.japanpost.jp/service/search/zipcode/download/readme.html
- Additional reviewed reading/category facts: source URLs are listed in
  src/main/dictionary-quality/confirmed.tsv and the compressed audit report.

Dictionary categories and audit data are build-time metadata. Serialized tokens
retain the existing LOUDS triplet format; no category labels are added to entries.
The Kotlin implementation is distributed under the repository's LICENSE.
