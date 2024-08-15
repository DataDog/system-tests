'use strict'

const { Kafka } = require('kafkajs')
const { readFileSync } = require('fs')

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

  app.get('/iast/source/kafkavalue/test', (req, res) => {
    const kafka = getKafka()
    const topic = 'dsm-system-tests-queue'
    const timeout = 60000

    let consumer
    const doKafkaOperations = async () => {
      consumer = kafka.consumer({
        groupId: 'testgroup2',
        heartbeatInterval: 10000, // should be lower than sessionTimeout
        sessionTimeout: 60000
      })

      await consumer.connect()
      await consumer.subscribe({ topic, fromBeginning: false })

      const deferred = {}
      const promise = new Promise((resolve, reject) => {
        deferred.resolve = resolve
        deferred.reject = reject
      })

      await consumer.run({
        eachMessage: async ({ topic, partition, message }) => {
          const vulnValue = message.value.toString()
          try {
            readFileSync(vulnValue)
          } catch {
            // do nothing
          }

          // in some occasions we consume messages from dsm tests
          if (vulnValue === 'hello value!') {
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
      consumer = kafka.consumer({
        groupId: 'testgroup2',
        heartbeatInterval: 10000, // should be lower than sessionTimeout
        sessionTimeout: 60000
      })

      await consumer.connect()
      await consumer.subscribe({ topic, fromBeginning: false })

      const deferred = {}
      const promise = new Promise((resolve, reject) => {
        deferred.resolve = resolve
        deferred.reject = reject
      })

      await consumer.run({
        eachMessage: async ({ topic, partition, message }) => {
          // in some occasions we consume messages from dsm tests
          if (!message.key) return

          const vulnKey = message.key.toString()
          try {
            readFileSync(vulnKey)
          } catch {
            // do nothing
          }

          if (vulnKey === 'hello key!') {
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
