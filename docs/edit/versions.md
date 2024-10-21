System-tests uses [SemVer](https://semver.org/), where a version can be seen as : `1.2.3-prerelease+build`.

* `1.2.3` is the trio `major`, `minor` and `patch`
* `prerelease` is an optional label, usually something like `rc1`, `dev` ...
* `build` is also an optional label, usually a commit SHA.

And a very important point, in SemVer `1.2.3` < `1.2.4-rc1` < `1.2.4`.

## Use cases

Let say your last released version is `1.2.3`, and your version on your main branch is `1.2.4-dev` (visible in system-tests output)

### Activate a test for your last released library

Simply use `1.2.3`

### Activate a test for a feature just merged on a `main` branch

* obviously, do not use `1.2.3`
* less obvious, do not use `1.2.4` ! your test won't be activated. If if you didn't implemented correctly your feature, or if a later PR break your implementation, you won't see anything before the release :scared:
* -> use `1.2.4-dev`


DataDog/dd-trace-js and DataDog/dd-trace-dotnet developers : as the version declared on your main branch is at the next future major, while the next version is **not** the next future major, `1.2.4` will work fine.

DataDog/dd-trace-rb : versions of the gem are not fully semver compatible, so system-tests tries to keep all possible data. More importantly, the version declared on the main branch is not bumped (it's still `1.2.3` on the current example). So system tests increase the `patch`, and set the prerelease to `z` if it's missing. So you can safely use `1.2.4-dev`.

