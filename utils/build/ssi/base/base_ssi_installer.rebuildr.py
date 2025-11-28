import os
from rebuildr.descriptor import Descriptor, ArgsInput, FileInput, ImageTarget, Inputs

image = Descriptor(
    targets=[
        ImageTarget(
            dockerfile="base_ssi_installer.Dockerfile",
            repository=os.getenv("IMAGE_REPOSITORY", "base_ssi_installer"),
            tag="latest",
            # platform="linux/arm64",
        )
    ],
    inputs=Inputs(
        files=[
            FileInput(path="install_script_ssi_installer.sh", target_path="base/install_script_ssi_installer.sh"),
        ],
        builders=[
            ArgsInput(key="BASE_IMAGE", default="ubuntu:22.04"),
            ArgsInput(key="DD_API_KEY", default="xxxxxxxxxx"),
        ],
    ),
)
