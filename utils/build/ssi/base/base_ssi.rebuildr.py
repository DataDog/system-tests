import os
from rebuildr.descriptor import Descriptor, ArgsInput, FileInput, ImageTarget, Inputs

image = Descriptor(
    targets=[
        ImageTarget(
            dockerfile="base_ssi.Dockerfile",
            repository=os.getenv("IMAGE_REPOSITORY", "base_ssi"),
            tag="latest",
            # platform="linux/arm64",
        )
    ],
    inputs=Inputs(
        files=[
            FileInput(path="install_script_ssi.sh", target_path="base/install_script_ssi.sh"),
        ],
        builders=[
            ArgsInput(key="BASE_IMAGE", default="ubuntu:22.04"),
            ArgsInput(key="DD_API_KEY", default="deadbeef"),
            ArgsInput(key="DD_LANG", default=""),
            ArgsInput(key="SSI_ENV", default=""),
            ArgsInput(key="DD_INSTALLER_LIBRARY_VERSION", default=""),
            ArgsInput(key="DD_INSTALLER_INJECTOR_VERSION", default=""),
            ArgsInput(key="DD_APPSEC_ENABLED", default=""),
        ],
    ),
)
