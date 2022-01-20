## Requirements

* Python 3.8 or higher
* `pip install aiohttp requests`

## Prepare 

1. Run an app
2. Get the `main.py` script
3. Even if the WAF should run also on 404, you may want to modify `TESTED_PATHS`
4. Set two mandatory env vars (which will name the output files):
    1. `SYSTEM_TESTS_LIBRARY` to whatever you want (usually your lang name)
    2. `DD_APPSEC_ENABLED` to `true` if you app is running with appsec, `false` otherwise
5. Set two optional env vars:
   1. `WEBLOG_URL` to point to your app
   2. `LOG_FOLDER` to save your results to the good location

## Run

1. Run `python main.py`
2. Re-run the app with (or without appsec), change `DD_APPSEC_ENABLED`, and rerun `python main.py`.

## Display

Get the `process.py`, set `LOG_FOLDER` env var if needed, and run it.

## Example

```
# install dependencies
pip install -r scenarios/perfs/requirements.txt

# start your app with appsec enabled
env DD_APPSEC_ENABLED=true DD_DIAGNOSTICS=false bundle exec puma -p 9292
# outputs log/stats_ruby_with_appsec.json
env SYSTEM_TESTS_LIBRARY=ruby DD_APPSEC_ENABLED=true WEBLOG_URL='http://127.0.0.1:9292' LOG_FOLDER="${PWD}/logs" python scenarios/perfs/main.py

# start your app with appsec disabled
env DD_APPSEC_ENABLED=false DD_DIAGNOSTICS=false bundle exec puma -p 9292
# outputs log/stats_ruby_without_appsec.json
env SYSTEM_TESTS_LIBRARY=ruby DD_APPSEC_ENABLED=true WEBLOG_URL='http://127.0.0.1:9292' LOG_FOLDER="${PWD}/logs" python scenarios/perfs/main.py

env LOG_FOLDER="${PWD}/logs" python scenarios/perfs/process.py
```
