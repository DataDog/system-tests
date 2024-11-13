const fs = require('fs');
const path = require('path');
const { fork } = require('child_process');

process.on('SIGTERM', (signal) => {
  process.exit(0);
});

function forkAndCrash(req, res) {
  const child = fork('child.js');

  child.on('exit', (code, signal) => {
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
    });

    // Send response back
    res.writeHead(200, { 'Content-Type': 'text/plain' });
    res.end(`${childPids.join(', ')}`);
  } catch (error) {
    res.writeHead(500, { 'Content-Type': 'text/plain' });
    res.end(`Error: ${error.message}`);
  }
}

require('http').createServer((req, res) => {
  if (req.url === '/fork_and_crash') {
    forkAndCrash(req, res);
   } else if (req.url === '/child_pids') {
    getChildPids(req, res);    
  } else {
    res.end('Hello, world!\n')
  }
}).listen(18080, () => {
  console.log('listening on port 18080') // eslint-disable-line no-console
})
