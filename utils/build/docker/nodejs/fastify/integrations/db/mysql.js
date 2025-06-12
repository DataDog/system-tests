'use strict'

const { join } = require('path')
const mysql = require('mysql2')
const { readFileSync } = require('fs')

function getConnection () {
  const con = mysql.createConnection({
    host: 'mysqldb',
    user: 'mysqldb',
    password: 'mysqldb',
    database: 'mysql_dbname',
    multipleStatements: true
  })

  con.connect(function (err) {
    if (err) throw err
    console.log('Connected!')
  })
  return con
}
async function launchQuery (query) {
  return new Promise(function (resolve, reject) {
    // simple query
    const connection = getConnection()
    const res = connection.query(
      query,
      function (err, results, fields) {
        if (err) {
          console.log('Error launching mysql query:' + err)
          return resolve('Error on mysql query')
        }
        console.log('mysql query result:' + results)
        const sql = res.sql
        resolve(sql)
      }
    )
  })
}
async function initData () {
  console.log('loading mysql data')
  const query = readFileSync(join(__dirname, 'resources', 'mysql.sql')).toString()
  console.log('Create query: ' + query)
  return await launchQuery(query)
}

async function select () {
  const query = 'SELECT * FROM demo where id=1 or id IN (3, 4)'
  return await launchQuery(query)
}

async function selectDbm () {
  const query = 'SELECT version()'
  return launchQuery(query).then((result) => {
    return result
  })
}

async function update () {
  const query = 'update demo set age=22 where id=1 '
  return await launchQuery(query)
}

async function insert () {
  const query = "insert into demo (id,name,age) values(3,'test3',163) "
  return await launchQuery(query)
}

async function deleteSQL () {
  const query = 'delete from demo where id=2 or id=11111111'
  return await launchQuery(query)
}

async function callProcedure () {
  const query = 'call test_procedure(?,?)'
  console.log('Calling procedure....')
  return new Promise(function (resolve, reject) {
    getConnection().query(query, [1, 'test'], (error, results, fields) => {
      if (error) {
        console.log('Error calling procedure:' + error.message)
        return resolve('Error on mysql procedure')
      }
      console.log('Ok. Procedure executed!')
      resolve('mysql procedure done')
    })
  })
}

async function selectError () {
  const query = 'SELECT * FROM demossssss where id=1 or id=233333'
  return await launchQuery(query)
}
async function doOperation (operation) {
  console.log('Selecting operation:')
  switch (operation) {
    case 'init':
      return await initData()
    case 'select':
      return await select()
    case 'execute':
      return await selectDbm()
    case 'select_error':
      return await selectError()
    case 'insert':
      return await insert()
    case 'delete':
      return await deleteSQL()
    case 'update':
      return await update()
    case 'procedure':
      console.log('Executing ' + operation + ' db operation')
      return await callProcedure()
    default:
      console.log('Operation ' + operation + ' not allowed')
  }
}

module.exports = {
  doOperation
}
