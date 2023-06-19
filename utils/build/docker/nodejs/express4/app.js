"use strict";

const tracer = require("dd-trace").init({
  debug: true
});

const app = require("express")();
const axios = require('axios');
const fs = require('fs');
const passport = require('passport')


app.use(require("body-parser").json());
app.use(require("body-parser").urlencoded({ extended: true }));
app.use(require("express-xml-bodyparser")());
app.use(require("cookie-parser")());

require('./auth')(app, passport)

app.get("/", (req, res) => {
  console.log("Received a request");
  res.send("Hello\n");
});

app.all(["/waf", "/waf/*"], (req, res) => {
  res.send("Hello\n");
});

app.get("/sample_rate_route/:i", (req, res) => {
  res.send("OK");
});

app.get("/params/:value", (req, res) => {
  res.send("OK");
});

app.get("/headers", (req, res) => {
  res.set({
    "content-type": "text/plain",
    "content-length": "42",
    "content-language": "en-US",
  });

  res.send("Hello, headers!");
});

app.get("/identify", (req, res) => {
  tracer.setUser({
    id: "usr.id",
    email: "usr.email",
    name: "usr.name",
    session_id: "usr.session_id",
    role: "usr.role",
    scope: "usr.scope",
  });

  res.send("OK");
});

app.get("/status", (req, res) => {
  res.status(parseInt(req.query.code)).send("OK");
});

app.get("/make_distant_call", (req, res) => {
  const url = req.query.url;
  console.log(url);

  axios.get(url)
    .then(response => {
      res.json({
        url: url,
        status_code: response.statusCode,
        request_headers: null,
        response_headers: null,
      });
    })
    .catch(error => {
      console.log(error);
      res.json({
        url: url,
        status_code: 500,
        request_headers: null,
        response_headers: null,
      });
    });
});

app.get("/user_login_success_event", (req, res) => {
  const userId = req.query.event_user_id || "system_tests_user";

  tracer.appsec.trackUserLoginSuccessEvent({
    id: userId,
    email: "system_tests_user@system_tests_user.com",
    name: "system_tests_user"
  }, { metadata0: "value0", metadata1: "value1" });

  res.send("OK");
});

app.get("/user_login_failure_event", (req, res) => {
  const userId = req.query.event_user_id || "system_tests_user";
  let exists = true;
  if (req.query && req.query.hasOwnProperty("event_user_exists")) {
    exists = req.query.event_user_exists.toLowerCase() === "true"
  }

  tracer.appsec.trackUserLoginFailureEvent(userId, exists, { metadata0: "value0", metadata1: "value1" });

  res.send("OK");
});

app.get("/custom_event", (req, res) => {
  const eventName = req.query.event_name || "system_tests_event";

  tracer.appsec.trackCustomEvent(eventName, { metadata0: "value0", metadata1: "value1" });

  res.send("OK");
});

app.get("/users", (req, res) => {
  let user = {}
  if (req.query['user']) {
    user.id = req.query['user']
  } else {
    user.id = 'anonymous'
  }

  const shouldBlock = tracer.appsec.isUserBlocked(user)
  if (shouldBlock) {
    tracer.appsec.blockRequest(req, res)
  } else {
    res.send(`Hello ${user.id}`)
  }
});

app.get('/load_dependency', (req, res) => {
  console.log('Load dependency endpoint');
  const glob = require("glob")
  res.send("Loaded a dependency")
});

app.all('/tag_value/:tag/:status', (req, res) => {
  require('dd-trace/packages/dd-trace/src/plugins/util/web').root(req).setTag('appsec.events.system_tests_appsec_event.value', req.params.tag);

  for (const [k, v] of Object.entries(req.query)) {
    res.set(k, v);
  }

  res.status(req.params.status || 200).send('Value tagged');
});

app.get('/read_file', (req, res) => {
  const path = req.query['file'];
  fs.readFile(path, (err, data) => {
    if (err) {
      console.error(err);
      res.status(500).send("ko");
    }
    res.send(data);
  });
});

require("./iast")(app, tracer);

app.listen(7777, '0.0.0.0', () => {
  tracer.trace('init.service', () => {});
  console.log('listening');
});
