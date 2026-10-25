package com.kazumaproject.classification

import java.io.File
import java.security.MessageDigest

internal object CrimeOffenderCandidateKeys {
    private const val FILE_NAME = "crime-offender-exclusion-keys.sha256"

    fun load(directory: File, required: Boolean = true): Set<String> {
        val file = File(directory, FILE_NAME)
        if (!file.isFile && !required) return emptySet()
        require(file.isFile) { "Missing crime-offender exclusion key list" }
        val keys = file.readLines(Charsets.US_ASCII)
        require(keys.isNotEmpty() && keys.size == keys.toSet().size &&
            keys.all { it.matches(Regex("[0-9a-f]{64}")) }) {
            "Malformed crime-offender exclusion key list"
        }
        return keys.toSet()
    }

    fun key(reading: String, surface: String): String = MessageDigest.getInstance("SHA-256")
        .digest((reading + "\u0000" + surface).toByteArray(Charsets.UTF_8))
        .joinToString("") { "%02x".format(it) }
}
