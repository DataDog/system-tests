'use strict'

const tracer = require('dd-trace').init({ debug: true });

const app = require('express')();

app.use(require('body-parser').json());
app.use(require('body-parser').urlencoded());
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

app.listen(7777, '0.0.0.0', () => {
  tracer.trace('init.service', () => {});
  console.log('listening');
});
