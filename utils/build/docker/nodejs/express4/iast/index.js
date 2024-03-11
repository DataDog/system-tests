'use strict'

const { Client } = require('pg')
const { readFileSync, statSync } = require('fs')
const { join } = require('path')
const crypto = require('crypto')
const { execSync } = require('child_process')
const https = require('https')
const { MongoClient } = require('mongodb')
const mongoSanitize = require('express-mongo-sanitize')
const ldap = require('../integrations/ldap')

async function initData () {
  const query = readFileSync(join(__dirname, '..', 'resources', 'iast-data.sql')).toString()
  const client = new Client()
  await client.connect()
  await client.query(query)
}

function initMiddlewares (app) {
  const hstsMissingInsecurePattern = /.*hstsmissing\/test_insecure$/gmi
  const xcontenttypeMissingInsecurePattern = /.*xcontent-missing-header\/test_insecure$/gmi
  app.use((req, res, next) => {
    if (!req.url.match(hstsMissingInsecurePattern)) {
      res.setHeader('Strict-Transport-Security', 'max-age=31536000')
    }
    if (!req.url.match(xcontenttypeMissingInsecurePattern)) {
      res.setHeader('X-Content-Type-Options', 'nosniff')
    }
    next()
  })
}

function initRoutes (app, tracer) {
  app.get('/iast/insecure_hashing/deduplicate', (req, res) => {
    const supportedAlgorithms = ['md5', 'sha1']

    let outputHashes = ''
    supportedAlgorithms.forEach(algorithm => {
      const hash = crypto.createHash(algorithm).update('insecure').digest('hex')
      outputHashes += `--- ${algorithm}:${hash} ---`
    })

    res.send(outputHashes)
  })

  app.get('/iast/insecure_hashing/multiple_hash', (req, res) => {
    const name = 'insecure'
    let outputHashes = crypto.createHash('md5').update(name).digest('hex')
    outputHashes += '--- ' + crypto.createHash('sha1').update(name).digest('hex')

    res.send(outputHashes)
  })

  app.get('/iast/insecure_hashing/test_secure_algorithm', (req, res) => {
    res.send(crypto.createHash('sha256').update('secure').digest('hex'))
  })

  app.get('/iast/insecure_hashing/test_md5_algorithm', (req, res) => {
    res.send(crypto.createHash('md5').update('insecure').digest('hex'))
  })

  app.get('/iast/insecure_cipher/test_insecure_algorithm', (req, res) => {
    const cipher = crypto.createCipheriv('des-ede-cbc', '1111111111111111', 'abcdefgh')
    res.send(Buffer.concat([cipher.update('12345'), cipher.final()]))
  })

  app.get('/iast/insecure_cipher/test_secure_algorithm', (req, res) => {
    const key = crypto.randomBytes(32)

    const iv = crypto.randomBytes(16)

    const cipher = crypto.createCipheriv('aes-256-cbc', Buffer.from(key), iv)
    res.send(Buffer.concat([cipher.update('12345'), cipher.final()]))
  })

  app.post('/iast/sqli/test_insecure', (req, res) => {
    const sql = 'SELECT * FROM IAST_USER WHERE USERNAME = \'' +
      req.body.username + '\' AND PASSWORD = \'' + req.body.password + '\''
    const client = new Client()
    client.connect().then(() => {
      return client.query(sql).then((queryResult) => {
        res.json(queryResult)
      })
    }).catch((err) => {
      res.status(500).json({ message: 'Error on request ' + err })
    })
  })

  app.post('/iast/sqli/test_secure', (req, res) => {
    const sql = 'SELECT * FROM IAST_USER WHERE USERNAME = $1 AND PASSWORD = $2'
    const values = [req.body.username, req.body.password]
    const client = new Client()
    client.connect().then(() => {
      return client.query(sql, values).then((queryResult) => {
        res.json(queryResult)
      })
    }).catch((err) => {
      res.status(500).json({ message: 'Error on request' + err })
    })
  })

  app.post('/iast/cmdi/test_insecure', (req, res) => {
    const result = execSync(req.body.cmd)
    res.send(result.toString())
  })

  app.post('/iast/path_traversal/test_insecure', (req, res) => {
    const stats = statSync(req.body.path)
    res.send(JSON.stringify(stats))
  })

  app.post('/iast/ssrf/test_insecure', (req, res) => {
    https.get(req.body.url, (clientResponse) => {
      clientResponse.on('data', function noop () {})
      clientResponse.on('end', () => {
        res.send('OK')
      })
    })
  })

  app.get('/iast/insecure-cookie/test_insecure', (req, res) => {
    res.cookie('insecure', 'cookie')
    res.send('OK')
  })

  app.get('/iast/insecure-cookie/test_secure', (req, res) => {
    res.setHeader('set-cookie', 'secure=cookie; Secure; HttpOnly; SameSite=Strict')
    res.cookie('secure2', 'value', { secure: true, httpOnly: true, sameSite: true })
    res.send('OK')
  })

  app.get('/iast/insecure-cookie/test_empty_cookie', (req, res) => {
    res.clearCookie('insecure')
    res.setHeader('set-cookie', 'empty=')
    res.cookie('secure3', '')
    res.send('OK')
  })

  app.get('/iast/no-httponly-cookie/test_insecure', (req, res) => {
    res.cookie('no-httponly', 'cookie')
    res.send('OK')
  })

  app.get('/iast/no-httponly-cookie/test_secure', (req, res) => {
    res.setHeader('set-cookie', 'httponly=cookie; Secure;HttpOnly;SameSite=Strict;')
    res.cookie('httponly2', 'value', { secure: true, httpOnly: true, sameSite: true })
    res.send('OK')
  })

  app.get('/iast/no-httponly-cookie/test_empty_cookie', (req, res) => {
    res.clearCookie('insecure')
    res.setHeader('set-cookie', 'httponlyempty=')
    res.cookie('httponlyempty2', '')
    res.send('OK')
  })

  app.get('/iast/no-samesite-cookie/test_insecure', (req, res) => {
    res.cookie('nosamesite', 'cookie')
    res.send('OK')
  })

  app.get('/iast/no-samesite-cookie/test_secure', (req, res) => {
    res.setHeader('set-cookie', 'samesite=cookie; Secure; HttpOnly; SameSite=Strict')
    res.cookie('samesite2', 'value', { secure: true, httpOnly: true, sameSite: true })
    res.send('OK')
  })

  app.get('/iast/no-samesite-cookie/test_empty_cookie', (req, res) => {
    res.clearCookie('insecure')
    res.setHeader('set-cookie', 'samesiteempty=')
    res.cookie('samesiteempty2', '')
    res.send('OK')
  })

  app.post('/iast/unvalidated_redirect/test_secure_header', (req, res) => {
    res.setHeader('location', 'http://dummy.location.com')
    res.send('OK')
  })

  app.post('/iast/unvalidated_redirect/test_insecure_header', (req, res) => {
    res.setHeader('location', req.body.location)
    res.send('OK')
  })

  app.post('/iast/unvalidated_redirect/test_secure_redirect', (req, res) => {
    res.redirect('http://dummy.location.com')
  })

  app.post('/iast/unvalidated_redirect/test_insecure_redirect', (req, res) => {
    res.redirect(req.body.location)
  })

  app.get('/iast/hstsmissing/test_insecure', (req, res) => {
    res.setHeader('Content-Type', 'text/html')
    res.end('<html><body><h1>Test</h1></html>')
  })

  app.get('/iast/hstsmissing/test_secure', (req, res) => {
    res.setHeader('Strict-Transport-Security', 'max-age=31536000')
    res.setHeader('X-Content-Type-Options', 'nosniff')
    res.send('<html><body><h1>Test</h1></html>')
  })

  app.get('/iast/xcontent-missing-header/test_insecure', (req, res) => {
    res.setHeader('Content-Type', 'text/html')
    res.end('<html><body><h1>Test</h1></html>')
  })

  app.get('/iast/xcontent-missing-header/test_secure', (req, res) => {
    res.setHeader('Content-Type', 'text/html')
    res.send('<html><body><h1>Test</h1></html>')
  })

  app.use('/iast/mongodb-nosql-injection/test_secure', mongoSanitize())
  app.post('/iast/mongodb-nosql-injection/test_secure', async function (req, res) {
    const url = 'mongodb://mongodb:27017/'
    const client = new MongoClient(url)
    await client.connect()
    const db = client.db('mydb')
    const collection = db.collection('test')
    await collection.find({
      param: req.body.key
    })
    res.send('OK')
  })

  // Same method, without sanitization middleware
  // DO NOT extract to one method, we should force different line numbers
  app.post('/iast/mongodb-nosql-injection/test_insecure', async function (req, res) {
    const url = 'mongodb://mongodb:27017/'
    const client = new MongoClient(url)
    await client.connect()
    const db = client.db('mydb')
    const collection = db.collection('test')
    await collection.find({
      param: req.body.key
    })
    res.send('OK')
  })

  function searchLdap (filter, req, res) {
    const sendError = (err) => res.status(500).send(`Error: ${err}`)

    ldap.connect()
      .catch(sendError)
      .then(client =>
        client.search('ou=people', filter, (err, searchRes) => {
          if (err) return sendError(err)

          const entries = new Set()
          searchRes.on('searchEntry', entry => entries.add(entry.json))
          searchRes.on('end', () => res.json([...entries]))
          searchRes.on('error', sendError)
        })
      )
  }

  app.post('/iast/ldapi/test_insecure', (req, res) => {
    const { username, password } = req.body
    const filter = '(&(uid=' + username + ')(password=' + password + '))'
    searchLdap(filter, req, res)
  })

  app.post('/iast/ldapi/test_secure', (req, res) => {
    const filter = '(&(uid=ssam)(password=sammy))'
    searchLdap(filter, req, res)
  })

  app.get('/iast/hardcoded_secrets/test_insecure', (req, res) => {
    const secret = 'A3TMAWZUKIWR6O0OGR7B'
    const datadogSecret = 'p5opobitzpi9g5e3z6w7hsanjbd0zrekz5684m7m'
    res.send(`OK:${secret}:${datadogSecret}`)
  })

  app.get('/iast/hardcoded_secrets/test_secure', (req, res) => {
    const secret = 'unknown_secret'
    res.send(`OK:${secret}`)
  })

  app.post('/iast/header_injection/test_insecure', (req, res) => {
    res.setHeader('testheader', req.body.test)
    res.send('OK')
  })

  app.post('/iast/header_injection/test_secure', (req, res) => {
    res.setHeader('testheader', 'not_tainted_string')
    res.send('OK')
  })

  app.get('/iast/weak_randomness/test_insecure', (req, res) => {
    const randomNumber = Math.random()
    res.send(`OK:${randomNumber}`)
  })

  app.get('/iast/weak_randomness/test_secure', (req, res) => {
    const randomBytes = crypto.randomBytes(256).toString('hex')
    res.send(`OK:${randomBytes}`)
  })

  require('./sources')(app, tracer)
}

module.exports = { initRoutes, initData, initMiddlewares }
