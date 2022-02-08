'use strict'

const tracer = require('dd-trace').init({ debug: true });

const app = require('express')();

app.use(require('body-parser').json());
app.use(require('body-parser').urlencoded({ extended: true }));
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
  res.send('OK')
})

app.get('/headers', (req, res) => {
  res.set({
    'content-type': 'text/plain',
    'content-length': '42',
    'content-language': 'en-US',
  })

  res.send('Hello, headers!')
});

app.listen(7777, '0.0.0.0', () => {
  tracer.trace('init.service', () => {});
  console.log('listening');
});
