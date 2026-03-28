plugins {
    kotlin("jvm") version "1.9.21"
    kotlin("plugin.serialization") version "1.9.22"
    id("application")
}

group = "com.kazumaproject"
version = "1.0-SNAPSHOT"

repositories {
    mavenCentral()
}

dependencies {
    testImplementation("org.jetbrains.kotlin:kotlin-test")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.9.0-RC.2")
}

tasks.test {
    useJUnitPlatform()
}

tasks.register<Test>("dictionaryBuildTest") {
    description = "Runs the full real-dictionary build integration test."
    group = "verification"
    useJUnitPlatform()
    maxHeapSize = "4g"
    systemProperty("dictionaryBuild.full", "true")
    filter {
        includeTestsMatching("*DictionaryBuildIntegrationTest")
    }
}

tasks.register<Test>("updateDictionaryBuildBaseline") {
    description = "Runs the full dictionary build test and updates the committed performance baseline."
    group = "verification"
    useJUnitPlatform()
    maxHeapSize = "4g"
    systemProperty("dictionaryBuild.full", "true")
    systemProperty("dictionaryBuild.updateBaseline", "true")
    filter {
        includeTestsMatching("*DictionaryBuildIntegrationTest")
    }
}

kotlin {
    jvmToolchain(17)
}

application {
    mainClass.set("com.kazumaproject.MainKt")
}

tasks.register<JavaExec>("runMozcUT") {
    mainClass.set("com.kazumaproject.MozcUTKt")
    classpath = sourceSets["main"].runtimeClasspath
}

tasks.register<JavaExec>("runMozcUTWiki") {
    mainClass.set("com.kazumaproject.MozcUTWikiKt")
    classpath = sourceSets["main"].runtimeClasspath
}

tasks.register<JavaExec>("runMozcUTNeologd") {
    mainClass.set("com.kazumaproject.MozcUTNeologdKt")
    classpath = sourceSets["main"].runtimeClasspath
}

tasks.register<JavaExec>("runMozcUTWikiNeologdCommon") {
    mainClass.set("com.kazumaproject.MozcUTWikiNeologdCommonKt")
    classpath = sourceSets["main"].runtimeClasspath
}
