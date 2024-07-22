const { Worker, isMainThread, parentPort, workerData } = require('worker_threads')

const { kinesisProduce, kinesisConsume } = require('./integrations/messaging/aws/kinesis')
const { snsPublish, snsConsume } = require('./integrations/messaging/aws/sns')
const { sqsProduce, sqsConsume } = require('./integrations/messaging/aws/sqs')
const { kafkaProduce, kafkaConsume } = require('./integrations/messaging/kafka/kafka')
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

    if (integration === 'kafka') {
      const message = 'hello from kafka DSM JS'
      const timeout = req.query.timeout ? req.query.timeout * 10000 : 60000

      kafkaProduce(queue, message)
        .then(() => {
          kafkaConsume(queue, timeout)
            .then(() => {
              res.send('ok')
            })
            .catch((error) => {
              console.log(error)
              res.status(500).send('[Kafka] Internal Server Error during DSM Kafka consume')
            })
        })
        .catch((error) => {
          console.log(error)
          res.status(500).send('[Kafka] Internal Server Error during DSM Kafka produce')
        })
    } else if (integration === 'sqs') {
      const message = 'hello from SQS DSM JS'
      const timeout = req.query.timeout ?? 5

      sqsProduce(queue, message)
        .then(() => {
          sqsConsume(queue, timeout * 1000)
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
      const message = 'hello from SNS DSM JS'
      const timeout = req.query.timeout ?? 5

      snsPublish(queue, topic, message)
        .then(() => {
          snsConsume(queue, timeout * 1000)
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
      const message = 'hello from SQS DSM JS'
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
      const message = JSON.stringify({ message: 'hello from Kinesis DSM JS' })
      const timeout = req.query.timeout ?? 60

      kinesisProduce(stream, message, '1', timeout)
        .then(() => {
          kinesisConsume(stream, timeout * 1000)
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

    res.status(200).send(JSON.stringify(headers))
  })

  app.get('/dsm/manual/produce_with_thread', (req, res) => {
    const type = req.query.type
    const target = req.query.target
    const headers = {}

    // Create a new worker thread to handle the setProduceCheckpoint function
    const worker = new Worker(`
        const { parentPort, workerData } = require('worker_threads')

        const { type, target, headers, tracer } = workerData
        tracer.dataStreamsCheckpointer.setProduceCheckpoint(type, target, headers)

        parentPort.postMessage(headers)
    `, {
      eval: true,
      workerData: { type, target, headers, tracer }
    })

    worker.on('message', (resultHeaders) => {
      res.status(200).send(JSON.stringify(resultHeaders))
    })

    worker.on('error', (error) => {
      res.status(500).send(`Worker error: ${error.message}`)
    })

    worker.on('exit', (code) => {
      if (code !== 0) {
        res.status(500).send(`Worker stopped with exit code ${code}`)
      }
    })
  })

  app.get('/dsm/manual/consume', (req, res) => {
    const type = req.query.type
    const target = req.query.source
    const headers = JSON.parse(req.query.headers)

    tracer.dataStreamsCheckpointer.setConsumeCheckpoint(
      type, target, headers
    )

    res.status(200).send('ok')
  })

  app.get('/dsm/manual/consume_with_thread', (req, res) => {
    const type = req.query.type
    const source = req.query.source
    const headers = JSON.parse(req.query.headers)

    // Create a new worker thread to handle the setProduceCheckpoint function
    const worker = new Worker(`
      const { parentPort, workerData } = require('worker_threads')

      const { type, source, headers, tracer } = workerData
      tracer.dataStreamsCheckpointer.setConsumeCheckpoint(type, source, headers)

      parentPort.postMessage("ok")
  `, {
      eval: true,
      workerData: { type, source, headers, tracer }
    })

    worker.on('message', () => {
      res.status(200).send('ok')
    })

    worker.on('error', (error) => {
      res.status(500).send(`Worker error: ${error.message}`)
    })

    worker.on('exit', (code) => {
      if (code !== 0) {
        res.status(500).send(`Worker stopped with exit code ${code}`)
      }
    })
  })
}

module.exports = { initRoutes }
