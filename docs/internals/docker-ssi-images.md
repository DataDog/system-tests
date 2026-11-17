# Docker SSI images

This page explains how a Docker SSI scenario builds the weblog image, and how it stores the base image in
the private registry. Read it before you change a file under `utils/build/ssi/` or the
`DockerSSIImageBuilder` class in `utils/_context/_scenarios/docker_ssi.py`.

To run the tests, see [Docker SSI](../understand/scenarios/docker_ssi.md).

## The four images

Each scenario run builds up to four images, each one on top of the previous one. The build runs in the
scenario `configure()` step, before the containers start. In the table, `<name>` is
`<base image>_<runtime>_<arch>`, for example `public_ecr_aws-lts-ubuntu-22_04_java_27_linux-amd64`.

| # | Local image | Dockerfile | Built on | Built when |
|---|-------------|------------|----------|------------|
| 1 | `<name>` | `base/base_lang.Dockerfile` or `base/base_deps.Dockerfile` | The OS image | The base image is not in the registry |
| 2 | `ssi_installer_<name>` | `base/base_ssi_installer.Dockerfile` | Image 1 | Same as image 1 |
| 3 | `ssi_all_<name>` | `base/base_ssi.Dockerfile` | Image 2, or the base image from the registry | Every run |
| 4 | `weblog-injection:latest` | `<lang>/<weblog>.Dockerfile` | Image 3 | Every run. The weblog container runs this image |

Images 1 and 2 are the **base image**: OS dependencies, the language runtime and the Datadog installer.
They are slow to build, so CI stores image 2 in the private registry. Images 3 and 4 are never pushed.

## Two paths

When the base image is **not** in the registry:

1. Build images 1 and 2, without the Docker cache.
2. Build image 3 on image 2, then image 4 on image 3.
3. Start the containers and run the tests.
4. At the end of the session, tag image 2 with the registry tag and push it.

When the base image **is** in the registry:

1. Pull it. Images 1 and 2 are not built.
2. Build image 3 on the pulled image, then image 4 on image 3.
3. Start the containers and run the tests. Nothing is pushed.

## The registry tag

All base images are stored in one repository, `system-tests/docker-ssi-base`:

```text
$PRIVATE_DOCKER_REGISTRY/system-tests/docker-ssi-base:<name>-<hash>
```

The hash covers:

* every file directly under `utils/build/ssi/base/`. Subfolders and hidden files are ignored, so
  `binaries/` is not part of it.
* the build arguments of image 1: base image, runtime version, architecture and language.

The code is in `utils/docker_ssi/base_image_tag.py`. A tag has at most 128 characters: a long `<name>` is
cut, and the hash keeps the tag unique.

Images expire 30 days after the push, through an ECR lifecycle policy. The next run that needs one builds
it again, so OS packages and the Datadog installer stay recent.

## What triggers a new base image

| You change | Result |
|------------|--------|
| A weblog (`utils/build/ssi/<lang>/`) | Same base image. Images 3 and 4 are rebuilt, as in every run |
| A file directly under `utils/build/ssi/base/` | New hash: the first run that needs each base image builds it again |
| A runtime version in `utils/docker_ssi/docker_ssi_runtimes.json` | New hash for that runtime |
| A new runtime, OS or architecture | New tag, built by the first run that needs it |
| Nothing, for 30 days | The image expires and the next run builds it again |

A new base image does not need a new repository or new permissions.

Some scenarios share a base image, such as `DOCKER_SSI`, `DOCKER_SSI_APPSEC` and `DOCKER_SSI_CRASHTRACKING`.
The first time, they can build and push the same tag at the same time. This is harmless: they push
equivalent images, and the repository allows a tag to be pushed again.

## Options

* `--ssi-force-build`: build every image again, without the Docker cache. Use it locally after you change
  something, or to get the latest SSI version.
* `--ssi-push-base-images`: if the base image is already in the registry, build and push it anyway. You
  will rarely need it.

## Local runs

Without `PRIVATE_DOCKER_REGISTRY`, the base image is never found, so it is always built and never pushed.
Docker reuses cached `RUN` steps for images 3 and 4. Add `--ssi-force-build` to rebuild them.
