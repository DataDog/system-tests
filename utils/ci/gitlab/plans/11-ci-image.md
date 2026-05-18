# Feature: move the CI image to the system-tests repo

## Context

The CI image (`registry.ddbuild.io/ci/libdatadog-build/system-tests:100425777`) is
currently defined and built in the `libdatadog-build` repo. Its tag is a manually
bumped integer which gives no indication of what changed. This plan moves the image
definition into the system-tests repo, and introduces a CI job that rebuilds and
pushes it automatically whenever its inputs change, using a content-hash as the tag.

Reference files:
- `libdatadog-build/docker/system-tests.Dockerfile` — current Dockerfile (to be moved)
- `libdatadog-build/docker/install_kube_dependencies.sh` — helper script (not moved, kept for backward compatibility)
- `requirements.txt` — Python dependencies baked into the image
- `utils/ci/gitlab/main.yml` — references the image tag in every job
- `utils/ci/gitlab/system-tests.yml` — Jinja template: references the image tag in every generated job
- `utils/ci/gitlab/build_pipeline.py` — generates the child pipeline YAML

---

## 1. Create the Dockerfile in the system-tests repo

Create `utils/ci/gitlab/docker/system-tests.Dockerfile` based on the existing
Dockerfile with the following changes:

### 1a. Remove unused dependencies

None of the following are called by any CI pipeline script:

| Removed | Reason |
|---|---|
| `binutils` | Redundant — already installed transitively by `build-essential` |
| `vault`, `libcap2-bin` | Secrets are fetched via AWS SSM, not Vault |
| Hashicorp GPG key, apt source, `setcap` call | Only present to support vault |
| `install_kube_dependencies.sh` (kind, kubectl, helm) | Only needed for K8s scenarios which run on dedicated infrastructure |

`jq` is kept: it is used by `utils/scripts/load-binary.sh` for GitHub API calls.

`install_kube_dependencies.sh` is **not** moved to the system-tests repo — it is
deleted entirely from `libdatadog-build`.

### 1b. Replace the git clone with a COPY

Instead of cloning system-tests at image build time (stale, slow, depends on
GitHub), copy only `requirements.txt` and build the venv directly from it:

```dockerfile
# Remove:
RUN git clone https://github.com/DataDog/system-tests.git /system-tests
RUN ./build.sh -i runner

# Replace with:
COPY requirements.txt /system-tests/requirements.txt
WORKDIR /system-tests
RUN python3.12 -m venv venv && \
    venv/bin/pip install --upgrade pip setuptools==75.8.0 && \
    venv/bin/pip install -r requirements.txt
```

The editable `pip install -e .` is intentionally dropped: CI jobs already handle
package resolution via `PYTHONPATH=$CI_PROJECT_DIR`.

---

## 2. Define the hash

The image tag is the first 12 hex characters of the SHA-256 hash of the files that
fully determine the image content:

- `utils/ci/gitlab/docker/system-tests.Dockerfile`
- `requirements.txt`

```bash
IMAGE_TAG=$(cat utils/ci/gitlab/docker/system-tests.Dockerfile requirements.txt \
    | sha256sum | cut -c1-12)
```

The concatenation order must be kept stable across changes.

---

## 3. Define the registry target

Use the GitLab project's built-in registry:

```
$CI_REGISTRY_IMAGE/ci-image:$IMAGE_TAG
```

`$CI_REGISTRY_IMAGE` expands to the project's registry prefix automatically in
GitLab CI (e.g. `registry.ddbuild.io/datadog/system-tests`).

---

## 4. Add the `build_ci_image` job to `main.yml`

The job:
1. Computes `IMAGE_TAG`
2. Checks whether the image already exists (`docker manifest inspect`). If so,
   skips the build entirely — common case has zero overhead.
3. If absent, builds and pushes.
4. Writes `CI_IMAGE` to a dotenv artifact so downstream jobs receive it.

```yaml
build_ci_image:
  image: registry.ddbuild.io/images/docker:20.10.13-jammy
  interruptible: true
  tags:
    - docker-in-docker:amd64
  stage: $[[ inputs.stage ]]
  script:
    - >
      IMAGE_TAG=$(cat utils/ci/gitlab/docker/system-tests.Dockerfile requirements.txt
      | sha256sum | cut -c1-12)
    - echo "CI_IMAGE=$CI_REGISTRY_IMAGE/ci-image:$IMAGE_TAG" >> build.env
    - >
      if docker manifest inspect $CI_REGISTRY_IMAGE/ci-image:$IMAGE_TAG > /dev/null 2>&1; then
        echo "Image already exists, skipping build";
      else
        docker build
          -f utils/ci/gitlab/docker/system-tests.Dockerfile
          -t $CI_REGISTRY_IMAGE/ci-image:$IMAGE_TAG
          . &&
        docker push $CI_REGISTRY_IMAGE/ci-image:$IMAGE_TAG;
      fi
  artifacts:
    reports:
      dotenv: build.env
  before_script:
    - export DOCKER_LOGIN=$(aws ssm get-parameter --region us-east-1
        --name ci.system-tests.docker-login-write --with-decryption
        --query "Parameter.Value" --out text)
    - export DOCKER_LOGIN_PASS=$(aws ssm get-parameter --region us-east-1
        --name ci.system-tests.docker-login-pass-write --with-decryption
        --query "Parameter.Value" --out text)
    - echo "$DOCKER_LOGIN_PASS" | docker login --username "$DOCKER_LOGIN" --password-stdin
```

`build_test_pipeline` gets `needs: [job: build_ci_image, artifacts: true]` so it
receives `CI_IMAGE` from the dotenv artifact. No new stage is needed — GitLab's DAG
scheduling runs `build_ci_image` before `build_test_pipeline` even within the same
stage.

---

## 5. Thread `CI_IMAGE` through to generated jobs

### `main.yml` — `build_test_pipeline`

- Replace the hardcoded `image:` with `$CI_IMAGE`
- Add `needs: [job: build_ci_image, artifacts: true]`
- Pass `--ci-image "$CI_IMAGE"` to `build_pipeline.py`

### `utils/ci/gitlab/build_pipeline.py`

Add `--ci-image` argument and pass it to the Jinja template:

```python
parser.add_argument("--ci-image", required=True, help="Full CI image reference")
...
template.render(..., ci_image=args.ci_image)
```

### `utils/ci/gitlab/system-tests.yml`

Replace every hardcoded
`image: registry.ddbuild.io/ci/libdatadog-build/system-tests:...`
with `image: {{ci_image}}`.

---

## Summary of file changes

| File | Change |
|---|---|
| `utils/ci/gitlab/docker/system-tests.Dockerfile` | New — adapted from `libdatadog-build` (unused deps removed, git clone replaced with COPY) |
| `utils/ci/gitlab/main.yml` | Add `build_ci_image` job; `build_test_pipeline` needs it and uses `$CI_IMAGE`; pass `--ci-image` to `build_pipeline.py` |
| `utils/ci/gitlab/build_pipeline.py` | Add `--ci-image` arg, pass to template |
| `utils/ci/gitlab/system-tests.yml` | Replace hardcoded image with `{{ci_image}}` |

`libdatadog-build/docker/system-tests.Dockerfile` and
`libdatadog-build/docker/install_kube_dependencies.sh` are kept as-is for
backward compatibility.
