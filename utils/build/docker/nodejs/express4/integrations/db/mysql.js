"use strict";

const { join } = require('path')
var mysql = require('mysql2');
const { readFileSync, statSync } = require('fs')

function getConnection() {
    var con = mysql.createConnection({
        host: "mysqldb",
        user: "mysqldb",
        password: "mysqldb",
        database: "world",
        multipleStatements: true
    });

    con.connect(function (err) {
        if (err) throw err;
        console.log("Connected!");
    });
    return con;
}

function initData() {
    console.log("loading mysql data")
    const query = readFileSync(join(__dirname, 'resources', 'mysql.sql')).toString()
    console.log("Create query: " + query)
    getConnection().query(query, function (err, result) {
        if (err) throw err;
        console.log("Result: " + result);
    });
}

function select() {
    const query = 'SELECT * FROM demo '
    getConnection().query(query, function (err, result) {
        if (err) throw err;
        console.log("Result: " + result);
    });
}

function update() {
    const query = 'update demo set age=22 where id=1 '
    getConnection().query(query, function (err, result) {
        if (err) throw err;
        console.log("Result: " + result);
    });
}

function insert() {
    const query = "insert into demo (id,name,age) values(3,'test3',163) "
    getConnection().query(query, function (err, result) {
        if (err) throw err;
        console.log("Result: " + result);
    });
}

function deleteSQL() {
    const query = 'delete from demo where id=2 '
    getConnection().query(query, function (err, result) {
        if (err) throw err;
        console.log("Result: " + result);
    });
}

function callProcedure() {
    const query = 'call test_procedure(?)'

    getConnection().query(query, 1, (error, results, fields) => {
        if (error) {
            return console.error(error.message);
        }
        console.log(results[0]);
    });
}

function selectError() {
    const query = 'SELECT * FROM demossssss'
    getConnection().query(query, function (err, result) {
        if (err) console.log(err);
        console.log("Result: " + result);
    });
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
    console.log("Initializing nodejs module");
    initData();
};
module.exports = {
    init: init,
    doOperation: doOperation
};