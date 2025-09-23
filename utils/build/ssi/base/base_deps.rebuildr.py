from rebuildr.descriptor import Descriptor, ArgsInput, FileInput, ImageTarget, Inputs

image = Descriptor(
    targets=[
        ImageTarget(
            dockerfile="base_deps.Dockerfile",
            repository="base_deps",
            tag="latest",
            # platform="linux/arm64",
        )
    ],
    inputs=Inputs(
        files=[
            FileInput(path="install_os_deps.sh", target_path="base/install_os_deps.sh"),
            FileInput(path="healthcheck.sh",target_path= "base/healthcheck.sh" ),
            FileInput(path="tested_components.sh", target_path="base/tested_components.sh"),
        ],
        builders =[
            ArgsInput(key="BASE_IMAGE", default="ubuntu:22.04")
        ]
    ),
)