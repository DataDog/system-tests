const { Worker } = require('worker_threads')

const { kinesisProduce, kinesisConsume } = require('./integrations/messaging/aws/kinesis')
const { snsPublish, snsConsume } = require('./integrations/messaging/aws/sns')
const { sqsProduce, sqsConsume } = require('./integrations/messaging/aws/sqs')
const { kafkaProduce, kafkaConsume } = require('./integrations/messaging/kafka/kafka')
const { rabbitmqProduce, rabbitmqConsume } = require('./integrations/messaging/rabbitmq/rabbitmq')

function initRoutes (fastify, tracer) {
  const { DsmPathwayCodec } = require('dd-trace/packages/dd-trace/src/datastreams/pathway')

  fastify.get('/dsm', async (request, reply) => {
    const integration = request.query.integration
    const topic = request.query.topic
    const queue = request.query.queue
    const exchange = request.query.exchange
    const routingKey = request.query.routing_key
    const stream = request.query.stream
    let message = request.query.message

    if (integration === 'kafka') {
      message = message ?? 'hello from kafka DSM JS'
      const timeout = request.query.timeout ? request.query.timeout * 10000 : 60000

      try {
        await kafkaProduce(queue, message)
        await kafkaConsume(queue, timeout)
        return 'ok'
      } catch (error) {
        console.log(error)
        reply.status(500)
        return '[Kafka] Internal Server Error during DSM Kafka produce/consume'
      }
    } else if (integration === 'sqs') {
      message = message ?? 'hello from SQS DSM JS'
      const timeout = request.query.timeout ?? 5

      try {
        await sqsProduce(queue, message)
        await sqsConsume(queue, timeout * 1000, message)
        return 'ok'
      } catch (error) {
        console.log(error)
        reply.status(500)
        return '[SQS] Internal Server Error during DSM SQS produce/consume'
      }
    } else if (integration === 'sns') {
      message = message ?? 'hello from SNS DSM JS'
      const timeout = request.query.timeout ?? 5

      try {
        await snsPublish(queue, topic, message)
        await snsConsume(queue, timeout * 1000, message)
        return 'ok'
      } catch (error) {
        console.log(error)
        reply.status(500)
        return '[SNS->SQS] Internal Server Error during DSM SNS/SQS produce/consume'
      }
    } else if (integration === 'rabbitmq') {
      message = message ?? 'hello from SQS DSM JS'
      const timeout = request.query.timeout ?? 5

      try {
        await rabbitmqProduce(queue, exchange, routingKey, message)
        await rabbitmqConsume(queue, timeout * 1000)
        reply.status(200)
        return 'ok'
      } catch (error) {
        console.error(error)
        reply.status(500)
        return '[RabbitMQ] Internal Server Error during RabbitMQ DSM produce/consume'
      }
    } else if (integration === 'kinesis') {
      message = message ?? JSON.stringify({ message: 'hello from Kinesis DSM JS' })
      const timeout = request.query.timeout ?? 60

      try {
        const value = await kinesisProduce(stream, message, '1', timeout)
        await kinesisConsume(stream, timeout * 1000, message, value.SequenceNumber)
        reply.status(200)
        return 'ok'
      } catch (error) {
        console.error(error)
        reply.status(500)
        return '[Kinesis] Internal Server Error during Kinesis DSM produce/consume'
      }
    } else {
      reply.status(400)
      return '[DSM] Wrong or missing integration, available integrations are [Kafka, RabbitMQ, SNS, SQS, Kinesis]'
    }
  })

  fastify.get('/dsm/inject', async (request, reply) => {
    const topic = request.query.topic
    const integration = request.query.integration
    const headers = {}

    const dataStreamsContext = tracer._tracer.setCheckpoint(
      ['direction:out', `topic:${topic}`, `type:${integration}`], null, null
    )
    DsmPathwayCodec.encode(dataStreamsContext, headers)

    reply.status(200)
    return JSON.stringify(headers)
  })

  fastify.get('/dsm/extract', async (request, reply) => {
    const topic = request.query.topic
    const integration = request.query.integration
    const ctx = request.query.ctx

    tracer._tracer.decodeDataStreamsContext(JSON.parse(ctx))
    tracer._tracer.setCheckpoint(
      ['direction:in', `topic:${topic}`, `type:${integration}`], null, null
    )

    reply.status(200)
    return 'ok'
  })

  fastify.get('/dsm/manual/produce', async (request, reply) => {
    const type = request.query.type
    const target = request.query.target
    const headers = {}

    tracer.dataStreamsCheckpointer.setProduceCheckpoint(
      type, target, headers
    )

    reply.headers(headers)
    reply.status(200)
    return 'ok'
  })

  fastify.get('/dsm/manual/produce_with_thread', async (request, reply) => {
    const type = request.query.type
    const target = request.query.target
    const headers = {}
    let responseSent = false // Flag to ensure only one response is sent

    return new Promise((resolve, reject) => {
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
          reply.headers(resultHeaders)
          reply.status(200)
          resolve('ok')
        }
      })

      worker.on('error', (error) => {
        if (!responseSent) {
          responseSent = true
          reply.status(500)
          reject(new Error(`Worker error: ${error.message}`))
        }
      })

      worker.on('exit', (code) => {
        if (code !== 0 && !responseSent) {
          responseSent = true
          reply.status(500)
          reject(new Error(`Worker stopped with exit code ${code}`))
        }
      })
    })
  })

  fastify.get('/dsm/manual/consume', async (request, reply) => {
    const type = request.query.type
    const target = request.query.source
    const headers = JSON.parse(request.headers._datadog)

    tracer.dataStreamsCheckpointer.setConsumeCheckpoint(
      type, target, headers
    )

    reply.status(200)
    return 'ok'
  })

  fastify.get('/dsm/manual/consume_with_thread', async (request, reply) => {
    const type = request.query.type
    const source = request.query.source
    const headers = JSON.parse(request.headers._datadog)
    let responseSent = false // Flag to ensure only one response is sent

    return new Promise((resolve, reject) => {
      // Create a new worker thread to handle the setConsumeCheckpoint function
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
          reply.status(200)
          resolve('ok')
        }
      })

      worker.on('error', (error) => {
        if (!responseSent) {
          responseSent = true
          reply.status(500)
          reject(new Error(`Worker error: ${error.message}`))
        }
      })

      worker.on('exit', (code) => {
        if (code !== 0 && !responseSent) {
          responseSent = true
          reply.status(500)
          reject(new Error(`Worker stopped with exit code ${code}`))
        }
      })
    })
  })
}

module.exports = { initRoutes }
