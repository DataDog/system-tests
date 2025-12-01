'use strict'

const { join } = require('path')
const { Client } = require('pg')
const { readFileSync } = require('fs')
let createDBMSpy = null
let getDbmQueryString = null

// load functions requiring dd-trace as long as this isn't an OTEL test
if (!process.env.OTEL_INTEGRATIONS_TEST) {
  try {
    ({ createDBMSpy, getDbmQueryString } = require('./utils'))
  } catch (error) {
    // pass
  }
}

async function launchQuery (query) {
  return new Promise(function (resolve, reject) {
    const client = new Client()
    client.connect().then(() => {
      client.query(query).then((queryResult) => {
        console.log('Postgres query result:' + queryResult)
        resolve('Postgres query done!')
      }).catch((err) => {
        console.log(err)
        resolve('Error on postgres query')
      })
    }).catch((err) => {
      console.log(err)
      reject(err)
    })
  })
}

async function initData () {
  console.log('loading sql data')
  const query = readFileSync(join(__dirname, 'resources', 'postgres.sql')).toString()
  return await launchQuery(query)
}

async function select () {
  const sql = 'SELECT * FROM demo where id=1 or id IN (3, 4)'
  return await launchQuery(sql)
}

async function selectDbm () {
  const dbmCommentSpy = createDBMSpy()
  const sql = 'SELECT version()'
  return launchQuery(sql).then(() => {
    dbmCommentSpy.restore()
    return getDbmQueryString()
  }).catch((error) => {
    console.log(error)
    dbmCommentSpy.restore()
    return error
  })
}

// async function selectManyDbm () {
//   const sql = 'SELECT version()'
//   return await launchQuery(sql)
// }

async function update () {
  const sql = "update demo set age=22 where name like '%tes%' "
  return await launchQuery(sql)
}

async function insert () {
  const sql = "insert into demo (id,name,age) values(3,'test3',163) "
  return await launchQuery(sql)
}

async function deleteSQL () {
  const sql = 'delete from demo where id=2 or id=11111111'
  return await launchQuery(sql)
}

async function callProcedure () {
  const sql = "call helloworld(1,'test') "
  return await launchQuery(sql)
}

async function selectError () {
  const sql = 'SELECT * FROM demossssss where id=1 or id=233333'
  return await launchQuery(sql)
}

async function doOperation (operation) {
  console.log('Selecting operation')
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
      return await callProcedure()
    default:
      console.log('Operation ' + operation + ' not allowed')
  }
}

module.exports = {
  doOperation
}
