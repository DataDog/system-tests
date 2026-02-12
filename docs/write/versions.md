System-tests uses [SemVer](https://semver.org/), where a version is defined like: `1.2.3-prerelease+build`.

* `1.2.3` is the trio `major`, `minor` and `patch`
* `prerelease` is an optional label, usually something like `rc1`, `dev` ...
* `build` is also an optional label, usually a commit SHA.

Any version suffixed with a prelease is always less than the same version without the suffix:

 **`1.2.3` < `1.2.4-rc1` < `1.2.4`**

## Use cases

Let say your last released version is `1.2.3`, and the version of your main branch is `1.2.4-dev` (visible in system-tests output)

### Activate a test for your last released library

Simply use `1.2.3`

### Activate a test for a feature just merged on a `main` branch

* obviously, do not use `1.2.3`
* less obvious, do not use `1.2.4` ! your test won't be activated. If you didn't implement your feature correctly, or if a later PR has broken your implementation, you won't see anything before the release 😨
* -> use `1.2.4-dev`


DataDog/dd-trace-js and DataDog/dd-trace-dotnet developers : as the version declared on your main branch is at the next future major, while the next version is **not** the next future major, `1.2.4` will work fine.

DataDog/dd-trace-rb : versions of the gem are not fully semver compatible, so system-tests tries to keep all possible data. More importantly, the version declared on the main branch is not bumped (it's still `1.2.3` on the current example). So system tests increase the `patch`, and set the prerelease to `z` if it's missing. So you can safely use `1.2.4-dev`.

Datadog/dd-trace-java: Use `v<next_minor_release>-SNAPSHOT` to reference the master branch. For example, if the last release was v1.46.0, you'd replace `<next_minor_release>` with `v1.47.0`. You can also get the current dev version by running `./gradlew :currentVersion` inside of the dd-trace-java repo.

Datadog/dd-trace-go: The main branch's version tag is documented inside of the [`dd-trace-go/internal/version/version.go` file](https://github.com/DataDog/dd-trace-go/blob/main/internal/version/version.go#L13-L16), on the main branch: `v<next_minor_release>-dev`.

