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
  const psCommand = `pgrep -P ${currentPid}`;

  exec(psCommand, (error, stdout, stderr) => {
    if (error) {
      res.writeHead(500, { 'Content-Type': 'text/plain' });
      res.end(`Error executing command: ${error.message}`);
    } else {
      res.writeHead(200, { 'Content-Type': 'text/plain' });
      res.end(stdout);
    }
  });
}

require('http').createServer((req, res) => {
  if (req.url === '/fork_and_crash') {
    forkAndCrash(req, res);
   } else if (req.url === '/child-pids') {
    getChildPids(req, res);    
  } else {
    res.end('Hello, world!\n')
  }
}).listen(18080, () => {
  console.log('listening on port 18080') // eslint-disable-line no-console
})
