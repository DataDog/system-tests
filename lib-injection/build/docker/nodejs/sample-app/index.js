var fs = require('fs');
var path = require('path');
var fork = require('child_process').fork;

process.on('SIGTERM', function (signal) {
  process.exit(0);
});

function crashme(req, res) {
  setTimeout(function () {
    process.kill(process.pid, 'SIGSEGV');

    res.writeHead(200, { 'Content-Type': 'text/plain' });
    res.end('Crashing process ' + process.pid);
  }, 2000); // Add a delay before crashing otherwise the telemetry forwarder leaves a zombie behind
}

function forkAndCrash(req, res) {
  var child = fork('child.js');

  child.on('close', function (code, signal) {
    res.writeHead(200, { 'Content-Type': 'text/plain' });
    res.end('Child process ' + child.pid + ' exited with code ' + code + ', signal ' + signal);
  });
}

function getChildPids(req, res) {
  var currentPid = process.pid;

  try {
    // Get the list of all process directories in /proc
    var procDir = '/proc';
    var procFiles = fs.readdirSync(procDir).filter(function (file) {
      return /^\d+$/.test(file)
    });

    var childPids = [];

    // Iterate through each process directory
    procFiles.forEach(function (pid) {
      var statusPath = path.join(procDir, pid, 'status');
      try {
        if (fs.existsSync(statusPath)) {
          var statusContent = fs.readFileSync(statusPath, 'utf8');

          // Find the PPid line in the status file
          var ppidMatch = statusContent.match(/^PPid:\s+(\d+)/m);
          if (ppidMatch) {
            var ppid = parseInt(ppidMatch[1], 10);
            if (ppid === currentPid) {
              childPids.push(pid);
            }
          }
        }
      } catch (error) {
        if (error.code !== 'ESRCH') {
          // Ignore ESRCH error, but throw other errors
          throw error;
        }
      }
    });

    // Send response back
    res.writeHead(200, { 'Content-Type': 'text/plain' });
    res.end(childPids.join(', '));
  } catch (error) {
    res.writeHead(500, { 'Content-Type': 'text/plain' });
    res.end('Error: ' + error.message);
  }
}

function getZombies(req, res) {
  try {
    var procDir = '/proc';
    var procFiles = fs.readdirSync(procDir).filter(function (file) {
      return /^\d+$/.test(file)
    });
    var zombieProcesses = [];

    // Iterate through each process directory
    procFiles.forEach(function (pid) {
      var statusPath = path.join(procDir, pid, 'status');
      try {
        if (fs.existsSync(statusPath)) {
          var statusContent = fs.readFileSync(statusPath, 'utf8');

          // Find the Name, State, and PPid lines in the status file
          var nameMatch = statusContent.match(/^Name:\s+(\S+)/m);
          var stateMatch = statusContent.match(/^State:\s+(\w)/m);
          var ppidMatch = statusContent.match(/^PPid:\s+(\d+)/m);

          if (nameMatch && stateMatch && ppidMatch) {
            var name = nameMatch[1];
            var state = stateMatch[1];
            var ppid = ppidMatch[1];

            // Check if the process state is 'Z' (zombie)
            if (state === 'Z') {
              zombieProcesses.push(name + ' (PID: ' + pid + ', PPID: ' + ppid + ')');
            }
          }
        }
      } catch (error) {
        if (error.code !== 'ESRCH') {
          // Ignore ESRCH error, but throw other errors
          throw error;
        }
      }
    });

    // Send response back
    res.writeHead(200, { 'Content-Type': 'text/plain' });
    res.end(zombieProcesses.join(', '));
  } catch (error) {
    res.writeHead(500, { 'Content-Type': 'text/plain' });
    res.end('Error: ' + error.message);
  }
}

require('http').createServer(function (req, res) {
  if (req.url === '/crashme') {
    crashme(req, res);
  } else if (req.url === '/fork_and_crash') {
    forkAndCrash(req, res);
  } else if (req.url === '/child_pids') {
    getChildPids(req, res);
  } else if (req.url === '/zombies') {
    getZombies(req, res);
  } else {
    res.end('Hello, world!\n')
  }
}).listen(18080, function () {
  console.log('listening on port 18080') // eslint-disable-line no-console
})
