"use strict";

const tracer = require("dd-trace").init({
  debug: true,
  experimental: {
    iast: {
      enabled: true,
      requestSampling: 100,
      maxConcurrentRequests: 4,
      maxContextOperations: 30,
    },
  },
});

const app = require("express")();
var axios = require('axios');
app.use(require("body-parser").json());
app.use(require("body-parser").urlencoded({ extended: true }));
app.use(require("express-xml-bodyparser")());
app.use(require("cookie-parser")());

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

require("./iast")(app, tracer);

app.listen(7777, "0.0.0.0", () => {
  tracer.trace("init.service", () => {});
  console.log("listening");
});
