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

require('./iast')(app, tracer);

app.get('/load_dependency', (req, res) => {
  console.log('Load dependency endpoint');
  var glob = require("glob")
  res.send("Loaded a dependency")
 }); 

app.listen(7777, '0.0.0.0', () => {
  tracer.trace('init.service', () => {});
  console.log('listening');
});
