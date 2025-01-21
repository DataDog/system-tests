target "runner" {
    dockerfile = "utils/build/docker/runner.Dockerfile"
}

target "default" {
    dockerfile = "bake.Dockerfile"
    contexts = {
        "runner" = "target:runner"
    }

    output = ["output/"]
}