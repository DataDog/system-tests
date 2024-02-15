First of all, add two secrets:

1. a valid github token in `GH_TOKEN`
1. a valid staging API key token in `DD_API_KEY`

Then, add a file in your repo named `.github/workflows/system-tests.yml`:

```yaml
name: System Tests

on:
  pull_request:
    branches:
      - "**"

jobs:
  system-tests:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        include:
          - library: golang
            weblog-variant: net-http
      fail-fast: false
    env:
      TEST_LIBRARY: ${{ matrix.library }}
      WEBLOG_VARIANT: ${{ matrix.weblog-variant }}
      DD_API_KEY: ${{ secrets.DD_API_KEY }}
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          repository: 'DataDog/system-tests'
          token: ${{ secrets.GH_TOKEN }}

      - name: Get component binary
        # you need to copy a valid binary of your component inside binaries/ folder.
        # You may need to get it from another action. For your first try, you can skip this step
        run: <...>

      - name: Build
        run: ./build.sh

      - name: Run
        run: ./run.sh

      - name: Upload artifact
        uses: actions/upload-artifact@v3
        if: ${{ always() }}
        with:
          name: logs_${{ matrix.library }}_${{ matrix.weblog-variant }}
          path: |
            logs/
            binaries/
```