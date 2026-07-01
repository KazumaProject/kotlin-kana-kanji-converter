package com.kazumaproject.mozc.zeroquery

enum class ZeroQueryType(val code: Int) {
    ZERO_QUERY_NONE(0),
    ZERO_QUERY_NUMBER_SUFFIX(1),
    ZERO_QUERY_EMOTICON(2),
    ZERO_QUERY_EMOJI(3),
    ;

    companion object {
        fun fromCode(code: Int): ZeroQueryType =
            entries.firstOrNull { it.code == code }
                ?: error("Invalid zero query type: type=$code")
    }
}
