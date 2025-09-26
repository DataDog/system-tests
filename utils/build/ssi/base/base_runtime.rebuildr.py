import os
from rebuildr.descriptor import Descriptor, ArgsInput, FileInput, ImageTarget, Inputs

image = Descriptor(
    targets=[
        ImageTarget(
            dockerfile="base_runtime.Dockerfile",
            repository=os.getenv("IMAGE_REPOSITORY", "base_runtime"),
            tag="latest",
            # platform="linux/arm64",
        )
    ],
    inputs=Inputs(
        files=[
            FileInput(
                path=f"{os.getenv('DD_LANG')}_install_runtimes.sh",
                target_path=f"base/{os.getenv('DD_LANG')}_install_runtimes.sh",
            ),
        ],
        builders=[
            ArgsInput(key="BASE_IMAGE", default="ubuntu:22.04"),
            ArgsInput(key="DD_LANG", default=""),
            ArgsInput(key="RUNTIME_VERSIONS", default=""),
        ],
    ),
)
