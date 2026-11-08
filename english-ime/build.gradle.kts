plugins {
    kotlin("jvm")
    application
}

repositories {
    mavenCentral()
}

kotlin {
    jvmToolchain(17)
}

application {
    mainClass.set("EnglishImeCliKt")
}

// The complete supplemental lexicon exceeds small/container JVM ergonomics.
tasks.named<JavaExec>("run") {
    maxHeapSize = "4g"
}

dependencies {
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.2")
    testImplementation(kotlin("test"))
}

tasks.test {
    useJUnitPlatform()
    inputs.dir(layout.projectDirectory.dir("data/grammar"))
    inputs.file(layout.projectDirectory.file("data/1-grams_score_cost_pos_combined_with_ner.zip"))
}

tasks.register<JavaExec>("verifySupplementAssets") {
    group = "verification"
    description = "Checks every original and supplemental entry against generated assets."
    dependsOn(tasks.testClasses)
    classpath = sourceSets.test.get().runtimeClasspath
    mainClass.set("conversion.VerifySupplementAssetsKt")
    maxHeapSize = "4g"
    doFirst {
        args(
            project.file(providers.gradleProperty("englishBaseAssets").get()).absolutePath,
            project.file(providers.gradleProperty("englishExtendedAssets").get()).absolutePath,
            project.file(providers.gradleProperty("englishSupplementEntries")
                .getOrElse(layout.projectDirectory.file("data/supplement/entries.tsv").asFile.absolutePath)).absolutePath,
        )
        providers.gradleProperty("englishRuntimeAssets").orNull?.let { args(project.file(it).absolutePath) }
    }
}
