"use strict";

const { join } = require('path')

const { readFileSync, statSync } = require('fs')

var config = {
    user: 'sa',
    password: 'yourStrong(!)Password',
    server: 'mssql',
    database: 'master',
    multipleStatements: true,
    options: {
        trustServerCertificate: true // change to true for local dev / self-signed certs
    }
};



function initData() {
    var mssql = require("mssql");
    console.log("loading mssql data")
    const query = readFileSync(join(__dirname, 'resources', 'mssql.sql')).toString()
    console.log("initData query: " + query)
    mssql.connect(config, function (err) {
        if (err) console.log(err);
        var request = new mssql.Request();
        request.query(query, function (err, recordset) {
            if (err) console.log(err)

            console.log(recordset);

        });
    });
    console.log("Creating mssql procedure")
    const query_procedure = "CREATE PROCEDURE helloworld "
        + " AS "
        + " BEGIN "
        + " SET NOCOUNT ON "

        + " SELECT id from demo where id=1"
        + " END "
    mssql.connect(config, function (err) {
        if (err) console.log(err);
        var request = new mssql.Request();
        request.query(query_procedure, function (err, recordset) {
            if (err) console.log(err)

            console.log(recordset);

        });
    });
}

function launchQuery(query) {
    var mssql = require("mssql");
    mssql.connect(config, function (err) {
        if (err) console.log(err);
        var request = new mssql.Request();
        request.query(query, function (err, recordset) {
            if (err) console.log(err)

            console.log(recordset);
            mssql.close();

        });
    });
}

function select() {
    launchQuery('SELECT * FROM demo ')
}

function update() {
    launchQuery('update demo set age=22 where id=1 ')
}

function insert() {
    launchQuery("insert into demo (id,name,age) values(3,'test3',163) ")
}

function deleteSQL() {
    launchQuery('delete from demo where id=2 ')
}

function callProcedure() {
    var mssql = require("mssql");
    mssql.connect(config, function (err) {
        if (err) console.log(err);
        var request = new mssql.Request();
        request.execute("helloworld", function (err, recordset) {
            if (err) console.log(err)

            console.log(recordset);

        });
    });
}

function selectError() {
    launchQuery('SELECT * FROM demossssss')
}
function doOperation(operation) {
    console.log("Selecting operation");
    switch (operation) {
        case "select":
            select();
            break;
        case "select_error":
            selectError();
            break;
        case "insert":
            insert();
            break;
        case "delete":
            deleteSQL();
            break;
        case "update":
            update();
            break;
        case "procedure":
            callProcedure();
            break;
        default:
            console.log("Operation " + crudOp + " not allowed");

    }
}
function init(app) {
    console.log("Initializing mssql module");
    initData();
};
module.exports = {
    init: init,
    doOperation: doOperation
};