'use strict'

import type { Express, NextFunction, Request, Response } from 'express'
import type { Stats } from 'fs'
import type { Client as LdapClient, SearchCallbackResponse } from 'ldapjs'
import type { Collection, Db, Document } from 'mongodb'

const { execSync } = require('child_process')
const crypto = require('crypto')
const { readFileSync, statSync } = require('fs')
const https = require('https')
const { MongoClient } = require('mongodb')
const mongoSanitize = require('express-mongo-sanitize')
const { join } = require('path')
const { Client } = require('pg')
const { Kafka } = require('kafkajs')
const pug = require('pug')
const { unserialize } = require('node-serialize')

const ldap = require('./integrations/ldap')
const initSecurityControls = require('./security-controls')

async function initData () {
  const query = readFileSync(join(__dirname, '..', 'resources', 'iast-data.sql')).toString()
  const client = new Client()
  await client.connect()
  await client.query(query)
}

function initMiddlewares (app: Express): void {
  const hstsMissingInsecurePattern: RegExp = /.*hstsmissing\/test_insecure$/gmi
  const xcontenttypeMissingInsecurePattern: RegExp = /.*xcontent-missing-header\/test_insecure$/gmi
  app.use((req: Request, res: Response, next: NextFunction): void => {
    if (!req.url.match(hstsMissingInsecurePattern)) {
      res.setHeader('Strict-Transport-Security', 'max-age=31536000')
    }
    if (!req.url.match(xcontenttypeMissingInsecurePattern)) {
      res.setHeader('X-Content-Type-Options', 'nosniff')
    }
    next()
  })
}

function initSinkRoutes (app: Express): void {
  app.get('/iast/insecure_hashing/deduplicate', (req: Request, res: Response): void => {
    const supportedAlgorithms: string[] = ['md5', 'sha1']

    let outputHashes: string = ''
    supportedAlgorithms.forEach((algorithm: string) => {
      const hash = crypto.createHash(algorithm).update('insecure').digest('hex')
      outputHashes += `--- ${algorithm}:${hash} ---`
    })

    res.send(outputHashes)
  })

  app.get('/iast/insecure_hashing/multiple_hash', (req: Request, res: Response): void => {
    const name: string = 'insecure'
    let outputHashes: string = crypto.createHash('md5').update(name).digest('hex')
    outputHashes += '--- ' + crypto.createHash('sha1').update(name).digest('hex')

    res.send(outputHashes)
  })

  app.get('/iast/insecure_hashing/test_secure_algorithm', (req: Request, res: Response): void => {
    res.send(crypto.createHash('sha256').update('secure').digest('hex'))
  })

  app.get('/iast/insecure_hashing/test_md5_algorithm', (req: Request, res: Response): void => {
    res.send(crypto.createHash('md5').update('insecure').digest('hex'))
  })

  app.get('/iast/insecure_cipher/test_insecure_algorithm', (req: Request, res: Response): void => {
    const cipher = crypto.createCipheriv('des-ede-cbc', '1111111111111111', 'abcdefgh')
    res.send(Buffer.concat([cipher.update('12345'), cipher.final()]))
  })

  app.get('/iast/insecure_cipher/test_secure_algorithm', (req: Request, res: Response): void => {
    const key = crypto.randomBytes(32)

    const iv = crypto.randomBytes(16)

    const cipher = crypto.createCipheriv('aes-256-cbc', Buffer.from(key), iv)
    res.send(Buffer.concat([cipher.update('12345'), cipher.final()]))
  })

  app.post('/iast/sqli/test_insecure', (req: Request, res: Response): void => {
    const sql: string = 'SELECT * FROM IAST_USER WHERE USERNAME = \'' +
        req.body.username + '\' AND PASSWORD = \'' + req.body.password + '\''
    const client = new Client()
    client.connect().then(() => {
      return client.query(sql).then((queryResult: any) => {
        res.json(queryResult)
      })
    }).catch((err: Error) => {
      res.status(500).json({ message: 'Error on request ' + err })
    })
  })

  app.post('/iast/sqli/test_secure', (req: Request, res: Response): void => {
    const sql: string = 'SELECT * FROM IAST_USER WHERE USERNAME = $1 AND PASSWORD = $2'
    const values: string[] = [req.body.username, req.body.password]
    const client = new Client()
    client.connect().then(() => {
      return client.query(sql, values).then((queryResult: any) => {
        res.json(queryResult)
      })
    }).catch((err: Error) => {
      res.status(500).json({ message: 'Error on request' + err })
    })
  })

  app.post('/iast/cmdi/test_insecure', (req: Request, res: Response): void => {
    const result: Buffer = execSync(req.body.cmd)
    res.send(result.toString())
  })

  app.post('/iast/path_traversal/test_insecure', (req: Request, res: Response): void => {
    const stats: Stats = statSync(req.body.path)
    res.send(JSON.stringify(stats))
  })

  app.post('/iast/ssrf/test_insecure', (req: Request, res: Response): void => {
    https.get(req.body.url, (clientResponse: any) => {
      clientResponse.on('data', function noop () {})
      clientResponse.on('end', () => {
        res.send('OK')
      })
    })
  })

  app.get('/iast/insecure-cookie/test_insecure', (req: Request, res: Response): void => {
    res.cookie('insecure', 'cookie', { httpOnly: true, sameSite: true })
    res.send('OK')
  })

  app.get('/iast/insecure-cookie/test_secure', (req: Request, res: Response): void => {
    res.setHeader('set-cookie', 'secure=cookie; Secure; HttpOnly; SameSite=Strict')
    res.cookie('secure2', 'value', { secure: true, httpOnly: true, sameSite: true })
    res.send('OK')
  })

  app.post('/iast/insecure-cookie/custom_cookie', (req: Request, res: Response): void => {
    res.cookie(req.body.cookieName, req.body.cookieValue, { httpOnly: true, sameSite: true })
    res.send('OK')
  })

  app.get('/iast/insecure-cookie/test_empty_cookie', (req: Request, res: Response): void => {
    res.clearCookie('insecure')
    res.setHeader('set-cookie', 'empty=')
    res.cookie('secure3', '')
    res.send('OK')
  })

  app.get('/iast/no-httponly-cookie/test_insecure', (req: Request, res: Response): void => {
    res.cookie('no-httponly', 'cookie', { secure: true, sameSite: true })
    res.send('OK')
  })

  app.get('/iast/no-httponly-cookie/test_secure', (req: Request, res: Response): void => {
    res.setHeader('set-cookie', 'httponly=cookie; Secure;HttpOnly;SameSite=Strict;')
    res.cookie('httponly2', 'value', { secure: true, httpOnly: true, sameSite: true })
    res.send('OK')
  })

  app.post('/iast/no-httponly-cookie/custom_cookie', (req: Request, res: Response): void => {
    res.cookie(req.body.cookieName, req.body.cookieValue, { secure: true, sameSite: true })
    res.send('OK')
  })

  app.get('/iast/no-httponly-cookie/test_empty_cookie', (req: Request, res: Response): void => {
    res.clearCookie('insecure')
    res.setHeader('set-cookie', 'httponlyempty=')
    res.cookie('httponlyempty2', '')
    res.send('OK')
  })

  app.get('/iast/no-samesite-cookie/test_insecure', (req: Request, res: Response): void => {
    res.cookie('nosamesite', 'cookie', { secure: true, httpOnly: true })
    res.send('OK')
  })

  app.get('/iast/no-samesite-cookie/test_secure', (req: Request, res: Response): void => {
    res.setHeader('set-cookie', 'samesite=cookie; Secure; HttpOnly; SameSite=Strict')
    res.cookie('samesite2', 'value', { secure: true, httpOnly: true, sameSite: true })
    res.send('OK')
  })

  app.post('/iast/no-samesite-cookie/custom_cookie', (req: Request, res: Response): void => {
    res.cookie(req.body.cookieName, req.body.cookieValue, { secure: true, httpOnly: true })
    res.send('OK')
  })

  app.get('/iast/no-samesite-cookie/test_empty_cookie', (req: Request, res: Response): void => {
    res.clearCookie('insecure')
    res.setHeader('set-cookie', 'samesiteempty=')
    res.cookie('samesiteempty2', '')
    res.send('OK')
  })

  app.post('/iast/unvalidated_redirect/test_secure_header', (req: Request, res: Response): void => {
    res.setHeader('location', 'http://dummy.location.com')
    res.send('OK')
  })

  app.post('/iast/unvalidated_redirect/test_insecure_header', (req: Request, res: Response): void => {
    res.setHeader('location', req.body.location)
    res.send('OK')
  })

  app.post('/iast/unvalidated_redirect/test_secure_redirect', (req: Request, res: Response): void => {
    res.redirect('http://dummy.location.com')
  })

  app.post('/iast/unvalidated_redirect/test_insecure_redirect', (req: Request, res: Response): void => {
    res.redirect(req.body.location)
  })

  app.get('/iast/hstsmissing/test_insecure', (req: Request, res: Response): void => {
    res.setHeader('Content-Type', 'text/html')
    res.end('<html><body><h1>Test</h1></html>')
  })

  app.get('/iast/hstsmissing/test_secure', (req: Request, res: Response): void => {
    res.setHeader('Strict-Transport-Security', 'max-age=31536000')
    res.setHeader('X-Content-Type-Options', 'nosniff')
    res.send('<html><body><h1>Test</h1></html>')
  })

  app.get('/iast/xcontent-missing-header/test_insecure', (req: Request, res: Response): void => {
    res.setHeader('Content-Type', 'text/html')
    res.end('<html><body><h1>Test</h1></html>')
  })

  app.get('/iast/xcontent-missing-header/test_secure', (req: Request, res: Response): void => {
    res.setHeader('Content-Type', 'text/html')
    res.send('<html><body><h1>Test</h1></html>')
  })



  app.get('/iast/sampling-by-route-method-count/:key', (req: Request, res: Response): void => {
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

    res.send('OK')
  })

  app.get('/iast/sampling-by-route-method-count-2/:key', (req: Request, res: Response): void => {
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

    res.send('OK')
  })

  app.post('/iast/sampling-by-route-method-count/:key', (req: Request, res: Response): void => {
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

    res.send('OK')
  })

  app.use('/iast/mongodb-nosql-injection/test_secure', mongoSanitize())
  app.post(
    '/iast/mongodb-nosql-injection/test_secure',
    async function (req: Request, res: Response): Promise<void> {
      const url: string = 'mongodb://mongodb:27017/'
      const client = new MongoClient(url)
      await client.connect()
      const db: Db = client.db('mydb')
      const collection: Collection<Document> = db.collection('test')
      await collection.find({
        param: req.body.key
      })
      res.send('OK')
  })

  // Same method, without sanitization middleware
  // DO NOT extract to one method, we should force different line numbers
  app.post(
    '/iast/mongodb-nosql-injection/test_insecure',
    async function (req: Request, res: Response): Promise<void> {
      const url: string = 'mongodb://mongodb:27017/'
      const client = new MongoClient(url)
      await client.connect()
      const db: Db = client.db('mydb')
      const collection: Collection<Document> = db.collection('test')
      await collection.find({
        param: req.body.key
      })
      res.send('OK')
  })

  function searchLdap (filter: any, req: Request, res: Response): void {
    const sendError = (err: Error) => res.status(500).send(`Error: ${err}`)

    ldap.connect()
      .catch(sendError)
      .then((client: LdapClient) =>
        client.search(
          'ou=people',
          filter,
          (err: Error | null, searchRes: SearchCallbackResponse): Response | void => {
            if (err) return sendError(err)

            const entries = new Set()
            searchRes.on('searchEntry', entry => entries.add(entry.json))
            searchRes.on('end', () => res.json([...entries]))
            searchRes.on('error', sendError)
          }
        )
      )
  }

  app.post('/iast/ldapi/test_insecure', (req: Request, res: Response): void => {
    const { username, password } = req.body
    const filter: string = '(&(uid=' + username + ')(password=' + password + '))'
    searchLdap(filter, req, res)
  })

  app.post('/iast/ldapi/test_secure', (req: Request, res: Response): void => {
    const filter: string = '(&(uid=ssam)(password=sammy))'
    searchLdap(filter, req, res)
  })

  app.get('/iast/hardcoded_secrets/test_insecure', (req: Request, res: Response): void => {
    const s3cret = 'A3TMAWZUKIWR6O0OGR7B'
    res.send(`OK:${s3cret}`)
  })

  app.get('/iast/hardcoded_secrets_extended/test_insecure', (req: Request, res: Response): void => {
    const datadogS3cret = 'p5opobitzpi9g5e3z6w7hsanjbd0zrekz5684m7m'
    res.send(`OK:${datadogS3cret}`)
  })

  app.get('/iast/hardcoded_passwords/test_insecure', (req: Request, res: Response): void => {
    const hashpwd = 'hpu0-ig=3o5slyr0rkqszidgxw-bc23tivq8e1-qvt.4191vlwm8ddk.ce64m4q0kga'
    res.send(`OK:${hashpwd}`)
  })

  app.get('/iast/hardcoded_passwords/test_secure', (req: Request, res: Response): void => {
    const token = 'unknown_secret'
    res.send(`OK:${token}`)
  })

  app.get('/iast/header_injection/reflected/exclusion', ({ headers, query }: Request, res: Response): void => {
    const reflectedHeaderName: string = `${query.reflected}`
    const originHeaderName: string = `${query.origin}`
    res.setHeader(reflectedHeaderName, `${headers[originHeaderName]}`)
    res.send('OK')
  })

  app.get('/iast/header_injection/reflected/no-exclusion', ({ query }: Request, res: Response): void => {
    // There is a reason for this: to avoid vulnerabilities deduplication,
    // which caused the non-exclusion test to fail for all tests after the first one,
    // since they are all in the same location (the hash is calculated based on the location).

    const reflectedHeaderName: string = `${query.reflected}`
    const originHeaderName: string = `${query.origin}`
    switch (reflectedHeaderName) {
      case 'pragma':
        res.setHeader(reflectedHeaderName, originHeaderName)
        break
      case 'transfer-encoding':
        res.setHeader(reflectedHeaderName, originHeaderName)
        break
      case 'content-encoding':
        res.setHeader(reflectedHeaderName, originHeaderName)
        break
      case 'access-control-allow-origin':
        res.setHeader(reflectedHeaderName, originHeaderName)
        break
      default:
        res.setHeader(reflectedHeaderName, originHeaderName)
        break
    }
    res.send('OK')
  })

  app.post('/iast/header_injection/test_insecure', (req: Request, res: Response): void => {
    res.setHeader('testheader', req.body.test)
    res.send('OK')
  })

  app.post('/iast/header_injection/test_secure', (req: Request, res: Response): void => {
    res.setHeader('testheader', 'not_tainted_string')
    res.send('OK')
  })

  app.get('/iast/weak_randomness/test_insecure', (req: Request, res: Response): void => {
    const randomNumber: number = Math.random()
    res.send(`OK:${randomNumber}`)
  })

  app.get('/iast/weak_randomness/test_secure', (req: Request, res: Response): void => {
    const randomBytes: string = crypto.randomBytes(256).toString('hex')
    res.send(`OK:${randomBytes}`)
  })

  app.post('/iast/code_injection/test_insecure', (req: Request, res: Response) => {
    // eslint-disable-next-line no-eval
    eval(req.body.code)
    res.send('OK')
  })

  app.post('/iast/code_injection/test_secure', (req: Request, res: Response) => {
    // eslint-disable-next-line no-eval
    eval('1+2')
    res.send('OK')
  })

  app.post('/iast/template_injection/test_insecure', (req: Request, res: Response) => {
    const fn = pug.compile(req.body.template)
    const html = fn()
    res.send(`OK:${html}`)
  })

  app.post('/iast/template_injection/test_secure', (req: Request, res: Response) => {
    const fn = pug.compile('p Hello!')
    const html = fn()
    res.send(`OK:${html}`)
  })

  app.get('/iast/untrusted_deserialization/test_insecure', (req: Request, res: Response) => {
    const name = unserialize(req.query.name)
    res.send(`OK:${name}`)
  })

  app.get('/iast/untrusted_deserialization/test_secure', (req: Request, res: Response) => {
    const name = unserialize(JSON.stringify({ name: 'example' }))
    res.send(`OK:${name}`)
  })
}

function initSourceRoutes (app: Express): void {
  app.post('/iast/source/body/test', (req: Request, res: Response): void => {
    try {
      readFileSync(req.body.name)
    } catch {
      // do nothing
    }
    res.send('OK')
  })

  app.get('/iast/source/headername/test', (req: Request, res: Response): void => {
    let vulnParam: string = ''
    Object.keys(req.headers).forEach((key: string): void => {
      vulnParam += key
    })
    try {
      readFileSync(vulnParam)
    } catch {
      // do nothing
    }
    res.send('OK')
  })

  app.get('/iast/source/header/test', (req: Request, res: Response): void => {
    let vulnParam: string = ''
    Object.keys(req.headers).forEach((key: string): void => {
      vulnParam += req.headers[key]
    })
    try {
      readFileSync(vulnParam)
    } catch {
      // do nothing
    }
    res.send('OK')
  })

  app.get('/iast/source/parametername/test', (req: Request, res: Response): void => {
    let vulnParam: string = ''
    Object.keys(req.query).forEach((key: string): void => {
      vulnParam += key
    })
    try {
      readFileSync(vulnParam)
    } catch {
      // do nothing
    }
    res.send('OK')
  })

  app.post('/iast/source/parameter/test', (req: Request, res: Response): void => {
    let vulnParam: string = ''
    Object.keys(req.body).forEach((key: string): void => {
      vulnParam += req.body[key]
    })
    try {
      readFileSync(vulnParam)
    } catch {
      // do nothing
    }
    res.send('OK')
  })

  app.get('/iast/source/parameter/test', (req: Request, res: Response): void => {
    let vulnParam: string = ''
    Object.keys(req.query).forEach((key: string): void => {
      vulnParam += req.query[key]
    })
    try {
      readFileSync(vulnParam)
    } catch {
      // do nothing
    }
    res.send('OK')
  })

  app.get('/iast/source/path_parameter/test/:table', (req: Request, res: Response): void => {
    try {
      readFileSync(req.params.table)
    } catch {
      // do nothing
    }
    res.send('OK')
  })

  app.get('/iast/source/cookiename/test', (req: Request, res: Response): void => {
    let vulnParam: string = ''
    Object.keys(req.cookies).forEach((key: string): void => {
      vulnParam += key
    })
    try {
      readFileSync(vulnParam)
    } catch {
      // do nothing
    }
    res.send('OK')
  })

  app.get('/iast/source/cookievalue/test', (req: Request, res: Response): void => {
    let vulnParam: string = ''
    Object.keys(req.cookies).forEach((key: string): void => {
      vulnParam += req.cookies[key]
    })
    try {
      readFileSync(vulnParam)
    } catch {
      // do nothing
    }
    res.send('OK')
  })

  app.get('/iast/source/sql/test', async (req: Request, res: Response) => {
    const client = new Client()

    try {
      await client.connect()

      const sql = 'SELECT * FROM IAST_USER'
      const queryResult = await client.query(`${sql} WHERE USERNAME = 'shaquille_oatmeal'`)

      const username = queryResult.rows[0].username

      await client.query(`${sql} WHERE USERNAME = '${username}'`)

      res.send('OK')
    } catch (err) {
      console.error('error', err)

      res.status(500).json({ message: 'Error on request ' + err })
    } finally {
      client.end()
    }
  })

  function getKafka () {
    return new Kafka({
      clientId: 'my-app-iast',
      brokers: ['kafka:9092'],
      retry: {
        initialRetryTime: 100, // Time to wait in milliseconds before the first retry
        retries: 20 // Number of retries before giving up
      }
    })
  }


  async function getKafkaConsumer (kafka: any, topic: string, groupId: string) {
    const consumer = kafka.consumer({
      groupId,
      heartbeatInterval: 10000, // should be lower than sessionTimeout
      sessionTimeout: 60000
    })

    await consumer.connect()
    await consumer.subscribe({ topic, fromBeginning: true })

    return consumer
  }

  app.get('/iast/source/kafkavalue/test', (req: Request, res: Response): void => {
    const kafka = getKafka()
    const topic = 'dsm-system-tests-queue'
    const timeout = 60000

    let consumer: any
    const doKafkaOperations = async () => {
      const deferred: {
        resolve?: Function,
        reject?: Function
      } = {}

      const promise = new Promise((resolve: Function, reject: Function): void => {
        deferred.resolve = resolve
        deferred.reject = reject
      })

      consumer = await getKafkaConsumer(kafka, topic, 'testgroup-iast-ts-value')
      await consumer.run({
        eachMessage: async ({ message }: { message: any }) => {
          if (!message.value) return

          const vulnValue = message.value.toString()
          if (vulnValue === 'hello value!') {
            try {
              readFileSync(vulnValue)
            } catch {
              // do nothing
            }

            deferred.resolve?.()
          }
        }
      })

      setTimeout(() => {
        deferred.reject?.(new Error('Message not received'))
      }, timeout)

      const producer = kafka.producer()
      await producer.connect()
      await producer.send({
        topic,
        messages: [{ value: 'hello value!' }]
      })
      await producer.disconnect()

      return promise
    }

    doKafkaOperations()
      .then(async () => {
        await consumer.stop()
        await consumer.disconnect()

        res.send('ok')
      })
      .catch((error) => {
        console.error(error)
        res.status(500).send('Internal Server Error')
      })
  })

  app.get('/iast/source/kafkakey/test', (req: Request, res: Response): void => {
    const kafka = getKafka()
    const topic = 'dsm-system-tests-queue'
    const timeout = 60000

    let consumer: any
    const doKafkaOperations = async () => {
      const deferred: {
        resolve?: Function,
        reject?: Function
      } = {}

      const promise = new Promise((resolve: Function, reject: Function): void => {
        deferred.resolve = resolve
        deferred.reject = reject
      })

      consumer = await getKafkaConsumer(kafka, topic, 'testgroup-iast-ts-key')
      await consumer.run({
        eachMessage: async ({ message }: { message: any }) => {
          if (!message.key) return

          const vulnKey = message.key.toString()
          if (vulnKey === 'hello key!') {
            try {
              readFileSync(vulnKey)
            } catch {
              // do nothing
            }

            deferred.resolve?.()
          }
        }
      })

      setTimeout(() => {
        deferred.reject?.(new Error('Message not received'))
      }, timeout)

      const producer = kafka.producer()
      await producer.connect()
      await producer.send({
        topic,
        messages: [{ key: 'hello key!', value: 'value' }]
      })
      await producer.disconnect()

      return promise
    }

    doKafkaOperations()
      .then(async () => {
        await consumer.stop()
        await consumer.disconnect()

        res.send('ok')
      })
      .catch((error) => {
        console.error(error)
        res.status(500).send('Internal Server Error')
      })
  })
}

function initRoutes (app: Express): void {
  initSinkRoutes(app)
  initSourceRoutes(app)
  initSecurityControls(app)
}


module.exports = { initRoutes, initData, initMiddlewares }
