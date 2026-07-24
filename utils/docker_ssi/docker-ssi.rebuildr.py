import os

from rebuildr import Build, BuildArg, File, Glob


root_dir = os.environ["REBUILDR_OVERRIDE_ROOT_DIR"]
platform = os.environ["DOCKER_SSI_PLATFORM"]
runtime = os.environ.get("DOCKER_SSI_RUNTIME")
library = os.environ["DOCKER_SSI_LIBRARY"]
dd_lang = os.environ["DOCKER_SSI_DD_LANG"]
installer_script = os.environ["DOCKER_SSI_INSTALLER_SCRIPT"]
reusable = f"{os.environ['DOCKER_SSI_REPOSITORY_PREFIX']}/ssi_{{}}_{os.environ['DOCKER_SSI_BASE_TAG']}"

BINARIES = "utils/build/ssi/base/binaries"
INSTALLER = "install_script_agent7.sh"

# One reference graph: base -> ssi-installer -> ssi -> weblog. `base` and
# `ssi-installer` are content addressed and shared between runs, so Rebuildr
# swaps them for their published image whenever the content is already in a
# registry (or in the local image store) instead of rebuilding them. Only `ssi`
# and `weblog` are per-run, and BuildKit resolves the whole graph in one job.
build = Build(default="weblog", platform=platform)

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

base = build.image(
    "base",
    repository=reusable.format("base"),
    context=base_context,
    dockerfile=dockerfile,
    build_args=base_build_args,
)
installer = build.image(
    "ssi-installer",
    repository=reusable.format("installer"),
    context=[
        File("utils/build/ssi/base/install_script_ssi_installer.sh", "base/install_script_ssi_installer.sh"),
        File(installer_script, f"base/binaries/{INSTALLER}"),
    ],
    dockerfile="utils/build/ssi/base/base_ssi_installer.Dockerfile",
    image_refs={"cached-base": base},
    build_args=[BuildArg("BASE_IMAGE", "cached-base")],
    tag="latest",
)

# The SSI runtime installs the library published under test, so its content is
# not a function of its inputs: it stays untagged and out of the content cache,
# and the nonce keeps BuildKit from reusing the install layer.
ssi_context = [File("utils/build/ssi/base/install_script_ssi.sh", "base/install_script_ssi.sh")]
binaries_dir = os.path.join(root_dir, BINARIES)
if os.path.isdir(binaries_dir):
    # Everything the run dropped in `binaries`: custom tracer artifacts, and the agent
    # installer itself when it is a local copy rather than a download.
    ssi_context.append(Glob("*", root_dir=BINARIES, target_path="base/binaries", allow_empty=True))
if not os.path.isfile(os.path.join(binaries_dir, INSTALLER)):
    ssi_context.append(File(installer_script, f"base/binaries/{INSTALLER}"))

ssi = build.image(
    "ssi",
    repository="system-tests/ssi-runtime",
    context=ssi_context,
    dockerfile="utils/build/ssi/base/base_ssi.Dockerfile",
    image_refs={"installer-image": installer},
    build_args=[
        BuildArg("BASE_IMAGE", "installer-image"),
        BuildArg("DD_LANG", dd_lang),
        BuildArg("SSI_ENV", os.environ["DOCKER_SSI_ENV"]),
        BuildArg("DD_INSTALLER_LIBRARY_VERSION", os.environ.get("DOCKER_SSI_LIBRARY_VERSION") or None),
        BuildArg("DD_INSTALLER_INJECTOR_VERSION", os.environ.get("DOCKER_SSI_INJECTOR_VERSION") or None),
        BuildArg("DD_APPSEC_ENABLED", os.environ.get("DOCKER_SSI_APPSEC_ENABLED") or None),
        BuildArg("SSI_BUILD_NONCE", os.environ["DOCKER_SSI_BUILD_NONCE"]),
    ],
    content_tag=False,
)
build.image(
    "weblog",
    repository="weblog-injection",
    context=[f"lib-injection/build/docker/{library}", f"utils/build/ssi/{library}"],
    dockerfile=f"utils/build/ssi/{library}/{os.environ['DOCKER_SSI_WEBLOG']}.Dockerfile",
    image_refs={"ssi-image": ssi},
    build_args=[BuildArg("BASE_IMAGE", "ssi-image")],
    content_tag=False,
    tag="latest",
)
