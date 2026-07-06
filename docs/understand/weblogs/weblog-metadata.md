# Weblog metadata

Each library folder under `utils/build/docker/<library>/` may contain a `weblog_metadata.yml` file
that declares metadata for weblogs that cannot be inferred from the Dockerfile alone.

## When to add an entry

A weblog discovered via a `<name>.Dockerfile` file defaults to `build_mode: prebuild` and no
`framework_versions`. Add an entry only when you need to override those defaults.

## Format

```yaml
<weblog-name>:
  build_mode: none | local | prebuild   # default: prebuild
  framework_versions: ["1.0.0", ...]    # optional; omit for non-integration-framework weblogs
```

The `library` field is intentionally absent — it is inferred from the folder the file lives in.

## `build_mode` values

| Value | Meaning |
|-------|---------|
| `none` | No Docker build. The shared `binaries_artifact` is used as-is (integration frameworks, proxies). |
| `local` | The weblog has a fully baked base image. The build step inside the test job is trivial (only `COPY` instructions). No dedicated CI build job. |
| `prebuild` | Built ahead of time by a dedicated `build_end_to_end` CI job that uploads a per-weblog artifact; still built locally when the test job runs. |

Both `local` and `prebuild` set `weblog_build_required = true`.

## Integration-framework weblogs

When `framework_versions` is set, a single entry fans out into one weblog per version at load time:

```yaml
openai-js:
  build_mode: none
  framework_versions: ["6.0.0", "7.0.0"]
```

produces `openai-js@6.0.0` and `openai-js@7.0.0`.

## Loader

`WeblogMetaData.load(library)` in `utils/_context/weblog_metadata.py` merges:
1. Weblogs discovered from `*.Dockerfile` files in the library folder (default metadata).
2. Explicit overrides from `weblog_metadata.yml`.

## Base image dependencies

A `weblog_metadata.yml` may also declare a top-level `base_image_dependencies` section, unrelated
to the per-weblog entries above, used by the `build_base_images` CI job
(`utils/scripts/build_base_images.py`) to know when a weblog base image needs to be rebuilt:

```yaml
base_image_dependencies:
  <docker-bake.hcl target name>:
    - <path to a file or directory the base image depends on>
    - ...
```

For each target listed there, the job computes a content hash from the resolved
`docker-bake.hcl` target config, the target's Dockerfile, and every git-tracked file under the
listed paths, then pushes the base image to Docker Hub tagged `<base-tag>-<hash12>` if that tag
doesn't already exist. It never overwrites an existing tag, so weblog Dockerfiles that `FROM` a
base image must have their tag updated by hand after a new one is pushed (run the script with
`--dry-run` to find the current tag for each target).
