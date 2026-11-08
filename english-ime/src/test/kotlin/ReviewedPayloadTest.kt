import conversion.readPayload
import java.io.InvalidClassException
import java.io.ObjectOutputStream
import java.io.RandomAccessFile
import kotlin.io.path.createTempDirectory
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs

class ReviewedPayloadTest {
    @Test
    fun acceptsLargeRealPrimitiveArraysButRejectsTruncatedAllocationClaimsAndOtherTypes() {
        val root=createTempDirectory("reviewed-payload").toFile()
        try {
            val file=root.resolve("payload.dat")
            ObjectOutputStream(file.outputStream()).use { it.writeObject(CharArray(4_000_001) { 'x' }) }
            assertEquals(4_000_001,file.readPayload { (it.readObject() as CharArray).size })
            RandomAccessFile(file,"rw").use { it.setLength(32) }
            val rejected=assertFailsWith<IllegalArgumentException> { file.readPayload { it.readObject() } }
            assertIs<InvalidClassException>(rejected.cause)
            ObjectOutputStream(file.outputStream()).use { it.writeObject(arrayListOf("unsupported")) }
            assertIs<InvalidClassException>(assertFailsWith<IllegalArgumentException> {
                file.readPayload { it.readObject() }
            }.cause)
            RandomAccessFile(file,"rw").use { it.setLength(128L*1024*1024+1) }
            assertFailsWith<IllegalArgumentException> { file.readPayload { it.readObject() } }
        } finally { root.deleteRecursively() }
    }
}
