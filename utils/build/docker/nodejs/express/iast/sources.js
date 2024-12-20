'use strict'

const { Kafka } = require('kafkajs')
const { readFileSync } = require('fs')
const { Client } = require('pg')

function init (app, tracer) {
  app.post('/iast/source/body/test', (req, res) => {
    try {
      readFileSync(req.body.name)
    } catch {
      // do nothing
    }
    res.send('OK')
  })

  app.get('/iast/source/headername/test', (req, res) => {
    let vulnParam = ''
    Object.keys(req.headers).forEach((key) => {
      vulnParam += key
    })
    try {
      readFileSync(vulnParam)
    } catch {
      // do nothing
    }
    res.send('OK')
  })

  app.get('/iast/source/header/test', (req, res) => {
    let vulnParam = ''
    Object.keys(req.headers).forEach((key) => {
      vulnParam += req.headers[key]
    })
    try {
      readFileSync(vulnParam)
    } catch {
      // do nothing
    }
    res.send('OK')
  })

  app.get('/iast/source/parametername/test', (req, res) => {
    let vulnParam = ''
    Object.keys(req.query).forEach((key) => {
      vulnParam += key
    })
    try {
      readFileSync(vulnParam)
    } catch {
      // do nothing
    }
    res.send('OK')
  })

  app.post('/iast/source/parameter/test', (req, res) => {
    let vulnParam = ''
    Object.keys(req.body).forEach((key) => {
      vulnParam += req.body[key]
    })
    try {
      readFileSync(vulnParam)
    } catch {
      // do nothing
    }
    res.send('OK')
  })

  app.get('/iast/source/parameter/test', (req, res) => {
    let vulnParam = ''
    Object.keys(req.query).forEach((key) => {
      vulnParam += req.query[key]
    })
    try {
      readFileSync(vulnParam)
    } catch {
      // do nothing
    }
    res.send('OK')
  })

  app.get('/iast/source/path_parameter/test/:table', (req, res) => {
    try {
      readFileSync(req.params.table)
    } catch {
      // do nothing
    }
    res.send('OK')
  })

  app.get('/iast/source/cookiename/test', (req, res) => {
    let vulnParam = ''
    Object.keys(req.cookies).forEach((key) => {
      vulnParam += key
    })
    try {
      readFileSync(vulnParam)
    } catch {
      // do nothing
    }
    res.send('OK')
  })

  app.get('/iast/source/cookievalue/test', (req, res) => {
    let vulnParam = ''
    Object.keys(req.cookies).forEach((key) => {
      vulnParam += req.cookies[key]
    })
    try {
      readFileSync(vulnParam)
    } catch {
      // do nothing
    }
    res.send('OK')
  })

  app.get('/iast/source/sql/test', async (req, res) => {
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

  async function getKafkaConsumer (kafka, topic, groupId) {
    const consumer = kafka.consumer({
      groupId,
      heartbeatInterval: 10000, // should be lower than sessionTimeout
      sessionTimeout: 60000
    })

    await consumer.connect()
    await consumer.subscribe({ topic, fromBeginning: true })

    return consumer
  }

  app.get('/iast/source/kafkavalue/test', (req, res) => {
    const kafka = getKafka()
    const topic = 'dsm-system-tests-queue'
    const timeout = 60000

    let consumer
    const doKafkaOperations = async () => {
      const deferred = {}
      const promise = new Promise((resolve, reject) => {
        deferred.resolve = resolve
        deferred.reject = reject
      })

      consumer = await getKafkaConsumer(kafka, topic, 'testgroup-iast-value')
      await consumer.run({
        eachMessage: async ({ topic, partition, message }) => {
          if (!message.value) return

          const vulnValue = message.value.toString()
          if (vulnValue === 'hello value!') {
            try {
              readFileSync(vulnValue)
            } catch {
              // do nothing
            }

            deferred.resolve()
          }
        }
      })

      setTimeout(() => {
        deferred.reject(new Error('Message not received'))
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

  app.get('/iast/source/kafkakey/test', (req, res) => {
    const kafka = getKafka()
    const topic = 'dsm-system-tests-queue'
    const timeout = 60000

    let consumer
    const doKafkaOperations = async () => {
      const deferred = {}
      const promise = new Promise((resolve, reject) => {
        deferred.resolve = resolve
        deferred.reject = reject
      })

      consumer = await getKafkaConsumer(kafka, topic, 'testgroup-iast-key')
      await consumer.run({
        eachMessage: async ({ topic, partition, message }) => {
          if (!message.key) return

          const vulnKey = message.key.toString()
          if (vulnKey === 'hello key!') {
            try {
              readFileSync(vulnKey)
            } catch {
            // do nothing
            }

            deferred.resolve()
          }
        }
      })

      setTimeout(() => {
        deferred.reject(new Error('Message not received'))
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

module.exports = init
