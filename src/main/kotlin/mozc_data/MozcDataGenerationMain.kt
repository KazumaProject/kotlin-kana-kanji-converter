package mozc_data

import java.nio.file.Path

fun main(args: Array<String>) {
    val projectRoot = Path.of(System.getProperty("user.dir"))
    val output = args.firstOrNull { it.startsWith("--output=") }
        ?.substringAfter("=")
        ?.let(Path::of)
        ?: projectRoot.resolve("build/generated/mozc-data/mozc.data")
    val source = args.firstOrNull { it.startsWith("--mozcSrcDir=") }?.substringAfter("=")
    val builder = MozcOfficialDataBuilder(projectRoot)
    builder.build(builder.resolveSourceDirectory(source), output)
}
