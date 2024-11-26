const fs = require('fs');
const path = require('path');
const { fork } = require('child_process');

process.on('SIGTERM', (signal) => {
  process.exit(0);
});

function crashme(req, res) {
  setTimeout(() => {
    process.kill(process.pid, 'SIGSEGV');

    res.writeHead(200, { 'Content-Type': 'text/plain' });
    res.end(`Crashing process ${process.pid}`);
  }, 2000); // Add a delay before crashing otherwise the telemetry forwarder leaves a zombie behind
}

function forkAndCrash(req, res) {
  const child = fork('child.js');

  child.on('close', (code, signal) => {
    res.writeHead(200, { 'Content-Type': 'text/plain' });
    res.end(`Child process ${child.pid} exited with code ${code}, signal ${signal}`);
  });
}

function getChildPids(req, res) {
  const currentPid = process.pid;

  try {
    // Get the list of all process directories in /proc
    const procDir = '/proc';
    const procFiles = fs.readdirSync(procDir).filter(file => /^\d+$/.test(file));

    let childPids = [];

    // Iterate through each process directory
    procFiles.forEach(pid => {
      const statusPath = path.join(procDir, pid, 'status');
      try {
        if (fs.existsSync(statusPath)) {
          const statusContent = fs.readFileSync(statusPath, 'utf8');

          // Find the PPid line in the status file
          const ppidMatch = statusContent.match(/^PPid:\s+(\d+)/m);
          if (ppidMatch) {
            const ppid = parseInt(ppidMatch[1], 10);
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
    res.end(`${childPids.join(', ')}`);
  } catch (error) {
    res.writeHead(500, { 'Content-Type': 'text/plain' });
    res.end(`Error: ${error.message}`);
  }
}

function getZombies(req, res) {
  try {
    const procDir = '/proc';
    const procFiles = fs.readdirSync(procDir).filter(file => /^\d+$/.test(file));
    let zombieProcesses = [];

    // Iterate through each process directory
    procFiles.forEach(pid => {
      const statusPath = path.join(procDir, pid, 'status');
      try {
        if (fs.existsSync(statusPath)) {
          const statusContent = fs.readFileSync(statusPath, 'utf8');

          // Find the Name, State, and PPid lines in the status file
          const nameMatch = statusContent.match(/^Name:\s+(\S+)/m);
          const stateMatch = statusContent.match(/^State:\s+(\w)/m);
          const ppidMatch = statusContent.match(/^PPid:\s+(\d+)/m);

          if (nameMatch && stateMatch && ppidMatch) {
            const name = nameMatch[1];
            const state = stateMatch[1];
            const ppid = ppidMatch[1];

            // Check if the process state is 'Z' (zombie)
            if (state === 'Z') {
              zombieProcesses.push(`${name} (PID: ${pid}, PPID: ${ppid})`);
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
    res.end(`${zombieProcesses.join(', ')}`);
  } catch (error) {
    res.writeHead(500, { 'Content-Type': 'text/plain' });
    res.end(`Error: ${error.message}`);
  }
}

require('http').createServer((req, res) => {
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
}).listen(18080, () => {
  console.log('listening on port 18080') // eslint-disable-line no-console
})
