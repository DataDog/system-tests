'use strict'

const { Kafka } = require('kafkajs')
const { Client } = require('pg')
const { execSync } = require('child_process')

function init (app) {
  app.post('/iast/source/body/test', (request, reply) => {
    try {
      const code = `echo ${request.body.name}`
      execSync(code)
    } catch {
      // do nothing
    }
    reply.send('OK')
  })

  app.get('/iast/source/headername/test', (request, reply) => {
    let vulnParam = ''
    Object.keys(request.headers).forEach((key) => {
      vulnParam += key
    })
    try {
      const code = `echo ${vulnParam}`
      execSync(code)
    } catch {
      // do nothing
    }
    reply.send('OK')
  })

  app.get('/iast/source/header/test', (request, reply) => {
    let vulnParam = ''
    Object.keys(request.headers).forEach((key) => {
      vulnParam += request.headers[key]
    })
    try {
      const code = `echo ${vulnParam}`
      execSync(code)
    } catch {
      // do nothing
    }
    reply.send('OK')
  })

  app.get('/iast/source/parametername/test', (request, reply) => {
    let vulnParam = ''
    Object.keys(request.query).forEach((key) => {
      vulnParam += key
    })
    try {
      const code = `echo ${vulnParam}`
      execSync(code)
    } catch {
      // do nothing
    }
    reply.send('OK')
  })

  app.post('/iast/source/parameter/test', (request, reply) => {
    let vulnParam = ''
    Object.keys(request.body).forEach((key) => {
      vulnParam += request.body[key]
    })
    try {
      const code = `echo ${vulnParam}`
      execSync(code)
    } catch {
      // do nothing
    }
    reply.send('OK')
  })

  app.get('/iast/source/parameter/test', (request, reply) => {
    let vulnParam = ''
    Object.keys(request.query).forEach((key) => {
      vulnParam += request.query[key]
    })
    try {
      const code = `echo ${vulnParam}`
      execSync(code)
    } catch {
      // do nothing
    }
    reply.send('OK')
  })

  app.get('/iast/source/path_parameter/test/:table', (request, reply) => {
    try {
      const code = `echo ${request.params.table}`
      execSync(code)
    } catch {
      // do nothing
    }
    reply.send('OK')
  })

  app.get('/iast/source/cookiename/test', (request, reply) => {
    let vulnParam = ''
    Object.keys(request.cookies).forEach((key) => {
      vulnParam += key
    })
    try {
      const code = `echo ${vulnParam}`
      execSync(code)
    } catch {
      // do nothing
    }
    reply.send('OK')
  })

  app.get('/iast/source/cookievalue/test', (request, reply) => {
    let vulnParam = ''
    Object.keys(request.cookies).forEach((key) => {
      vulnParam += request.cookies[key]
    })
    try {
      const code = `echo ${vulnParam}`
      execSync(code)
    } catch {
      // do nothing
    }
    reply.send('OK')
  })

  app.get('/iast/source/sql/test', async (request, reply) => {
    const client = new Client()

    try {
      await client.connect()

      const sql = 'SELECT * FROM IAST_USER'
      const queryResult = await client.query(`${sql} WHERE USERNAME = 'shaquille_oatmeal'`)

      const username = queryResult.rows[0].username

      await client.query(`${sql} WHERE USERNAME = '${username}'`)

      reply.send('OK')
    } catch (err) {
      console.error('error', err)

      reply.code(500).send({ message: 'Error on request ' + err })
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

  app.get('/iast/source/kafkavalue/test', (request, reply) => {
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
              const code = `echo ${vulnValue}`
              execSync(code)
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

        reply.send('ok')
      })
      .catch((error) => {
        console.error(error)
        reply.code(500).send('Internal Server Error')
      })
  })

  app.get('/iast/source/kafkakey/test', (request, reply) => {
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
              const code = `echo ${vulnKey}`
              execSync(code)
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

        reply.send('ok')
      })
      .catch((error) => {
        console.error(error)
        reply.code(500).send('Internal Server Error')
      })
  })
}

module.exports = init
