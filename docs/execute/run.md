`run.sh` accepts several options:

## Run all tests

```bash
./run.sh
```

## Run only one file

```bash
./run.sh tests/test_waf.py
```

## Run only one class, or one method

```bash
./run.sh tests/test_waf.py::Test_WAFAddresses

# and one method:
./run.sh tests/test_waf.py::Test_WAFAddresses::test_post_json_value
```

## Spawn componenents, but do nothing

```bash
./run.sh SLEEP

# play with the weblog, and look inside logs/interfaces/ what's happening
```
