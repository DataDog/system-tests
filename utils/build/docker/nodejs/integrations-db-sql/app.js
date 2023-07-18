"use strict";

const tracer = require('dd-trace').init({
  debug: true
});

const app = require("express")();
const pgsql = require('./postgres');
const mysql = require('./mysql');

app.use(require("body-parser").json());
app.use(require("body-parser").urlencoded({ extended: true }));
app.use(require("express-xml-bodyparser")());
app.use(require("cookie-parser")());


app.get("/", (req, res) => {
  console.log("Received a request");
  res.send("Hello\n");
});


//"/db?service={integration_db_id}&operation=select"
app.get('/db', (req, res) => {
  console.log("Service: " + req.query.service)
  console.log("Operation: " + req.query.operation)
  if (req.query.service == "postgresql") {
    pgsql.doOperation(req.query.operation)
  }else  if (req.query.service == "mysql") {
    mysql.doOperation(req.query.operation)
  }

});


app.listen(7777, '0.0.0.0', () => {
  tracer.trace('init.service', () => { });
  console.log('listening');
  pgsql.init();
  mysql.init();
});

