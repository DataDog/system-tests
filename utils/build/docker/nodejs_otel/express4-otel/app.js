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

app.get("/", (req, res) => {
  console.log("Received a request");
  res.send("Hello\n");
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
