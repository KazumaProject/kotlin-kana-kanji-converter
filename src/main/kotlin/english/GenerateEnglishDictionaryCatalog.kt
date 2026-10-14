package com.kazumaproject.english

import java.nio.file.Files
import java.nio.file.Path
import java.util.Locale

/** Human-readable snapshot of the same adopted entries used by the binary builder. */
fun main(args: Array<String>) {
    val source = loadEnglishDictionarySource(args)
    fun requiredPath(option: String) = Path.of(englishOption(args, option) ?: error("Missing required option: $option"))
    val output = requiredPath("--output")
    val bySurface = source.runtimeEntries.groupBy { it.tango }
    val singleWords = bySurface.keys.count { it.none(Char::isWhitespace) }
    val foldedSingleWords = bySurface.keys.filter { it.none(Char::isWhitespace) }.map { it.lowercase(Locale.ROOT) }.toSet().size
    val sortedSurfaces = bySurface.keys.sortedWith(compareBy({ it.lowercase(Locale.ROOT) }, { it }))
    val sections = sortedSurfaces.groupBy { it.first().uppercaseChar().takeIf { c -> c in 'A'..'Z' }?.toString() ?: "その他" }
    output.toAbsolutePath().parent?.let(Files::createDirectories)
    Files.newBufferedWriter(output).use { writer ->
        writer.appendLine("# かな→英語辞書の収録一覧")
        writer.appendLine()
        writer.appendLine("上流辞書と補完TSVを統合し、品質検査・重複排除後に採用した全英語表記と読みです。補完TSVだけの一覧ではありません。")
        writer.appendLine("同じ英語表記の別読みは同じ行にまとめ、大小文字が異なる表記は区別しています。括弧内は各読みの登録コストです。")
        writer.appendLine()
        writer.appendLine("- 読みと表記の組: ${source.runtimeEntries.size}")
        writer.appendLine("- 読みの種類: ${source.runtimeEntries.map { it.yomi }.toSet().size}")
        writer.appendLine("- 英語表記の種類（大小文字を区別）: ${bySurface.size}")
        writer.appendLine("- 単独表記: $singleWords（大小文字をまとめると $foldedSingleWords）")
        writer.appendLine("- 空白を含む複合表記: ${bySurface.size - singleWords}")
        writer.appendLine()
        writer.appendLine("表記には略語・既存の語形・複合語も含むため、種類数は基本見出し語数とは異なります。コストは登録値で、実端末の表示・最終順位の確認結果ではありません。")
        writer.appendLine("この一覧は以下の入力時点のスナップショットです。別の上流配布では収録内容が変わる場合があります。")
        writer.appendLine()
        for ((label, option) in listOf("上流辞書" to "--input", "補完TSV" to "--supplement", "共有POS定義" to "--id-def")) {
            writer.appendLine("- $label SHA-256: `${EnglishWordCoverage.sha256(requiredPath(option))}`")
        }
        writer.appendLine()
        writer.appendLine("更新: `./gradlew generateEnglishDictionaryCatalog`（上流辞書とid.defを準備）。一覧の採用結果は辞書生成と共通です。手作業でこの表へ単語を追加せず、元の入力を更新して再生成してください。")
        writer.appendLine("出典・ライセンスは [LICENSE-DATA.md](../LICENSE-DATA.md)、作成手順は [english-dictionary.md](english-dictionary.md) を参照してください。")
        writer.appendLine()
        writer.appendLine(sections.keys.joinToString(" · ") { "[$it](#${if (it == "その他") it else it.lowercase(Locale.ROOT)})" })
        sections.forEach { (section, surfaces) ->
            writer.appendLine()
            writer.appendLine("## $section")
            writer.appendLine()
            writer.appendLine("| 英語表記 | かな読み（コスト） |")
            writer.appendLine("| --- | --- |")
            surfaces.forEach { surface ->
                val readings = bySurface.getValue(surface).sortedWith(compareBy({ it.cost }, { it.yomi }))
                    .joinToString("、") { "${it.yomi} (${it.cost})" }
                writer.appendLine("| $surface | $readings |")
            }
        }
    }
    println("Wrote English dictionary catalog: surfaces=${bySurface.size}, pairs=${source.runtimeEntries.size}, output=$output")
}
