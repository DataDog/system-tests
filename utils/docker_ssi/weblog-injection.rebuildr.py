import os

from rebuildr import Build, BuildArg, File


root_dir = os.environ["REBUILDR_OVERRIDE_ROOT_DIR"]
library = os.environ["DOCKER_SSI_LIBRARY"]
dd_lang = os.environ["DOCKER_SSI_DD_LANG"]

ssi_context = [
    File("utils/build/ssi/base/install_script_ssi.sh", "base/install_script_ssi.sh"),
    File(os.environ["DOCKER_SSI_INSTALLER_SCRIPT"], "base/binaries/install_script_agent7.sh"),
]
binary_dir = os.path.join(root_dir, "utils/build/ssi/base/binaries")
if os.path.isdir(binary_dir):
    for name in sorted(os.listdir(binary_dir)):
        if name != "install_script_agent7.sh":
            source = os.path.relpath(os.path.join(binary_dir, name), root_dir)
            ssi_context.append(File(source, f"base/binaries/{name}"))

build = Build(default="weblog", platform=os.environ["DOCKER_SSI_PLATFORM"], content_tag=False)
ssi = build.image(
    "ssi",
    repository="system-tests/ssi-runtime",
    context=ssi_context,
    dockerfile="utils/build/ssi/base/base_ssi.Dockerfile",
    build_args=[
        BuildArg("BASE_IMAGE", os.environ["DOCKER_SSI_CACHED_BASE_IMAGE"]),
        BuildArg("DD_LANG", dd_lang),
        BuildArg("SSI_ENV", os.environ["DOCKER_SSI_ENV"]),
        BuildArg("DD_INSTALLER_LIBRARY_VERSION", os.environ.get("DOCKER_SSI_LIBRARY_VERSION")),
        BuildArg("DD_INSTALLER_INJECTOR_VERSION", os.environ.get("DOCKER_SSI_INJECTOR_VERSION")),
        BuildArg("DD_APPSEC_ENABLED", os.environ.get("DOCKER_SSI_APPSEC_ENABLED")),
        BuildArg("SSI_BUILD_NONCE", os.environ["DOCKER_SSI_BUILD_NONCE"]),
    ],
)
build.image(
    "weblog",
    repository="weblog-injection",
    context=[
        f"lib-injection/build/docker/{library}",
        f"utils/build/ssi/{library}",
    ],
    dockerfile=f"utils/build/ssi/{library}/{os.environ['DOCKER_SSI_WEBLOG']}.Dockerfile",
    image_refs={"ssi-image": ssi},
    build_args=[BuildArg("BASE_IMAGE", "ssi-image")],
    tag="latest",
)
