import org.springframework.boot.gradle.tasks.bundling.BootBuildImage
import software.amazon.awssdk.services.ecr.EcrClient
import software.amazon.awssdk.services.ecr.model.AuthorizationData
import java.util.Base64

buildscript {
    repositories {
        mavenCentral()
    }
    dependencies {
        classpath(platform("software.amazon.awssdk:bom:2.20.121"))
        classpath("software.amazon.awssdk:ecr")
        classpath("software.amazon.awssdk:sts") // sts is required to use roleArn in aws profiles
    }
}

plugins {
    id("org.springframework.boot") version "2.7.2"
    id("io.spring.dependency-management") version "1.0.11.RELEASE"
    id("java")
}

group = "com.example"
version = "0.0.1-SNAPSHOT"
java.sourceCompatibility = JavaVersion.VERSION_11

dependencies {
    implementation("org.springframework.fu:spring-fu-jafu:0.5.1")
    implementation("org.springframework.boot:spring-boot-starter-webflux")

    testImplementation("org.springframework.boot:spring-boot-starter-test")
}

repositories {
    mavenLocal()
    mavenCentral()
    maven("https://repo.spring.io/milestone")
    maven("https://repo.spring.io/snapshot")
}

tasks.withType<Test> {
    useJUnitPlatform()
}

val dockerImageRepo: String? by project
val resolvedDockerImageRepo: String = dockerImageRepo ?: "docker.io/" + System.getenv("DOCKER_USERNAME") + "/dd-lib-java-init-test-app"
val dockerImageTag: String by project
val useDockerProxy: String? by project

tasks.named<BootBuildImage>("bootBuildImage") {
    imageName = "${resolvedDockerImageRepo}:${dockerImageTag}"

    if (useDockerProxy == null) {
        builder = "paketobuildpacks/builder-jammy-java-tiny:0.0.11"
        runImage = "paketobuildpacks/run-jammy-tiny:0.2.55"
    } else {
        // Use dockerhub mirror
        builder = "669783387624.dkr.ecr.us-east-1.amazonaws.com/dockerhub/paketobuildpacks/builder-jammy-java-tiny:0.0.11"
        runImage = "669783387624.dkr.ecr.us-east-1.amazonaws.com/dockerhub/paketobuildpacks/run-jammy-tiny:0.2.55"

        // Setup authentication
        // https://stackoverflow.com/questions/65320552/publish-docker-images-using-spring-boot-plugin-without-credentials/76898025#76898025
        val ecrClient = EcrClient.builder().build()
        val base64Token = ecrClient
                    .getAuthorizationToken()
                    .authorizationData()[0]
                    .authorizationToken()
        val auth = String(Base64.getDecoder().decode(base64Token)).split(":")

        docker {
            builderRegistry {
                username = auth[0]
                password = auth[1]
            }
        }
    }
}
