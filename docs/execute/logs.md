System tests export a lot of data in `logs/` folder, and this folder is usually exported in CI artifacts. Here is a small explanation of what they contains, in bold the file you may find the most interesting infos:

- `logs/docker/` raw log of docker containers. They are quite hard to read as they contain coloring chars. `cat` is your friend.
  - `logs/docker/weblog.log`: **Agent's log level is set to DEBUG during system tests, so you'll find plenty of info in it**
  - `logs/docker/runner.log`: Test runner, you'll have exactly the same data in standart output.
- `logs/interfaces/`: raw data seen in interfaces. File a re prefixed with an index, so you'll know what was the timeline
  - `logs/interfaces/library`: **library -> agent communication, key folder if you own a library**
  - `logs/interfaces/agent`: **agent -> bakcend communication, key folder if you own an agent**
- `logs/interfaces.log`: Debug log of what's happening on interfaces
- `logs/pytest.log`: **Entire debug, including `logs/interfaces.log`, lot of infos here**
- `logs/report.json`: Technical data about the test run, will be exported to dashboard
- `logs/weblog_image.json`: Result of `docker inspect` on [weblog](../edit/weblog.md) images
