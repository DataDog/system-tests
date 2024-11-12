const { fork, exec } = require('child_process');

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
  const psCommand = `ps -eo ppid,pid,comm`;

  exec(psCommand, (error, stdout, stderr) => {
    if (error) {
      res.writeHead(500, { 'Content-Type': 'text/plain' });
      res.end(`Error executing command: ${error.message}`);
    } else {
      const lines = stdout.split('\n');
      const childPids = [];

      lines.forEach(line => {
        const parts = line.trim().split(/\s+/);
        if (parts.length >= 3) {
          const ppid = parseInt(parts[0], 10);
          const pid = parseInt(parts[1], 10);
          const command = parts.slice(2).join(' ');

          // If the PPID matches the current process ID, it is a child process
          if (ppid === currentPid) {
            childPids.push({ pid, command });
          }
        }
      });

      const response = childPids.map(proc => `PID: ${proc.pid}, Command: ${proc.command}`).join('\n');
      res.writeHead(200, { 'Content-Type': 'text/plain' });
      res.end(response);
    }
  });
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
