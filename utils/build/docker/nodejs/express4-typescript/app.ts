'use strict'

import { Request, Response } from "express";

const tracer = require('dd-trace').init({ debug: true });

const app = require('express')();
var axios = require('axios');

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

app.get('/identify', (req: Request, res: Response) => {
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

app.get('/status', (req: Request, res: Response) => {
  res.status(parseInt('' + req.query.code)).send('OK');
});

app.get("/make_distant_call", (req: Request, res: Response) => {
  const url = req.query.url;
  console.log(url);

  axios.get(url)
  .then((response: Response) => {
    res.json({
      url: url,
      status_code: response.statusCode,
      request_headers: null,
      response_headers: null,
    });
  })
  .catch((error: Error) => {
    console.log(error);
    res.json({
      url: url,
      status_code: 500,
      request_headers: null,
      response_headers: null,
    });
  });
});

app.get("/user_login_success_event", (req: Request, res: Response) => {
  tracer.appsec.trackUserLoginSuccessEvent({
    id: "system_tests_user",
    email: "system_tests_user@system_tests_user.com",
    name: "system_tests_user"
  }, { metadata0: 'value0', metadata1: 'value1' });

  res.send("OK");
});

app.get("/user_login_failure_event", (req: Request, res: Response) => {
  tracer.appsec.trackUserLoginFailureEvent('system_tests_user', true, { metadata0: 'value0', metadata1: 'value1' });

  res.send("OK");
});

app.get("/custom_event", (req: Request, res: Response) => {
  tracer.appsec.trackCustomEvent('system_tests_event', { metadata0: 'value0', metadata1: 'value1' });

  res.send("OK");
});

app.listen(7777, '0.0.0.0', () => {
  tracer.trace('init.service', () => {});
  console.log('listening');
});
