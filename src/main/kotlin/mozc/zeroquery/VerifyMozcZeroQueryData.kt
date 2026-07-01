package com.kazumaproject.mozc.zeroquery

import java.nio.file.Files
import java.nio.file.Path

object VerifyMozcZeroQueryData {
    @JvmStatic
    fun main(args: Array<String>) {
        val inputDir = parseInputDir(args.toList())
        val summary = verify(inputDir)
        println("Verified Mozc zero query data: input_dir=$inputDir")
        println("zero_query_token.data bytes=${summary.zeroQueryTokenBytes} entries=${summary.zeroQueryTokenEntries}")
        println("zero_query_string.data bytes=${summary.zeroQueryStringBytes}")
        println("zero_query_number_token.data bytes=${summary.zeroQueryNumberTokenBytes} entries=${summary.zeroQueryNumberTokenEntries}")
        println("zero_query_number_string.data bytes=${summary.zeroQueryNumberStringBytes}")
        println("custom lookup: \"服を\" -> ${summary.customLookupValues}")
    }

    fun verify(inputDir: Path): ZeroQueryVerificationSummary {
        val zeroQueryToken = readRequiredNonEmpty(inputDir.resolve("zero_query_token.data"))
        val zeroQueryString = readRequiredNonEmpty(inputDir.resolve("zero_query_string.data"))
        val zeroQueryNumberToken = readRequiredNonEmpty(inputDir.resolve("zero_query_number_token.data"))
        val zeroQueryNumberString = readRequiredNonEmpty(inputDir.resolve("zero_query_number_string.data"))

        val zeroQueryDict = ZeroQueryDict(zeroQueryToken, zeroQueryString)
        val zeroQueryNumberDict = ZeroQueryDict(zeroQueryNumberToken, zeroQueryNumberString)

        requireLookup(zeroQueryDict, "@", "gmail.com")
        requireLookup(zeroQueryDict, "ありがとう", "。")
        requireLookup(zeroQueryDict, "服を", "着る")
        requireLookup(zeroQueryNumberDict, "12", "月")
        requireLookup(zeroQueryNumberDict, "default", "年")

        return ZeroQueryVerificationSummary(
            zeroQueryTokenBytes = zeroQueryToken.size,
            zeroQueryStringBytes = zeroQueryString.size,
            zeroQueryNumberTokenBytes = zeroQueryNumberToken.size,
            zeroQueryNumberStringBytes = zeroQueryNumberString.size,
            zeroQueryTokenEntries = zeroQueryDict.entryCount,
            zeroQueryNumberTokenEntries = zeroQueryNumberDict.entryCount,
            customLookupValues = zeroQueryDict.lookup("服を").map { it.value },
        )
    }

    private fun parseInputDir(args: List<String>): Path {
        if (args.isEmpty()) {
            return Path.of("src/main/resources")
        }
        val values = parseFlagMap(args, setOf("--input_dir"))
        return Path.of(values.getValue("--input_dir"))
    }

    private fun readRequiredNonEmpty(path: Path): ByteArray {
        if (!Files.isRegularFile(path)) {
            error("Missing zero query binary file: file path=$path")
        }
        val bytes = Files.readAllBytes(path)
        if (bytes.isEmpty()) {
            error("Empty zero query binary file: file path=$path")
        }
        return bytes
    }

    private fun requireLookup(dict: ZeroQueryDict, key: String, expectedValue: String) {
        val values = dict.lookup(key).map { it.value }
        require(expectedValue in values) {
            "Zero query lookup failed: key='$key', expected value='$expectedValue', actual values=$values"
        }
    }
}

data class ZeroQueryVerificationSummary(
    val zeroQueryTokenBytes: Int,
    val zeroQueryStringBytes: Int,
    val zeroQueryNumberTokenBytes: Int,
    val zeroQueryNumberStringBytes: Int,
    val zeroQueryTokenEntries: Int,
    val zeroQueryNumberTokenEntries: Int,
    val customLookupValues: List<String>,
)
