'use strict'

import { Request, Response } from "express";

const tracer = require('dd-trace').init({ debug: true });

const app = require('express')();

app.use(require('body-parser').json());
app.use(require('body-parser').urlencoded({ extended: true }));
app.use(require('express-xml-bodyparser')());
app.use(require('cookie-parser')());

app.get('/', (req: Request, res: Response) => {
  console.log('Received a request');
  res.send('Hello\n');
});

app.all(['/waf', '/waf/*'], (req: Request, res: Response) => {
  res.send('Hello\n');
});

app.get('/sample_rate_route/:i', (req: Request, res: Response) => {
  res.send('OK');
});

app.get('/params/:value', (req: Request, res: Response) => {
  res.send('OK');
});

app.get('/headers', (req: Request, res: Response) => {
  res.set({
    'content-type': 'text/plain',
    'content-length': '42',
    'content-language': 'en-US',
  });

  res.send('Hello, headers!');
});

app.listen(7777, '0.0.0.0', () => {
  tracer.trace('init.service', () => {});
  console.log('listening');
});
