'use strict'

const { Client } = require('pg')
const { readFileSync, statSync } = require('fs')
const { join } = require('path')
const crypto = require('crypto')
const { execSync } = require('child_process')
const https = require('https')
const { MongoClient } = require('mongodb')
const pug = require('pug')
const { unserialize } = require('node-serialize')

const ldap = require('../integrations/ldap')

async function initData () {
  const query = readFileSync(join(__dirname, '..', 'resources', 'iast-data.sql')).toString()
  const client = new Client()
  await client.connect()
  await client.query(query)
}

function initPlugins (app) {
  const hstsMissingInsecurePattern = /.*hstsmissing\/test_insecure$/gmi
  const xcontenttypeMissingInsecurePattern = /.*xcontent-missing-header\/test_insecure$/gmi

  app.addHook('onRequest', async (request, reply) => {
    if (!request.url.match(hstsMissingInsecurePattern)) {
      reply.header('Strict-Transport-Security', 'max-age=31536000')
    }

    if (!request.url.match(xcontenttypeMissingInsecurePattern)) {
      reply.header('X-Content-Type-Options', 'nosniff')
    }
  })
}

function initRoutes (app, tracer) {
  app.get('/iast/insecure_hashing/deduplicate', (request, reply) => {
    const supportedAlgorithms = ['md5', 'sha1']

    let outputHashes = ''
    supportedAlgorithms.forEach(algorithm => {
      const hash = crypto.createHash(algorithm).update('insecure').digest('hex')
      outputHashes += `--- ${algorithm}:${hash} ---`
    })

    reply.send(outputHashes)
  })

  app.get('/iast/insecure_hashing/multiple_hash', (request, reply) => {
    const name = 'insecure'
    let outputHashes = crypto.createHash('md5').update(name).digest('hex')
    outputHashes += '--- ' + crypto.createHash('sha1').update(name).digest('hex')

    reply.send(outputHashes)
  })

  app.get('/iast/insecure_hashing/test_secure_algorithm', (request, reply) => {
    reply.send(crypto.createHash('sha256').update('secure').digest('hex'))
  })

  app.get('/iast/insecure_hashing/test_md5_algorithm', (request, reply) => {
    reply.send(crypto.createHash('md5').update('insecure').digest('hex'))
  })

  app.get('/iast/insecure_cipher/test_insecure_algorithm', (request, reply) => {
    const cipher = crypto.createCipheriv('des-ede-cbc', '1111111111111111', 'abcdefgh')
    reply.send(Buffer.concat([cipher.update('12345'), cipher.final()]))
  })

  app.get('/iast/insecure_cipher/test_secure_algorithm', (request, reply) => {
    const key = crypto.randomBytes(32)

    const iv = crypto.randomBytes(16)

    const cipher = crypto.createCipheriv('aes-256-cbc', Buffer.from(key), iv)
    reply.send(Buffer.concat([cipher.update('12345'), cipher.final()]))
  })

  app.post('/iast/sqli/test_insecure', (request, reply) => {
    const sql = 'SELECT * FROM IAST_USER WHERE USERNAME = \'' +
      request.body.username + '\' AND PASSWORD = \'' + request.body.password + '\''
    const client = new Client()
    client.connect().then(() => {
      return client.query(sql).then((queryResult) => {
        reply.send(queryResult)
      })
    }).catch((err) => {
      reply.code(500).send({ message: 'Error on request ' + err })
    })
  })

  app.post('/iast/sqli/test_secure', (request, reply) => {
    const sql = 'SELECT * FROM IAST_USER WHERE USERNAME = $1 AND PASSWORD = $2'
    const values = [request.body.username, request.body.password]
    const client = new Client()
    client.connect().then(() => {
      return client.query(sql, values).then((queryResult) => {
        reply.send(queryResult)
      })
    }).catch((err) => {
      reply.code(500).send({ message: 'Error on request' + err })
    })
  })

  app.post('/iast/cmdi/test_insecure', (request, reply) => {
    const result = execSync(request.body.cmd)
    reply.send(result.toString())
  })

  app.post('/iast/path_traversal/test_insecure', (request, reply) => {
    const stats = statSync(request.body.path)
    reply.send(JSON.stringify(stats))
  })

  app.post('/iast/ssrf/test_insecure', (request, reply) => {
    https.get(request.body.url, (clientResponse) => {
      clientResponse.on('data', function noop () {})
      clientResponse.on('end', () => {
        reply.send('OK')
      })
    })
  })

  app.get('/iast/insecure-cookie/test_insecure', (request, reply) => {
    reply.cookie('insecure', 'cookie', { httpOnly: true, sameSite: true })
    reply.send('OK')
  })

  app.get('/iast/insecure-cookie/test_secure', (request, reply) => {
    reply.header('set-cookie', 'secure=cookie; Secure; HttpOnly; SameSite=Strict')
    reply.cookie('secure2', 'value', { secure: true, httpOnly: true, sameSite: true })
    reply.send('OK')
  })

  app.post('/iast/insecure-cookie/custom_cookie', (request, reply) => {
    reply.cookie(request.body.cookieName, request.body.cookieValue, { httpOnly: true, sameSite: true })
    reply.send('OK')
  })

  app.get('/iast/insecure-cookie/test_empty_cookie', (request, reply) => {
    reply.clearCookie('insecure')
    reply.header('set-cookie', 'empty=')
    reply.cookie('secure3', '')
    reply.send('OK')
  })

  app.get('/iast/no-httponly-cookie/test_insecure', (request, reply) => {
    reply.cookie('no-httponly', 'cookie', { secure: true, sameSite: true })
    reply.send('OK')
  })

  app.get('/iast/no-httponly-cookie/test_secure', (request, reply) => {
    reply.header('set-cookie', 'httponly=cookie; Secure;HttpOnly;SameSite=Strict;')
    reply.cookie('httponly2', 'value', { secure: true, httpOnly: true, sameSite: true })
    reply.send('OK')
  })

  app.post('/iast/no-httponly-cookie/custom_cookie', (request, reply) => {
    reply.cookie(request.body.cookieName, request.body.cookieValue, { secure: true, sameSite: true })
    reply.send('OK')
  })

  app.get('/iast/no-httponly-cookie/test_empty_cookie', (request, reply) => {
    reply.clearCookie('insecure')
    reply.header('set-cookie', 'httponlyempty=')
    reply.cookie('httponlyempty2', '')
    reply.send('OK')
  })

  app.get('/iast/no-samesite-cookie/test_insecure', (request, reply) => {
    reply.cookie('nosamesite', 'cookie', { secure: true, httpOnly: true })
    reply.send('OK')
  })

  app.get('/iast/no-samesite-cookie/test_secure', (request, reply) => {
    reply.header('set-cookie', 'samesite=cookie; Secure; HttpOnly; SameSite=Strict')
    reply.cookie('samesite2', 'value', { secure: true, httpOnly: true, sameSite: true })
    reply.send('OK')
  })

  app.post('/iast/no-samesite-cookie/custom_cookie', (request, reply) => {
    reply.cookie(request.body.cookieName, request.body.cookieValue, { secure: true, httpOnly: true })
    reply.send('OK')
  })

  app.get('/iast/no-samesite-cookie/test_empty_cookie', (request, reply) => {
    reply.clearCookie('insecure')
    reply.header('set-cookie', 'samesiteempty=')
    reply.cookie('samesiteempty2', '')
    reply.send('OK')
  })

  app.post('/iast/unvalidated_redirect/test_secure_header', (request, reply) => {
    reply.header('location', 'http://dummy.location.com')
    reply.send('OK')
  })

  app.post('/iast/unvalidated_redirect/test_insecure_header', (request, reply) => {
    reply.header('location', request.body.location)
    reply.send('OK')
  })

  app.post('/iast/unvalidated_redirect/test_secure_redirect', (request, reply) => {
    reply.redirect('http://dummy.location.com')
  })

  app.post('/iast/unvalidated_redirect/test_insecure_redirect', (request, reply) => {
    reply.redirect(request.body.location)
  })

  app.get('/iast/hstsmissing/test_insecure', (request, reply) => {
    reply.header('Content-Type', 'text/html')
    reply.send('<html><body><h1>Test</h1></html>')
  })

  app.get('/iast/hstsmissing/test_secure', (request, reply) => {
    reply.header('Strict-Transport-Security', 'max-age=31536000')
    reply.header('X-Content-Type-Options', 'nosniff')
    reply.send('<html><body><h1>Test</h1></html>')
  })

  app.get('/iast/xcontent-missing-header/test_insecure', (request, reply) => {
    reply.header('Content-Type', 'text/html')
    reply.send('<html><body><h1>Test</h1></html>')
  })

  app.get('/iast/xcontent-missing-header/test_secure', (request, reply) => {
    reply.header('Content-Type', 'text/html')
    reply.send('<html><body><h1>Test</h1></html>')
  })

  app.get('/iast/sampling-by-route-method-count/:key', (request, reply) => {
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')

    reply.send('OK')
  })

  app.get('/iast/sampling-by-route-method-count-2/:key', (request, reply) => {
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')

    reply.send('OK')
  })

  app.post('/iast/sampling-by-route-method-count/:key', (request, reply) => {
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')
    crypto.createHash('md5').update('insecure').digest('hex')

    reply.send('OK')
  })

  // if (mongoSanitizeEnabled) {
  //   const mongoSanitize = require('express-mongo-sanitize')
  //   app.register(async function (fastify) {
  //     fastify.addHook('preHandler', async (request, reply) => {
  //       if (request.url.includes('/iast/mongodb-nosql-injection/test_secure')) {
  //         // not sure if this is needed, but it's the same as in express
  //         mongoSanitize()(request, reply, () => {})
  //       }
  //     })
  //   })
  // }

  app.post('/iast/mongodb-nosql-injection/test_secure', async function (request, reply) {
    const url = 'mongodb://mongodb:27017/'
    const client = new MongoClient(url)
    await client.connect()
    const db = client.db('mydb')
    const collection = db.collection('test')
    await collection.find({
      param: request.body.key
    })
    reply.send('OK')
  })

  // Same method, without sanitization middleware
  // DO NOT extract to one method, we should force different line numbers
  app.post('/iast/mongodb-nosql-injection/test_insecure', async function (request, reply) {
    const url = 'mongodb://mongodb:27017/'
    const client = new MongoClient(url)
    await client.connect()
    const db = client.db('mydb')
    const collection = db.collection('test')
    await collection.find({
      param: request.body.key
    })
    reply.send('OK')
  })

  function searchLdap (filter, request, reply) {
    const sendError = (err) => reply.code(500).send(`Error: ${err}`)

    ldap.connect()
      .catch(sendError)
      .then(client =>
        client.search('ou=people', filter, (err, searchRes) => {
          if (err) return sendError(err)

          const entries = new Set()
          searchRes.on('searchEntry', entry => entries.add(entry.json))
          searchRes.on('end', () => reply.send([...entries]))
          searchRes.on('error', sendError)
        })
      )
  }

  app.post('/iast/ldapi/test_insecure', (request, reply) => {
    const { username, password } = request.body
    const filter = '(&(uid=' + username + ')(password=' + password + '))'
    searchLdap(filter, request, reply)
  })

  app.post('/iast/ldapi/test_secure', (request, reply) => {
    const filter = '(&(uid=ssam)(password=sammy))'
    searchLdap(filter, request, reply)
  })

  app.get('/iast/hardcoded_secrets/test_insecure', (request, reply) => {
    const s3cret = 'A3TMAWZUKIWR6O0OGR7B'
    reply.send(`OK:${s3cret}`)
  })

  app.get('/iast/hardcoded_secrets_extended/test_insecure', (request, reply) => {
    const datadogS3cret = 'p5opobitzpi9g5e3z6w7hsanjbd0zrekz5684m7m'
    reply.send(`OK:${datadogS3cret}`)
  })

  app.get('/iast/hardcoded_passwords/test_insecure', (request, reply) => {
    const hashpwd = 'hpu0-ig=3o5slyr0rkqszidgxw-bc23tivq8e1-qvt.4191vlwm8ddk.ce64m4q0kga'
    reply.send(`OK:${hashpwd}`)
  })

  app.get('/iast/hardcoded_passwords/test_secure', (request, reply) => {
    const token = 'unknown_secret'
    reply.send(`OK:${token}`)
  })

  app.get('/iast/header_injection/reflected/exclusion', (request, reply) => {
    reply.header(request.query.reflected, request.headers[request.query.origin])
    reply.send('OK')
  })

  app.get('/iast/header_injection/reflected/no-exclusion', (request, reply) => {
    // There is a reason for this: to avoid vulnerabilities deduplication,
    // which caused the non-exclusion test to fail for all tests after the first one,
    // since they are all in the same location (the hash is calculated based on the location).

    switch (request.query.reflected) {
      case 'pragma':
        reply.header(request.query.reflected, request.query.origin)
        break
      case 'transfer-encoding':
        reply.header(request.query.reflected, request.query.origin)
        break
      case 'content-encoding':
        reply.header(request.query.reflected, request.query.origin)
        break
      case 'access-control-allow-origin':
        reply.header(request.query.reflected, request.query.origin)
        break
      default:
        reply.header(request.query.reflected, request.query.origin)
        break
    }
    reply.send('OK')
  })

  app.post('/iast/header_injection/test_insecure', (request, reply) => {
    reply.header('testheader', request.body.test)
    reply.send('OK')
  })

  app.post('/iast/header_injection/test_secure', (request, reply) => {
    reply.header('testheader', 'not_tainted_string')
    reply.send('OK')
  })

  app.get('/iast/weak_randomness/test_insecure', (request, reply) => {
    const randomNumber = Math.random()
    reply.send(`OK:${randomNumber}`)
  })

  app.get('/iast/weak_randomness/test_secure', (request, reply) => {
    const randomBytes = crypto.randomBytes(256).toString('hex')
    reply.send(`OK:${randomBytes}`)
  })

  app.post('/iast/code_injection/test_insecure', (request, reply) => {
    // eslint-disable-next-line no-eval
    eval(request.body.code)
    reply.send('OK')
  })

  app.post('/iast/code_injection/test_secure', (request, reply) => {
    // eslint-disable-next-line no-eval
    eval('1+2')
    reply.send('OK')
  })

  app.post('/iast/template_injection/test_insecure', (request, reply) => {
    const fn = pug.compile(request.body.template)
    const html = fn()
    reply.send(`OK:${html}`)
  })

  app.post('/iast/template_injection/test_secure', (request, reply) => {
    const fn = pug.compile('p Hello!')
    const html = fn()
    reply.send(`OK:${html}`)
  })

  app.get('/iast/untrusted_deserialization/test_insecure', (request, reply) => {
    const name = unserialize(request.query.name)
    reply.send(`OK:${name}`)
  })

  app.get('/iast/untrusted_deserialization/test_secure', (request, reply) => {
    const name = unserialize(JSON.stringify({ name: 'example' }))
    reply.send(`OK:${name}`)
  })

  require('./sources')(app, tracer)

  require('./security-controls')(app, tracer)
}

module.exports = { initRoutes, initData, initPlugins }
