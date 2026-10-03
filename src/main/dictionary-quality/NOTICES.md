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

## JMdict / JMnedict reference data and derived dictionary data

This version uses JMdict and the JMnedict/ENAMDICT proper-name dictionary,
copyright James William BREEN and the Electronic
Dictionary Research and Development Group, as a reference for existing
MozcUT/Wiki/NEologd candidate spelling/reading pairs and sense classifications.
No additional JMdict headwords are injected into the supplemental inputs.
The matched facts and dictionaries incorporating these derived facts are
provided under CC BY-SA 4.0, with attribution and changes described in this
notice and manifest. This does not change the Kotlin source-code license.

Source: https://www.edrdg.org/pub/Nihongo/JMdict_e.gz
Proper-name source: https://www.edrdg.org/pub/Nihongo/JMnedict.xml.gz
Documentation: https://www.edrdg.org/jmdict/edict_doc.html
Proper-name documentation: https://www.edrdg.org/enamdict/enamdict_doc.html
License statement: https://www.edrdg.org/edrdg/licence.html
License: https://creativecommons.org/licenses/by-sa/4.0/

Copies of the EDRDG license statement and CC BY-SA 4.0 legal code accompany this
package as LICENSE-JMDICT.html and LICENSE-CC-BY-SA-4.0.txt. Input reference
hashes are retained in the metadata snapshot. Extracted facts keep JMdict entry
and sense identifiers, reading/spelling restrictions, POS and field tags.
JMnedict facts additionally retain entry/translation identifiers, restricted
readings and name types. Changes: select existing input pairs, separate reading
verification from semantic classification, and normalize only with source-bound
component evidence. Reference editions and SHA-256 hashes are pinned in the
research ledger and reduced snapshot; research bulk imports can update editions.

The metadata snapshot includes CC0 Wikidata and Japan Post reference facts
alongside JMdict-derived facts. Redistribution of the combined derived snapshot
must preserve the JMdict attribution and CC BY-SA terms; notices and license
copies are published with the snapshot Release.

## Additional name-specific reading references

Individually checked facts retain their spelling/reading pair and source URL in
confirmed.tsv; research method and date are recorded in reading-research.json.
Wikipedia contributors provide several name-specific pronunciation facts under
CC BY-SA 4.0 (https://ja.wikipedia.org/wiki/Wikipedia:著作権).
Changes: extracted factual spelling/pronunciation/name-role correspondences only.
The source URLs and revisions identify the contributing articles. Full article
and official-page bodies remain in the local research cache. Reduced snapshots
keep factual name/reading bindings and short quotations needed for those facts,
plus hashes of context used for classification; full page prose is not bundled.
The combined derived dictionary is distributed with the attribution and
CC BY-SA 4.0 license above.
