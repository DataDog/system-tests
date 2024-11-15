process.on('SIGTERM', (signal) => {
  process.exit(0);
});

import { createServer } from 'http';

createServer((req, res) => {
  res.end('Hello, world!\n')
}).listen(18080, () => {
  console.log('listening on port 18080') // eslint-disable-line no-console
})
