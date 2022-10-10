'use strict'

const tracer = require('dd-trace').init({ debug: true,  experimental: {
  iast: {
    enabled: true,
    requestSampling: 100,
    maxConcurrentRequests: 4,
    maxContextOperations: 30
  }
} });

const app = require('express')();
const crypto = require('crypto');

app.use(require('body-parser').json());
app.use(require('body-parser').urlencoded({ extended: true }));
app.use(require('express-xml-bodyparser')());
app.use(require('cookie-parser')());

app.get('/', (req, res) => {
  console.log('Received a request');
  res.send('Hello\n');
});

app.all(['/waf', '/waf/*'], (req, res) => {
  res.send('Hello\n');
});

app.get('/sample_rate_route/:i', (req, res) => {
  res.send('OK');
});

app.get('/params/:value', (req, res) => {
  res.send('OK');
});

app.get('/headers', (req, res) => {
  res.set({
    'content-type': 'text/plain',
    'content-length': '42',
    'content-language': 'en-US',
  });

  res.send('Hello, headers!');
});

app.get('/identify', (req, res) => {
  tracer.setUser({
    id: 'usr.id',
    email: 'usr.email',
    name: 'usr.name',
    session_id: 'usr.session_id',
    role: 'usr.role',
    scope: 'usr.scope'
  });

  res.send('OK');
});

app.get('/status', (req, res) => {
  res.status(parseInt(req.query.code)).send('OK');
});

app.get('/iast/insecure_hashing/deduplicate', (req, res) => {
  const span = tracer.scope().active();
  span.setTag('appsec.event"', true);

  var supportedAlgorithms = [ 'md5', 'sha1' ];

  var outputHashes = "";
  supportedAlgorithms.forEach(algorithm => {
    var hash = crypto.createHash(algorithm).update('insecure').digest('hex')
    outputHashes += `--- ${algorithm}:${hash} ---`
  });

  res.send(outputHashes);
});

app.get('/iast/insecure_hashing/multiple_hash', (req, res) => {
  const span = tracer.scope().active();
  span.setTag('appsec.event"', true);

  const name = 'insecure';
  var outputHashes = crypto.createHash('md5').update(name).digest('hex');
  outputHashes += `--- ` + crypto.createHash('sha1').update(name).digest('hex')

  res.send(outputHashes);
});

app.get('/iast/insecure_hashing/test_secure_algorithm', (req, res) => {
  const span = tracer.scope().active();
  span.setTag('appsec.event"', true);

  res.send(crypto.createHash('sha256').update('insecure').digest('hex'));
});


app.get('/iast/insecure_hashing/test_md5_algorithm', (req, res) => {
  const span = tracer.scope().active();
  span.setTag('appsec.event"', true);

  res.send(crypto.createHash('md5').update('insecure').digest('hex'));
});

app.get('/iast/insecure_cipher/test_insecure_algorithm', (req, res) => {
  const span = tracer.scope().active();
  span.setTag('appsec.event"', true);
  const cipher = crypto.createCipheriv('des-ede-cbc', '1111111111111111', 'abcdefgh')
  res.send(Buffer.concat([cipher.update('12345'), cipher.final()]))
});

app.get('/iast/insecure_cipher/test_secure_algorithm', (req, res) => {
  const span = tracer.scope().active();
  span.setTag('appsec.event"', true);
  const cipher = crypto.createCipheriv('sha256', '1111111111111111', 'abcdefgh')
  res.send(Buffer.concat([cipher.update('12345'), cipher.final()]))
});

app.listen(7777, '0.0.0.0', () => {
  tracer.trace('init.service', () => {});
  console.log('listening');
});
