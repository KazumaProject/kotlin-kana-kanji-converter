package mozc_data

import java.nio.ByteBuffer

class MozcDataManager(
    private val sections: Map<String, MozcDataSection>,
    expectedVersion: String? = null,
) {
    init {
        validateRequiredSections()
        validateUsageSections()
        val version = version()
        require(version.isNotEmpty()) { "mozc.data version section is empty" }
        if (expectedVersion != null) {
            require(version == expectedVersion) {
                "mozc.data version mismatch: expected=$expectedVersion actual=$version"
            }
        }
    }

    fun section(name: String): ByteBuffer =
        sections[name]?.data?.asReadOnlyBuffer()?.order(java.nio.ByteOrder.LITTLE_ENDIAN)
            ?: error("Missing mozc.data section: $name")

    fun metadata(name: String): MozcDataSection =
        sections[name] ?: error("Missing mozc.data section: $name")

    fun version(): String =
        sections["version"]?.data?.toUtf8String()?.trimEnd('\u0000', '\r', '\n')
            ?: error("Missing mozc.data section: version")

    fun hasUsageDictionary(): Boolean = UsageSections.all { it in sections }

    private fun validateRequiredSections() {
        val missing = RequiredSections.filterNot { it in sections }
        require(missing.isEmpty()) { "mozc.data is missing required sections: ${missing.joinToString()}" }
    }

    private fun validateUsageSections() {
        val present = UsageSections.filter { it in sections }
        require(present.isEmpty() || present.size == UsageSections.size) {
            "mozc.data usage dictionary sections are incomplete: present=${present.joinToString()}, required=${UsageSections.joinToString()}"
        }
    }

    companion object {
        val RequiredSections: List<String> = listOf(
            "pos_matcher",
            "user_pos_token",
            "user_pos_string",
            "coll",
            "cols",
            "conn",
            "dict",
            "sugg",
            "posg",
            "bdry",
            "segmenter_sizeinfo",
            "segmenter_ltable",
            "segmenter_rtable",
            "segmenter_bitarray",
            "counter_suffix",
            "suffix_key",
            "suffix_value",
            "suffix_token",
            "reading_correction_value",
            "reading_correction_error",
            "reading_correction_correction",
            "symbol_token",
            "symbol_string",
            "emoticon_token",
            "emoticon_string",
            "emoji_token",
            "emoji_string",
            "single_kanji_token",
            "single_kanji_string",
            "single_kanji_variant_type",
            "single_kanji_variant_token",
            "single_kanji_variant_string",
            "single_kanji_noun_prefix_token",
            "single_kanji_noun_prefix_string",
            "zero_query_token_array",
            "zero_query_string_array",
            "zero_query_number_token_array",
            "zero_query_number_string_array",
            "a11y_description_token",
            "a11y_description_string",
            "version",
        )

        val UsageSections: List<String> = listOf(
            "usage_base_conjugation_suffix",
            "usage_conjugation_suffix",
            "usage_conjugation_index",
            "usage_item_array",
            "usage_string_array",
        )
    }
}
