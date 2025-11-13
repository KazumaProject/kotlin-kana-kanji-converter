package com.kazumaproject

import com.kazumaproject.graph.Node

object Other {
    const val NUM_OF_CONNECTION_ID = 2671
    const val NOUN_PART_OF_SPEECH_ID = (1852).toShort()
    const val ALPHABET_PART_OF_SPEECH_ID = (2642).toShort()
    const val PROPER_NOUN_PART_OF_SPEECH_ID = (1921).toShort()
    val BOS = Node(
        l = 0,
        r = 0,
        score = 0,
        f = 0,
        g = 0,
        tango = "BOS",
        len = 0,
        0
    )
}
