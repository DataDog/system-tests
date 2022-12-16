## OSError: source code not available

When an interface test fails, source code that trigger the fail is logged. If `OSError: source code not available` 
is printed, it means that you have previously ran tests outside docker, and python took the source from cached version.

=> Remove any `__pycache__` folder

## `run.sh` fails at the very beginning, saying `runner` is unhealthy

You may have python errors, try `docker-compose up runner` to directly see them

## `run.sh` fails at the very beginning, saying `agent` is unhealthy

Internet connection issue?

