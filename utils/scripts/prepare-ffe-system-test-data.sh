#!/usr/bin/env bash

set -euo pipefail

repository=${SYSTEM_TESTS_FFE_TEST_DATA_REPOSITORY:-https://github.com/DataDog/ffe-system-test-data.git}
ref=${SYSTEM_TESTS_FFE_TEST_DATA_REF:-80dddff0c084967c2558bfbedd602dd5ece11c65}
checkout_path=${SYSTEM_TESTS_FFE_TEST_DATA_PATH:-binaries/ffe-system-test-data}

if [[ -e $checkout_path && ! -d $checkout_path/.git ]]; then
  printf 'Refusing to replace non-git path: %s\n' "$checkout_path" >&2
  exit 1
fi

if [[ ! -d $checkout_path/.git ]]; then
  git clone --filter=blob:none "$repository" "$checkout_path"
fi

if [[ -n $(git -C "$checkout_path" status --short) ]]; then
  printf 'Refusing to update dirty fixture checkout: %s\n' "$checkout_path" >&2
  exit 1
fi

git -C "$checkout_path" fetch --no-tags origin "$ref"
git -C "$checkout_path" checkout --detach FETCH_HEAD
printf 'Prepared FFE fixtures at %s (%s)\n' "$checkout_path" "$(git -C "$checkout_path" rev-parse HEAD)"
