pluginManagement {
    repositories {
        System.getenv("MAVEN_REPOSITORY_PROXY")?.let { maven(it) } ?: gradlePluginPortal()
    }
    resolutionStrategy {
        eachPlugin {
            if (requested.id.id == "org.springframework.boot") {
                useModule("org.springframework.boot:spring-boot-gradle-plugin:${requested.version}")
            }
        }
    }
}

rootProject.name = "k8s-lib-injection-app"
