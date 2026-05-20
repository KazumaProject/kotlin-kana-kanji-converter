package mozc

import com.kazumaproject.mozc.ConnectionMatrix
import com.kazumaproject.mozc.ConnectionMatrixIO
import com.kazumaproject.mozc.ConnectionMatrixParser
import java.nio.ByteBuffer
import java.nio.file.Files
import java.nio.file.Path
import kotlin.io.path.writeText
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class ConnectionMatrixTest {
    private val repoRoot: Path = Path.of(System.getProperty("user.dir"))
    private val connectionPath: Path = repoRoot.resolve("src/main/resources/connection_single_column.txt")

    @Test
    fun parsesBundledConnectionMatrixHeaderAndDataCount() {
        val matrix = realConnectionMatrix()

        assertEquals(2672, matrix.size)
        assertEquals(2672 * 2672, matrix.costs.size)
    }

    @Test
    fun rejectsShortConnectionMatrix() {
        val path = writeConnection("2\n1\n2\n3\n")

        val error = assertFailsWith<IllegalStateException> { ConnectionMatrixParser.parse(path) }
        assertTrue(error.message!!.contains("expected count=4"))
        assertTrue(error.message!!.contains("actual count=3"))
        assertTrue(error.message!!.contains(path.toString()))
    }

    @Test
    fun rejectsLongConnectionMatrix() {
        val path = writeConnection("2\n1\n2\n3\n4\n5\n")

        val error = assertFailsWith<IllegalStateException> { ConnectionMatrixParser.parse(path) }
        assertTrue(error.message!!.contains("expected count=4"))
        assertTrue(error.message!!.contains("actual count=5"))
    }

    @Test
    fun rejectsInvalidCostWithLineNumber() {
        val path = writeConnection("2\n1\nnot-a-number\n3\n4\n")

        val error = assertFailsWith<IllegalStateException> { ConnectionMatrixParser.parse(path) }
        assertTrue(error.message!!.contains("line number=3"))
        assertTrue(error.message!!.contains("not-a-number"))
    }

    @Test
    fun rejectsCostOutsideShortRange() {
        val path = writeConnection("2\n1\n2\n40000\n4\n")

        val error = assertFailsWith<IllegalStateException> { ConnectionMatrixParser.parse(path) }
        assertTrue(error.message!!.contains("outside Short range"))
        assertTrue(error.message!!.contains("line number=4"))
    }

    @Test
    fun restoresMatrixSizeFromRawConnectionIdDat() {
        val path = Files.createTempFile("connectionId-", ".dat")
        val bytes = ByteBuffer.allocate(8)
            .putShort(10)
            .putShort(20)
            .putShort(30)
            .putShort(40)
            .array()
        Files.write(path, bytes)

        val matrix = ConnectionMatrixIO.read(path)

        assertEquals(2, matrix.size)
        assertEquals(30, matrix.getCost(1, 0))
    }

    @Test
    fun rejectsRawConnectionIdDatWhenShortCountIsNotSquare() {
        val path = Files.createTempFile("connectionId-invalid-", ".dat")
        val bytes = ByteBuffer.allocate(6)
            .putShort(1)
            .putShort(2)
            .putShort(3)
            .array()
        Files.write(path, bytes)

        val error = assertFailsWith<IllegalStateException> { ConnectionMatrixIO.read(path) }
        assertTrue(error.message!!.contains("short count=3"))
        assertTrue(error.message!!.contains("perfect square"))
    }

    @Test
    fun getCostUsesMatrixSizeAndRejectsOutOfRangeIds() {
        val matrix = ConnectionMatrix(3, shortArrayOf(0, 1, 2, 3, 4, 5, 6, 7, 8))

        assertEquals(5, matrix.getCost(1, 2))
        assertFailsWith<IllegalArgumentException> { matrix.getCost(3, 0) }
        assertFailsWith<IllegalArgumentException> { matrix.getCost(0, 3) }
    }

    private fun writeConnection(content: String): Path {
        val path = Files.createTempFile("connection-", ".txt")
        path.writeText(content)
        return path
    }

    private fun realConnectionMatrix(): ConnectionMatrix = realMatrix

    companion object {
        private val realMatrix: ConnectionMatrix by lazy {
            val repoRoot = Path.of(System.getProperty("user.dir"))
            ConnectionMatrixParser.parse(repoRoot.resolve("src/main/resources/connection_single_column.txt"))
        }
    }
}
