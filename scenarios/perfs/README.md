## Requirements

* Python 3.8 or higher
* `pip install aiohttp requests`

## Prepare 

1. Run an app
2. Get the `main.py` script
   1. modify `WEBLOG_URL` to point to your app
   2. modify `LOG_FOLDER` to save your results to the good location
3. Even if the WAff should run also on 404, you may want to modify `TESTED_PATHS`
4. Set two env var: 
    1. `SYSTEM_TESTS_LIBRARY` to whatever you want (usually your lang name)
    2. `DD_APPSEC_ENABLED` to `true` if you app is running with appsec, `false` otherwise

## Run 

1. Run `python main.py`
2. Re-run the app with (or without appsec), change `DD_APPSEC_ENABLED`, and rerun `python main.py`.

## Display

Get the `process.py`, modify `LOG_FOLDER` if needed, and run it.