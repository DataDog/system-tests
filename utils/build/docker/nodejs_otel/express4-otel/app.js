"use strict";


const pgsql = require('./integrations/db/postgres');
const mysql = require('./integrations/db/mysql');
const mssql = require('./integrations/db/mssql');

const app = require("express")();
const fs = require('fs');

app.use(require("body-parser").json());
app.use(require("body-parser").urlencoded({ extended: true }));
app.use(require("express-xml-bodyparser")());
app.use(require("cookie-parser")());

app.all("/", (req, res) => {
  console.log("Received a request");
  res.send("Hello\n");
});


// Endpoints below mirror the Datadog express weblog so the OpenTelemetry HTTP
// semantic-convention suite can also be pointed at the upstream OpenTelemetry SDK. Keep the
// paths and the query parameter names identical to utils/build/docker/nodejs/express/app.js.
app.get("/sample_rate_route/:i", (req, res) => {
  res.send("OK");
});


app.get("/status", (req, res) => {
  res.status(parseInt(req.query.code, 10) || 200).send("OK");
});


app.get("/make_distant_call", (req, res) => {
  const http = require("http");
  const parsedUrl = new URL(req.query.url);
  const method = req.query.method || "GET";

  const request = http.request(parsedUrl, { method }, (response) => {
    let responseBody = "";
    response.on("data", (chunk) => { responseBody += chunk; });
    response.on("end", () => {
      res.json({
        url: req.query.url,
        status_code: response.statusCode,
        request_headers: request.getHeaders(),
        response_headers: response.headers
      });
    });
  });

  request.on("error", (error) => {
    res.json({ url: req.query.url, status_code: 0, error: String(error) });
  });

  request.end();
});


app.get("/healthcheck", (req, res) => {
  var otel_data = JSON.parse(fs.readFileSync('node_modules/@opentelemetry/auto-instrumentations-node/package.json', 'utf8'));

  res.json({
    status: 'ok',
    library: {
      name: 'nodejs_otel',
      version: otel_data.version
    }
  })
});


app.get('/db', async (req, res) => {
  console.log("Service: " + req.query.service)
  console.log("Operation: " + req.query.operation)

  var opResponse = "Service " + req.query.service + " not supported"
  if (req.query.service == "postgresql") {
    res.send(await pgsql.doOperation(req.query.operation));
  } else if (req.query.service == "mysql") {
    res.send(await mysql.doOperation(req.query.operation));
  } else if (req.query.service == "mssql") {
    res.send(await mssql.doOperation(req.query.operation));
  }
});


app.listen(7777, '0.0.0.0', () => {
  console.log('listening');
});
