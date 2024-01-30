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
    readFileSync(req.body.name)
    res.send('OK')
  })

  app.get('/iast/source/headername/test', (req, res) => {
    let vulnParam = ''
    Object.keys(req.headers).forEach((key) => {
      vulnParam += key
    })
    readFileSync(vulnParam)
    res.send('OK')
  })

  app.get('/iast/source/header/test', (req, res) => {
    let vulnParam = ''
    Object.keys(req.headers).forEach((key) => {
      vulnParam += req.headers[key]
    })
    readFileSync(vulnParam)
    res.send('OK')
  })

  app.get('/iast/source/parametername/test', (req, res) => {
    let vulnParam = ''
    Object.keys(req.query).forEach((key) => {
      vulnParam += key
    })
    readFileSync(vulnParam)
    res.send('OK')
  })

  app.post('/iast/source/parameter/test', (req, res) => {
    let vulnParam = ''
    Object.keys(req.body).forEach((key) => {
      vulnParam += req.body[key]
    })
    readFileSync(vulnParam)
    res.send('OK')
  })

  app.get('/iast/source/parameter/test', (req, res) => {
    let vulnParam = ''
    Object.keys(req.query).forEach((key) => {
      vulnParam += req.query[key]
    })
    readFileSync(vulnParam)
    res.send('OK')
  })

  app.get('/iast/source/cookiename/test', (req, res) => {
    let vulnParam = ''
    Object.keys(req.cookies).forEach((key) => {
      vulnParam += key
    })
    readFileSync(vulnParam)
    res.send('OK')
  })

  app.get('/iast/source/cookievalue/test', (req, res) => {
    let vulnParam = ''
    Object.keys(req.cookies).forEach((key) => {
      vulnParam += req.cookies[key]
    })
    readFileSync(vulnParam)
    res.send('OK')
  })

  app.get('/iast/source/kafkavalue/test', (req, res) => {
    const kafka = getKafka()

    const producer = kafka.producer()
    const doKafkaOperations = async () => {
      await producer.connect()
      await producer.send({
        topic: 'iast-system-tests-queue',
        messages: [
          { value: 'hello value!' }
        ]
      })
      await producer.disconnect()

      const consumer = kafka.consumer({ groupId: 'testgroup2' })

      await consumer.connect()
      await consumer.subscribe({ topic: 'iast-system-tests-queue', fromBeginning: true })

      await consumer.run({
        eachMessage: async ({ topic, partition, message }) => {
          const vulnValue = message.value.toString()
          readFileSync(vulnValue)
          await consumer.stop()
          await consumer.disconnect()
        }
      })
    }
    doKafkaOperations()
      .then(() => {
        res.send('ok')
      })
      .catch((error) => {
        console.error(error)
        res.status(500).send('Internal Server Error')
      })
  })

  app.get('/iast/source/kafkakey/test', (req, res) => {
    const kafka = getKafka()

    const producer = kafka.producer()
    const doKafkaOperations = async () => {
      await producer.connect()
      await producer.send({
        topic: 'iast-system-tests-queue',
        messages: [
          { key: 'hello key!', value: 'value' }
        ]
      })
      await producer.disconnect()

      const consumer = kafka.consumer({ groupId: 'testgroup2' })

      await consumer.connect()
      await consumer.subscribe({ topic: 'iast-system-tests-queue', fromBeginning: true })

      await consumer.run({
        eachMessage: async ({ topic, partition, message }) => {
          const vulnKey = message.key.toString()
          readFileSync(vulnKey)
          await consumer.stop()
          await consumer.disconnect()
        }
      })
    }
    doKafkaOperations()
      .then(() => {
        res.send('ok')
      })
      .catch((error) => {
        console.error(error)
        res.status(500).send('Internal Server Error')
      })
  })
}

module.exports = init
