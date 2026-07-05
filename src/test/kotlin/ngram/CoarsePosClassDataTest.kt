package com.kazumaproject.ngram

import java.nio.file.Files
import kotlin.io.path.writeText
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class CoarsePosClassDataTest {
    @Test
    fun mapperUsesIdDefPos1() {
        assertEquals(ContextualCorrectionCoarseClass.NOUN, CoarsePosClassMapper.classifyIdDefName("名詞,一般,*,*,*,*,*"))
        assertEquals(ContextualCorrectionCoarseClass.PARTICLE, CoarsePosClassMapper.classifyIdDefName("助詞,格助詞,一般,*,*,*,*"))
        assertEquals(ContextualCorrectionCoarseClass.VERB, CoarsePosClassMapper.classifyIdDefName("動詞,自立,*,*,五段・カ行イ音便,基本形,*"))
        assertEquals(ContextualCorrectionCoarseClass.AUX, CoarsePosClassMapper.classifyIdDefName("助動詞,*,*,*,特殊・デス,基本形,*"))
        assertEquals(ContextualCorrectionCoarseClass.SYMBOL, CoarsePosClassMapper.classifyIdDefName("記号,一般,*,*,*,*,*"))
        assertEquals(ContextualCorrectionCoarseClass.UNKNOWN, CoarsePosClassMapper.classifyIdDefName("副詞,一般,*,*,*,*,*"))
    }

    @Test
    fun binaryRoundTripClassifiesLeftIds() {
        val dir = Files.createTempDirectory("coarse-pos-class-")
        try {
            val idDef = writeSampleIdDef(dir)
            val build = CoarsePosClassBuilder.build(idDef)
            val dictionary = CoarsePosClassDataReader().readBytes(CoarsePosClassDataWriter().toByteArray(build))

            assertEquals(7, dictionary.idCount)
            assertEquals(ContextualCorrectionCoarseClass.UNKNOWN, dictionary.classify(0))
            assertEquals(ContextualCorrectionCoarseClass.NOUN, dictionary.classify(1))
            assertEquals(ContextualCorrectionCoarseClass.PARTICLE, dictionary.classify(2))
            assertEquals(ContextualCorrectionCoarseClass.VERB, dictionary.classify(3))
            assertEquals(ContextualCorrectionCoarseClass.AUX, dictionary.classify(4))
            assertEquals(ContextualCorrectionCoarseClass.SYMBOL, dictionary.classify(5))
            assertEquals(ContextualCorrectionCoarseClass.UNKNOWN, dictionary.classify(6))
            assertEquals(ContextualCorrectionCoarseClass.UNKNOWN, dictionary.classify(999))
        } finally {
            dir.toFile().deleteRecursively()
        }
    }

    @Test
    fun classifyShortFallsBackToRightIdOnlyWhenLeftIsUnknown() {
        val dir = Files.createTempDirectory("coarse-pos-class-fallback-")
        try {
            val idDef = writeSampleIdDef(dir)
            val table = CoarsePosClassDataReader().readBytes(
                CoarsePosClassDataWriter().toByteArray(CoarsePosClassBuilder.build(idDef))
            )

            assertEquals(
                ContextualCorrectionCoarseClass.NOUN,
                table.classify(1.toShort(), 3.toShort()),
            )
            assertEquals(
                ContextualCorrectionCoarseClass.VERB,
                table.classify(6.toShort(), 3.toShort()),
            )
        } finally {
            dir.toFile().deleteRecursively()
        }
    }

    @Test
    fun generatorVerifierAndManifestRoundTrip() {
        val dir = Files.createTempDirectory("coarse-pos-class-generate-")
        try {
            val idDef = writeSampleIdDef(dir)
            val data = dir.resolve("coarse_pos_class.data")
            val manifest = dir.resolve("coarse_pos_class_manifest.json")

            val generated = CoarsePosClassGenerator.generate(idDef, data, manifest)
            val verified = CoarsePosClassVerifier.verify(idDef, data)

            assertEquals(COARSE_POS_CLASS_FORMAT, generated.format)
            assertEquals(7, generated.idDefEntryCount)
            assertEquals(7, verified.verifiedIdCount)
            assertEquals(1, generated.classCounts.getValue(ContextualCorrectionCoarseClass.NOUN))
            assertEquals(2, generated.classCounts.getValue(ContextualCorrectionCoarseClass.UNKNOWN))
            val manifestJson = Files.readString(manifest)
            assertTrue(manifestJson.contains("\"mappingPolicy\": \"LEFT_ID_POS1_V1\""))
            assertTrue(manifestJson.contains("\"sourceChecksum\""))
        } finally {
            dir.toFile().deleteRecursively()
        }
    }

    @Test
    fun emptyTableReturnsUnknown() {
        assertEquals(ContextualCorrectionCoarseClass.UNKNOWN, EmptyCoarsePosClassTable.classify(0))
        assertEquals(ContextualCorrectionCoarseClass.UNKNOWN, EmptyCoarsePosClassTable.classify(1.toShort(), 2.toShort()))
    }

    @Test
    fun generatedBytesAreDeterministic() {
        val dir = Files.createTempDirectory("coarse-pos-class-deterministic-")
        try {
            val idDef = writeSampleIdDef(dir)
            val build = CoarsePosClassBuilder.build(idDef)

            val bytes1 = CoarsePosClassDataWriter().toByteArray(build)
            val bytes2 = CoarsePosClassDataWriter().toByteArray(build)

            assertContentEquals(bytes1, bytes2)
        } finally {
            dir.toFile().deleteRecursively()
        }
    }

    private fun writeSampleIdDef(dir: java.nio.file.Path): java.nio.file.Path {
        val idDef = dir.resolve("id.def")
        idDef.writeText(
            """
            0 BOS/EOS,*,*,*,*,*,*
            1 名詞,一般,*,*,*,*,*
            2 助詞,格助詞,一般,*,*,*,*
            3 動詞,自立,*,*,五段・カ行イ音便,基本形,*
            4 助動詞,*,*,*,特殊・デス,基本形,*
            5 記号,一般,*,*,*,*,*
            6 副詞,一般,*,*,*,*,*
            """.trimIndent() + "\n"
        )
        return idDef
    }
}
