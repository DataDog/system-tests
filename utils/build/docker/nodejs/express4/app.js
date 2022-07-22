'use strict'

const tracer = require('dd-trace').init({ debug: true });

const app = require('express')();

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

app.get('/iast/insecure_hashing', (req, res) => {
  const span = tracer.scope().active();
  span.setTag('appsec.event"', true);

  const crypto = require('crypto');
  const name = 'insecure';
  var supportedAlgorithms = [ 'md5', 'md4', 'sha1' ];
  let algorithmName = req.query.algorithmName;

  if (supportedAlgorithms.includes(algorithmName)){
    supportedAlgorithms = supportedAlgorithms.filter(function(value, index, arr){ 
      return value == algorithmName;
    });
  }

  var outputHashes = "";
  supportedAlgorithms.forEach(algorithm => {
    var hash = crypto.createHash(algorithm).update(name).digest('hex')
    outputHashes += `--- ${algorithm}:${hash} ---`
  });
  
  res.send(outputHashes);
});

app.listen(7777, '0.0.0.0', () => {
  tracer.trace('init.service', () => {});
  console.log('listening');
});
