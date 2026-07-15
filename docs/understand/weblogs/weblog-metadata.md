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

Base images (built by the `build_base_images` CI job, `utils/scripts/build_base_images.py`) are
declared in each library's `utils/build/docker/<library>/docker-bake.hcl`, one target per base
image. There is no separate dependency list to maintain: for each target, the job parses the
target's own `<name>.base.Dockerfile` and treats every `COPY` source as a dependency. This works
because base Dockerfiles are required to follow a few rules that make that derivation
unambiguous:

- No `ADD` — use `COPY` for everything (no glob sources, no whole-directory copies, no remote
  URLs).
- Every `COPY` has exactly one source: `COPY [flags] <source> <dest>`.
- The bake target's `context` is always the Dockerfile's own directory, so every `COPY` source
  is a plain path relative to that directory.
- No `RUN --mount` — a bind/cache/secret mount reads from a path the script can't see, so it
  would silently escape the derived dependency list.

(`COPY --from=<stage-or-image>` is unaffected: it isn't a local repository path, so it's skipped.)

The job computes a content hash from the resolved `docker-bake.hcl` target config, the target's
Dockerfile, and every git-tracked file under each derived dependency path, then pushes the base
image to Docker Hub tagged `<base-tag>-<hash12>` if that tag doesn't already exist. It never
overwrites an existing tag, so weblog Dockerfiles that `FROM` a base image must have their tag
updated by hand after a new one is pushed (run the script with `--dry-run` to find the current
tag for each target).

As a safety net, before building, every derived dependency is hardlinked (or copied, if
hardlinking isn't possible) into an isolated build context under `.base_image_build/`, and the
image is built from that directory instead of the real one. This way, if the Dockerfile
references a file the parser failed to recognize as a dependency, the build fails loudly
("file not found") instead of silently succeeding against the full checkout — which would leave
the tag's content hash stale without anyone noticing.

GitHub Actions never builds these base images itself: `utils/scripts/wait_for_base_image.py`
polls Docker Hub for the tag currently referenced in the weblog's `FROM` line (with a timeout)
before building the weblog, since GitLab CI is the only pipeline that builds and pushes them.
