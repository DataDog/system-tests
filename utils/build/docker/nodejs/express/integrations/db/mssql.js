'use strict'

const { join } = require('path')

const { readFileSync } = require('fs')

const config = {
  user: 'sa',
  password: 'yourStrong(!)Password',
  server: 'mssql',
  database: 'master',
  multipleStatements: true,
  options: {
    trustServerCertificate: true // change to true for local dev / self-signed certs
  }
}

async function initData () {
  const queryProcedure = 'CREATE PROCEDURE helloworld ' +
    ' @Name VARCHAR(100),@Test VARCHAR(100) ' +
    ' AS ' +
    ' BEGIN ' +
    ' SET NOCOUNT ON ' +

    ' SELECT id from demo where id=1' +
    ' END '

  const query = readFileSync(join(__dirname, 'resources', 'mssql.sql')).toString()
  await launchQuery(query)
  return await launchQuery(queryProcedure)
}

async function launchQuery (query) {
  const mssql = require('mssql')
  return new Promise(function (resolve, reject) {
    mssql.connect(config, function (err) {
      if (err) {
        console.log('Error connecting mssql database:' + err)
        return reject(new Error('Error on database connection'))
      }
      const request = new mssql.Request()
      request.query(query, function (err, recordset) {
        if (err) {
          console.log('Error launching mssql query:' + err)
          return resolve('Error on mssql query')
        }

        console.log('mssql query result:' + recordset)
        // mssql.close();
        return resolve('Mssql query done!')
      })
    })
  })
}

async function select () {
  return await launchQuery('SELECT * FROM demo where id=1 or id IN (3, 4)')
}

async function update () {
  return await launchQuery('update demo set age=22 where id=1 ')
}

async function insert () {
  return await launchQuery("insert into demo (id,name,age) values(3,'test3',163) ")
}

async function deleteSQL () {
  return await launchQuery('delete from demo where id=2 or id=11111111')
}

async function callProcedure () {
  const mssql = require('mssql')
  return new Promise(function (resolve, reject) {
    mssql.connect(config, function (err) {
      if (err) {
        console.log('Error connecting mssql database:' + err)
        return reject(new Error('Error on database connection'))
      }
      const request = new mssql.Request()
      request.input('Name', 'MyParam').input('Test', 'MyTestParam').execute('helloworld', function (err, recordset) {
        if (err) {
          console.log('Error launching mssql query:' + err)
          return resolve('Error on mssql query')
        }

        console.log('mssql query result:' + recordset)
        // mssql.close();
        return resolve('Mssql query done!')
      })
    })
  })
}

async function selectError () {
  return await launchQuery('SELECT * FROM demossssss where id=1 or id=233333')
}

async function doOperation (operation) {
  console.log('Selecting operation')
  switch (operation) {
    case 'init':
      return await initData()
    case 'select':
      return await select()
    case 'select_error':
      return await selectError()
    case 'insert':
      return await insert()
    case 'delete':
      return await deleteSQL()
    case 'update':
      return await update()
    case 'procedure':
      return await callProcedure()
    default:
      console.log('Operation ' + operation + ' not allowed')
  }
}

module.exports = {
  doOperation
}
