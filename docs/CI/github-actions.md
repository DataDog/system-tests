Add a file in your repo named `.github/workflows/system-tests.yml`:

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
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          repository: 'DataDog/system-tests'
          persist_credentials: false

      - name: Get component binary
        # you need to copy a valid binary of your component inside binaries/ folder.
        # You may need to get it from another action. For your first try, you can skip this step
        run: <...>

      - name: Build
        run: ./build.sh ${{ matrix.library }} -w ${{ matrix.weblog-variant }}

      - name: Run
        run: ./run.sh

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        if: ${{ always() }}
        with:
          name: logs_${{ matrix.library }}_${{ matrix.weblog-variant }}
          path: |
            logs/
            binaries/
```