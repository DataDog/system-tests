#!/bin/sh
# Strips runtime-unnecessary files from node_modules to reduce Docker image
# file count. Image extraction time scales with file count, not compressed
# size, so fewer files means faster CI load times.
#
# Usage: cleanup-node-modules [--typescript]
#   --typescript  Keep .d.ts declarations and @types packages, which the
#                 TypeScript compiler needs. Raw .ts source files are still
#                 removed since tsc only reads declarations from dependencies.
#
# MAINTENANCE — review this script whenever a package.json changes:
#
#   1. STALE REMOVALS: a package explicitly removed below may have become a
#      real production dependency. Silently deleting a live dep breaks runtime
#      behaviour without a build error. Check each listed package still has no
#      production dependent:
#        grep -rl '"<pkg>"' node_modules/*/package.json \
#          node_modules/@*/*/package.json \
#          | xargs grep -l '"dependencies"' \
#          | while read f; do
#              grep -A30 '"dependencies"' "$f" | grep -q '"<pkg>"' && echo "$f"
#            done
#
#   2. NEW ORPHANS: adding or removing a dep may leave behind transitive
#      devDeps with no remaining consumer. Run the query above for any suspect
#      package; if nothing depends on it in a dependencies block, add it here.

set -e

TYPESCRIPT=0
for arg in "$@"; do
  case "$arg" in --typescript) TYPESCRIPT=1 ;; esac
done

# Remove the bun global install cache. bun populates /root/.bun/install/cache
# during `bun install`, mirroring every package also installed into
# node_modules. This doubles the file count for no runtime benefit.
rm -rf /root/.bun

# Remove source maps, markdown docs, and lint config files that packages ship
# alongside their runtime code but serve no purpose inside a container.
find node_modules -type f \
  \( -name "*.map" -o -name "*.md" -o -name ".eslint*" \) \
  -delete

# Remove TypeScript files. For JavaScript runtimes, all .ts files (including
# .d.ts declarations) are unnecessary. For TypeScript images, keep .d.ts
# declarations — tsc reads them for type checking — but drop raw source files,
# which packages compile away and never read at runtime.
if [ "$TYPESCRIPT" = "1" ]; then
  find node_modules -name "*.ts" -not -name "*.d.ts" -delete
else
  find node_modules -name "*.ts" -delete
  rm -rf node_modules/@types
fi

# Remove test, example, benchmark, and docs directories that packages bundle
# with their source. Use -depth so children are processed before parents,
# preventing "already removed" errors when a matched dir has matched children.
{
  find node_modules -depth -type d \
    \( -name "test"      -o -name "tests"   -o -name "__tests__" \
    -o -name "examples"  -o -name "docs" \
    -o -name "benchmark" -o -name "benchmarks" \) \
    -exec rm -rf {} + 2>/dev/null
  true
}

# Remove devDependencies. bun installs them even under NODE_ENV=production
# when --frozen-lockfile is used, because the lockfile was generated with
# devDeps included and frozen installs honour the lockfile verbatim.
jq -r '.devDependencies // {} | keys[]' package.json \
  | xargs -I{} rm -rf node_modules/{}

# Remove orphaned transitive dependencies of eslint. Removing eslint and its
# plugins (above) leaves these packages behind since they are not listed as
# direct devDependencies in package.json, only as transitive deps of eslint.
rm -rf \
  node_modules/@eslint \
  node_modules/@eslint-community \
  node_modules/@humanwhocodes \
  node_modules/espree \
  node_modules/eslint-import-resolver-node \
  node_modules/eslint-module-utils \
  node_modules/eslint-plugin-es-x \
  node_modules/eslint-scope \
  node_modules/eslint-utils \
  node_modules/eslint-visitor-keys

# Remove ECMAScript polyfill shims that were transitive devDeps of eslint.
# None of these packages have any remaining production dependent after eslint
# is removed, and Node.js 18+ provides all the methods they polyfill natively.
rm -rf \
  node_modules/array-includes \
  node_modules/array.prototype.findlastindex \
  node_modules/array.prototype.flat \
  node_modules/array.prototype.flatmap \
  node_modules/arraybuffer.prototype.slice \
  node_modules/function.prototype.name \
  node_modules/object.fromentries \
  node_modules/object.groupby \
  node_modules/object.values \
  node_modules/string.prototype.trim \
  node_modules/string.prototype.trimend \
  node_modules/string.prototype.trimstart

# Remove rambda, which is an orphaned transitive devDep (no production
# dependent remains after eslint removal).
rm -rf node_modules/rambda

# Remove es-abstract year directories for 2015–2022. The only remaining
# consumer (es-aggregate-error, a tedious/mssql dep) imports exclusively
# from es-abstract/2023/. The older year directories are dead weight.
rm -rf \
  node_modules/es-abstract/2015 \
  node_modules/es-abstract/2016 \
  node_modules/es-abstract/2017 \
  node_modules/es-abstract/2018 \
  node_modules/es-abstract/2019 \
  node_modules/es-abstract/2020 \
  node_modules/es-abstract/2021 \
  node_modules/es-abstract/2022
