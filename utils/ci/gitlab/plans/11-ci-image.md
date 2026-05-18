# Feature: move the CI image to the system-tests repo

## Context

The CI image (`registry.ddbuild.io/ci/libdatadog-build/system-tests:100425777`) is
currently defined and built in the `libdatadog-build` repo. Its tag is a manually
bumped integer which gives no indication of what changed. This plan moves the image
definition into the system-tests repo, and introduces a CI job that rebuilds and
pushes it automatically whenever its inputs change, using a content-hash as the tag.

Reference files:
- `libdatadog-build/docker/system-tests.Dockerfile` — current Dockerfile (to be moved)
- `libdatadog-build/docker/install_kube_dependencies.sh` — helper script (to be moved)
- `requirements.txt` — Python dependencies baked into the image
- `utils/ci/gitlab/main.yml` — references the image tag in every job
- `utils/ci/gitlab/system-tests.yml` — Jinja template: references the image tag in every generated job
- `utils/ci/gitlab/build_pipeline.py` — generates the child pipeline YAML

---

## 1. Move the Dockerfile and helper script into the system-tests repo

Create `utils/ci/docker/` and add two files:

### `utils/ci/docker/install_kube_dependencies.sh`
Copy verbatim from `libdatadog-build/docker/install_kube_dependencies.sh`.

### `utils/ci/docker/system-tests.Dockerfile`
Based on the existing Dockerfile with two changes:

1. **Replace the git clone with a `COPY`** of only the files needed to build the
   venv (`requirements.txt`). This removes the dependency on GitHub and makes the
   image hermetically tied to the repo's own `requirements.txt`:

   ```dockerfile
   # instead of:
   RUN git clone https://github.com/DataDog/system-tests.git /system-tests
   RUN ./build.sh -i runner

   # use:
   COPY requirements.txt /system-tests/requirements.txt
   WORKDIR /system-tests
   RUN python3.12 -m venv venv && \
       venv/bin/pip install --upgrade pip setuptools==75.8.0 && \
       venv/bin/pip install -r requirements.txt
   ```

   The editable `pip install -e .` is intentionally dropped: CI jobs already
   handle package resolution via `PYTHONPATH=$CI_PROJECT_DIR`.

2. **Replace the `COPY docker/install_kube_dependencies.sh`** path with the new
   location inside the repo:
   ```dockerfile
   COPY utils/ci/docker/install_kube_dependencies.sh .
   ```

---

## 2. Define the hash

The image tag is the first 12 hex characters of the SHA-256 hash of the files that
fully determine the image content:

- `utils/ci/docker/system-tests.Dockerfile`
- `requirements.txt`

```bash
IMAGE_TAG=$(cat utils/ci/docker/system-tests.Dockerfile requirements.txt \
    | sha256sum | cut -c1-12)
```

Sorting the inputs by filename is not required here since the order is fixed by the
script, but it should be kept stable across changes.

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
2. Checks whether `$CI_REGISTRY_IMAGE/ci-image:$IMAGE_TAG` already exists in the
   registry (`docker manifest inspect`). If it does, skips the build entirely.
3. If the image is absent, builds and pushes it.
4. Writes `IMAGE_TAG` to a dotenv artifact so downstream jobs receive it.

```yaml
build_ci_image:
  image: registry.ddbuild.io/images/docker:20.10.13-jammy
  interruptible: true
  tags:
    - docker-in-docker:amd64
  stage: $[[ inputs.stage ]]
  script:
    - >
      IMAGE_TAG=$(cat utils/ci/docker/system-tests.Dockerfile requirements.txt
      | sha256sum | cut -c1-12)
    - echo "CI_IMAGE=$CI_REGISTRY_IMAGE/ci-image:$IMAGE_TAG" >> build.env
    - >
      if docker manifest inspect $CI_REGISTRY_IMAGE/ci-image:$IMAGE_TAG > /dev/null 2>&1; then
        echo "Image already exists, skipping build";
      else
        docker build
          -f utils/ci/docker/system-tests.Dockerfile
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

Pass `CI_IMAGE` (received from dotenv artifact) as a new `--ci-image` CLI argument
to `build_pipeline.py`:

```bash
python3 utils/ci/gitlab/build_pipeline.py \
  --stage $[[ inputs.stage ]] \
  --library $library \
  --params params_${library}.json \
  --ci-image "$CI_IMAGE" \
  ...
```

Replace the hardcoded image in `build_test_pipeline` itself:
```yaml
build_test_pipeline:
  image: $CI_IMAGE   # instead of hardcoded tag
```

### `utils/ci/gitlab/build_pipeline.py`

Add `--ci-image` argument and pass it to the Jinja template:

```python
parser.add_argument("--ci-image", required=True, help="Full CI image reference")
...
template.render(..., ci_image=args.ci_image)
```

### `utils/ci/gitlab/system-tests.yml`

Replace every hardcoded `image: registry.ddbuild.io/ci/libdatadog-build/system-tests:...`
with `image: {{ci_image}}`.

---

## 6. Remove the image from `libdatadog-build`

Once the above is in place and the new image is in use:
- Delete `docker/system-tests.Dockerfile` and `docker/install_kube_dependencies.sh`
  from the `libdatadog-build` repo (separate PR/MR).

---

## Summary of file changes

| File | Change |
|---|---|
| `utils/ci/docker/system-tests.Dockerfile` | New — moved + adapted from `libdatadog-build` |
| `utils/ci/docker/install_kube_dependencies.sh` | New — moved verbatim |
| `utils/ci/gitlab/main.yml` | Add `build_ci_image` job; `build_test_pipeline` needs it and uses `$CI_IMAGE`; pass `--ci-image` to `build_pipeline.py` |
| `utils/ci/gitlab/build_pipeline.py` | Add `--ci-image` arg, pass to template |
| `utils/ci/gitlab/system-tests.yml` | Replace hardcoded image with `{{ci_image}}` |
| `libdatadog-build/docker/system-tests.Dockerfile` | Delete (separate MR) |
| `libdatadog-build/docker/install_kube_dependencies.sh` | Delete (separate MR) |
