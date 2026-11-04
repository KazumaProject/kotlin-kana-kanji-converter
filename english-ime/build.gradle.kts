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
    testImplementation(kotlin("test"))
}

tasks.test {
    useJUnitPlatform()
    inputs.file(layout.projectDirectory.file("data/1-grams_score_cost_pos_combined_with_ner.zip"))
}
