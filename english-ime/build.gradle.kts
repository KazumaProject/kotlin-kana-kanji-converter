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

dependencies {
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.2")
    testImplementation(kotlin("test"))
}

tasks.test {
    useJUnitPlatform()
    inputs.dir(layout.projectDirectory.dir("data/grammar"))
    inputs.file(layout.projectDirectory.file("data/1-grams_score_cost_pos_combined_with_ner.zip"))
}
