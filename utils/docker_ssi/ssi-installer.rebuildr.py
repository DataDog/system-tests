import os

from rebuildr import Build, BuildArg, File


platform = os.environ["DOCKER_SSI_PLATFORM"]
runtime = os.environ.get("DOCKER_SSI_RUNTIME")
dd_lang = os.environ["DOCKER_SSI_DD_LANG"]
repository = f"{os.environ['DOCKER_SSI_REPOSITORY_PREFIX']}/ssi_{{}}_{os.environ['DOCKER_SSI_BASE_TAG']}"

base_context = [
    File("utils/build/ssi/base/install_os_deps.sh", "base/install_os_deps.sh"),
    File("utils/build/ssi/base/healthcheck.sh", "base/healthcheck.sh"),
    File("utils/build/ssi/base/tested_components.sh", "base/tested_components.sh"),
]
base_build_args = [BuildArg("BASE_IMAGE", os.environ["DOCKER_SSI_BASE_IMAGE"]), BuildArg("ARCH", platform)]
if runtime:
    dockerfile = "utils/build/ssi/base/base_lang.Dockerfile"
    base_context.append(
        File(f"utils/build/ssi/base/{dd_lang}_install_runtimes.sh", f"base/{dd_lang}_install_runtimes.sh")
    )
    base_build_args.extend([BuildArg("DD_LANG", dd_lang), BuildArg("RUNTIME_VERSIONS", runtime)])
else:
    dockerfile = "utils/build/ssi/base/base_deps.Dockerfile"

build = Build(default="ssi-installer", platform=platform)
base = build.image(
    "base",
    repository=repository.format("base"),
    context=base_context,
    dockerfile=dockerfile,
    build_args=base_build_args,
)
build.image(
    "ssi-installer",
    repository=repository.format("installer"),
    context=[
        File("utils/build/ssi/base/install_script_ssi_installer.sh", "base/install_script_ssi_installer.sh"),
        File(os.environ["DOCKER_SSI_INSTALLER_SCRIPT"], "base/binaries/install_script_agent7.sh"),
    ],
    dockerfile="utils/build/ssi/base/base_ssi_installer.Dockerfile",
    image_refs={"cached-base": base},
    build_args=[BuildArg("BASE_IMAGE", "cached-base")],
    tag="latest",
)
