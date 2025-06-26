const { Worker } = require('worker_threads')

const { kinesisProduce, kinesisConsume } = require('./integrations/messaging/aws/kinesis')
const { snsPublish, snsConsume } = require('./integrations/messaging/aws/sns')
const { sqsProduce, sqsConsume } = require('./integrations/messaging/aws/sqs')
const { kafkaProduce, kafkaConsume } = require('./integrations/messaging/kafka/kafka')
const {
  kafkaProduce: kafkaProduceConfluent,
  kafkaConsume: kafkaConsumeConfluent
} = require('./integrations/messaging/kafka/confluent_kafka')
const { rabbitmqProduce, rabbitmqConsume } = require('./integrations/messaging/rabbitmq/rabbitmq')

function initRoutes (app, tracer) {
  const { DsmPathwayCodec } = require('dd-trace/packages/dd-trace/src/datastreams/pathway')

  app.get('/dsm', (req, res) => {
    const integration = req.query.integration
    const topic = req.query.topic
    const queue = req.query.queue
    const exchange = req.query.exchange
    const routingKey = req.query.routing_key
    const stream = req.query.stream
    let message = req.query.message
    const library = req.query.library
    const groupId = req.query.group

    if (integration === 'kafka') {
      if (library === 'kafkajs') {
        message = message ?? 'hello from kafkajs DSM JS'
        const timeout = req.query.timeout ? req.query.timeout * 10000 : 60000

        kafkaProduce(queue, message)
          .then(() => {
            kafkaConsume(queue, timeout, groupId)
              .then(() => {
                res.send('ok')
              })
              .catch((error) => {
                console.log(error)
                res.status(500).send('[KafkaJS] Internal Server Error during DSM Kafka consume')
              })
          })
          .catch((error) => {
            console.log(error)
            res.status(500).send('[KafkaJS] Internal Server Error during DSM Kafka produce')
          })
      } else if (library === '@confluentinc/kafka-javascript') {
        message = message ?? 'hello from ConfluentKafka DSM JS'
        const timeout = req.query.timeout ? req.query.timeout * 10000 : 60000

        kafkaProduceConfluent(queue, message)
          .then(() => {
            kafkaConsumeConfluent(queue, timeout, groupId)
              .then(() => {
                res.send('ok')
              })
          }).catch((error) => {
            console.log(error)
            res.status(500).send('[ConfluentKafka] Internal Server Error during DSM ConfluentKafka produce')
          })
      }
    } else if (integration === 'sqs') {
      message = message ?? 'hello from SQS DSM JS'
      const timeout = req.query.timeout ?? 5

      sqsProduce(queue, message)
        .then(() => {
          sqsConsume(queue, timeout * 1000, message)
            .then(() => {
              res.send('ok')
            })
            .catch((error) => {
              console.log(error)
              res.status(500).send('[SQS] Internal Server Error during DSM SQS consume')
            })
        })
        .catch((error) => {
          console.log(error)
          res.status(500).send('[SQS] Internal Server Error during DSM SQS produce')
        })
    } else if (integration === 'sns') {
      message = message ?? 'hello from SNS DSM JS'
      const timeout = req.query.timeout ?? 5

      snsPublish(queue, topic, message)
        .then(() => {
          snsConsume(queue, timeout * 1000, message)
            .then(() => {
              res.send('ok')
            })
            .catch((error) => {
              console.log(error)
              res.status(500).send('[SNS->SQS] Internal Server Error during DSM SQS consume from SNS')
            })
        })
        .catch((error) => {
          console.log(error)
          res.status(500).send('[SNS->SQS] Internal Server Error during DSM SNS publish')
        })
    } else if (integration === 'rabbitmq') {
      message = message ?? 'hello from SQS DSM JS'
      const timeout = req.query.timeout ?? 5

      rabbitmqProduce(queue, exchange, routingKey, message)
        .then(() => {
          rabbitmqConsume(queue, timeout * 1000)
            .then(() => {
              res.status(200).send('ok')
            })
            .catch((error) => {
              console.error(error)
              res.status(500).send('[RabbitMQ] Internal Server Error during RabbitMQ DSM consume')
            })
        })
        .catch((error) => {
          console.error(error)
          res.status(500).send('[RabbitMQ] Internal Server Error during RabbitMQ DSM produce')
        })
    } else if (integration === 'kinesis') {
      message = message ?? JSON.stringify({ message: 'hello from Kinesis DSM JS' })
      const timeout = req.query.timeout ?? 60

      kinesisProduce(stream, message, '1', timeout)
        .then((value) => {
          kinesisConsume(stream, timeout * 1000, message, value.SequenceNumber)
            .then(() => {
              res.status(200).send('ok')
            })
            .catch((error) => {
              console.error(error)
              res.status(500).send('[Kinesis] Internal Server Error during Kinesis DSM consume')
            })
        })
        .catch((error) => {
          console.error(error)
          res.status(500).send('[Kinesis] Internal Server Error during Kinesis DSM produce')
        })
    } else {
      res.status(400).send(
        '[DSM] Wrong or missing integration, available integrations are [Kafka, RabbitMQ, SNS, SQS, Kinesis]'
      )
    }
  })

  app.get('/dsm/inject', (req, res) => {
    const topic = req.query.topic
    const integration = req.query.integration
    const headers = {}

    const dataStreamsContext = tracer._tracer.setCheckpoint(
      ['direction:out', `topic:${topic}`, `type:${integration}`], null, null
    )
    DsmPathwayCodec.encode(dataStreamsContext, headers)

    res.status(200).send(JSON.stringify(headers))
  })

  app.get('/dsm/extract', (req, res) => {
    const topic = req.query.topic
    const integration = req.query.integration
    const ctx = req.query.ctx

    tracer._tracer.decodeDataStreamsContext(JSON.parse(ctx))
    tracer._tracer.setCheckpoint(
      ['direction:in', `topic:${topic}`, `type:${integration}`], null, null
    )

    res.status(200).send('ok')
  })

  app.get('/dsm/manual/produce', (req, res) => {
    const type = req.query.type
    const target = req.query.target
    const headers = {}

    tracer.dataStreamsCheckpointer.setProduceCheckpoint(
      type, target, headers
    )

    res.set(headers)
    res.status(200).send('ok')
  })

  app.get('/dsm/manual/produce_with_thread', (req, res) => {
    const type = req.query.type
    const target = req.query.target
    const headers = {}
    let responseSent = false // Flag to ensure only one response is sent

    // Create a new worker thread to handle the setProduceCheckpoint function
    const worker = new Worker(`
        const { parentPort, workerData } = require('worker_threads');
        const tracer = require('dd-trace').init({
          debug: true,
          flushInterval: 5000
        });

        const { type, target, headers } = workerData;
        tracer.dataStreamsCheckpointer.setProduceCheckpoint(type, target, headers);

        parentPort.postMessage(headers);
    `, {
      eval: true,
      workerData: { type, target, headers }
    })

    worker.on('message', (resultHeaders) => {
      if (!responseSent) {
        responseSent = true
        res.set(resultHeaders)
        res.status(200).send('ok')
      }
    })

    worker.on('error', (error) => {
      if (!responseSent) {
        responseSent = true
        res.status(500).send(`Worker error: ${error.message}`)
      }
    })

    worker.on('exit', (code) => {
      if (code !== 0 && !responseSent) {
        responseSent = true
        res.status(500).send(`Worker stopped with exit code ${code}`)
      }
    })
  })

  app.get('/dsm/manual/consume', (req, res) => {
    const type = req.query.type
    const target = req.query.source
    const headers = JSON.parse(req.headers._datadog)

    tracer.dataStreamsCheckpointer.setConsumeCheckpoint(
      type, target, headers
    )

    res.status(200).send('ok')
  })

  app.get('/dsm/manual/consume_with_thread', (req, res) => {
    const type = req.query.type
    const source = req.query.source
    const headers = JSON.parse(req.headers._datadog)
    let responseSent = false // Flag to ensure only one response is sent

    // Create a new worker thread to handle the setProduceCheckpoint function
    const worker = new Worker(`
      const { parentPort, workerData } = require('worker_threads')
      const tracer = require('dd-trace').init({
        debug: true,
        flushInterval: 5000
      });

      const { type, source, headers } = workerData
      tracer.dataStreamsCheckpointer.setConsumeCheckpoint(type, source, headers)

      parentPort.postMessage("ok")
  `, {
      eval: true,
      workerData: { type, source, headers }
    })

    worker.on('message', () => {
      if (!responseSent) {
        responseSent = true
        res.status(200).send('ok')
      }
    })

    worker.on('error', (error) => {
      if (!responseSent) {
        responseSent = true
        res.status(500).send(`Worker error: ${error.message}`)
      }
    })

    worker.on('exit', (code) => {
      if (code !== 0 && !responseSent) {
        responseSent = true
        res.status(500).send(`Worker stopped with exit code ${code}`)
      }
    })
  })
}

module.exports = { initRoutes }
