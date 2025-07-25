'use strict'

const tracer = require('dd-trace').init({
  debug: true,
  flushInterval: 5000
})

const { promisify } = require('util')
const fastify = require('fastify')({ logger: true })
const axios = require('axios')
const crypto = require('crypto')
const http = require('http')
const winston = require('winston')

const iast = require('./iast')
const dsm = require('./dsm')
const di = require('./debugger')

const pgsql = require('./integrations/db/postgres')
const mysql = require('./integrations/db/mysql')
const mssql = require('./integrations/db/mssql')
const apiGateway = require('./integrations/api_gateway')
const { kinesisProduce, kinesisConsume } = require('./integrations/messaging/aws/kinesis')
const { snsPublish, snsConsume } = require('./integrations/messaging/aws/sns')
const { sqsProduce, sqsConsume } = require('./integrations/messaging/aws/sqs')
const { kafkaProduce, kafkaConsume } = require('./integrations/messaging/kafka/kafka')
const { rabbitmqProduce, rabbitmqConsume } = require('./integrations/messaging/rabbitmq/rabbitmq')

// Unstructured logging (plain text)
const plainLogger = console

// Structured logging (JSON)
const jsonLogger = winston.createLogger({
  level: 'info',
  format: winston.format.json(), // structured
  transports: [new winston.transports.Console()]
})

// Register Fastify plugins for parsing
fastify.register(require('@fastify/formbody'))
fastify.register(require('@fastify/multipart'), { attachFieldsToBody: true })
fastify.register(require('@fastify/cookie'), { hook: 'onRequest', secret: 'my-secret' })

iast.initPlugins(fastify)
iast.initData().catch(() => {})

fastify.addContentTypeParser('application/xml', { parseAs: 'string' }, (req, body, done) => {
  try {
    const xml2js = require('xml2js')
    xml2js.parseString(body, (err, result) => {
      if (err) {
        err.statusCode = 400
        return done(err, undefined)
      }
      done(null, result)
    })
  } catch (err) {
    done(err, undefined)
  }
})

fastify.addContentTypeParser('application/octet-stream', { parseAs: 'buffer' }, function (req, body, done) {
  done(null, body)
})

fastify.addContentTypeParser('text/plain', { parseAs: 'buffer' }, function (req, body, done) {
  done(null, body)
})

fastify.get('/', async (request, reply) => {
  console.log('Received a request')
  return 'Hello\n'
})

fastify.get('/healthcheck', async (request, reply) => {
  return {
    status: 'ok',
    library: {
      name: 'nodejs',
      version: require('dd-trace/package.json').version
    }
  }
})

fastify.all('/waf', async (request, reply) => {
  return 'Hello\n'
})

fastify.all('/waf/*', async (request, reply) => {
  return 'Hello\n'
})

fastify.get('/sample_rate_route/:i', async (request, reply) => {
  return 'OK'
})

fastify.get('/api_security/sampling/:status', async (request, reply) => {
  reply.status(parseInt(request.params.status) || 200)
  return 'Hello!'
})

fastify.get('/api_security_sampling/:i', async (request, reply) => {
  return 'OK'
})

fastify.get('/params/:value', async (request, reply) => {
  return 'OK'
})

fastify.get('/headers', async (request, reply) => {
  reply.headers({
    'content-type': 'text/plain',
    'content-length': '42',
    'content-language': 'en-US'
  })

  return 'Hello, headers!'
})

fastify.get('/customResponseHeaders', (request, reply) => {
  reply.headers({
    'content-type': 'text/plain',
    'content-language': 'en-US',
    'x-test-header-1': 'value1',
    'x-test-header-2': 'value2',
    'x-test-header-3': 'value3',
    'x-test-header-4': 'value4',
    'x-test-header-5': 'value5'
  })
  return 'OK'
})

fastify.get('/exceedResponseHeaders', (request, reply) => {
  reply.header('content-type', 'text/plain')
  for (let i = 0; i < 50; i++) {
    reply.header(`x-test-header-${i}`, `value${i}`)
  }
  reply.header('content-language', 'en-US')
  return 'OK'
})

fastify.get('/identify', async (request, reply) => {
  tracer.setUser({
    id: 'usr.id',
    email: 'usr.email',
    name: 'usr.name',
    session_id: 'usr.session_id',
    role: 'usr.role',
    scope: 'usr.scope'
  })
  return 'OK'
})

fastify.get('/session/new', async (request, reply) => {
  // endpoint needs to be present to pass a test, but is currently not implemented properly
  // request.session.someData = 'blabla' // needed for the session to be saved
  // return request.session.sessionId
})

fastify.get('/status', async (request, reply) => {
  reply.status(parseInt(request.query.code))
  return 'OK'
})

fastify.get('/make_distant_call', async (request, reply) => {
  const url = request.query.url
  console.log(url)

  const parsedUrl = new URL(url)

  const options = {
    hostname: parsedUrl.hostname,
    port: parsedUrl.port || 80, // Use default port if not provided
    path: parsedUrl.pathname,
    method: 'GET'
  }

  return new Promise((resolve, reject) => {
    const httpRequest = http.request(options, (response) => {
      let responseBody = ''
      response.on('data', (chunk) => {
        responseBody += chunk
      })

      response.on('end', () => {
        resolve({
          url,
          status_code: response.statusCode,
          request_headers: response.req._headers,
          response_headers: response.headers,
          response_body: responseBody
        })
      })
    })

    httpRequest.on('error', (error) => {
      console.log(error)
      resolve({
        url,
        status_code: 500,
        request_headers: null,
        response_headers: null
      })
    })

    httpRequest.end()
  })
})

fastify.get('/user_login_success_event', async (request, reply) => {
  const userId = request.query.event_user_id || 'system_tests_user'

  tracer.appsec.trackUserLoginSuccessEvent({
    id: userId,
    email: 'system_tests_user@system_tests_user.com',
    name: 'system_tests_user'
  }, { metadata0: 'value0', metadata1: 'value1' })

  return 'OK'
})

fastify.get('/user_login_failure_event', async (request, reply) => {
  const userId = request.query.event_user_id || 'system_tests_user'
  let exists = true
  const query = request.query
  if (query && 'event_user_exists' in query) {
    exists = request.query.event_user_exists.toLowerCase() === 'true'
  }

  tracer.appsec.trackUserLoginFailureEvent(userId, exists, { metadata0: 'value0', metadata1: 'value1' })

  return 'OK'
})

fastify.get('/custom_event', async (request, reply) => {
  const eventName = request.query.event_name || 'system_tests_event'

  tracer.appsec.trackCustomEvent(eventName, { metadata0: 'value0', metadata1: 'value1' })

  return 'OK'
})

fastify.post('/user_login_success_event_v2', async (request, reply) => {
  const login = request.body.login
  const userId = request.body.user_id
  const metadata = request.body.metadata

  tracer.appsec.eventTrackingV2?.trackUserLoginSuccess(login, userId, metadata)

  return 'OK'
})

fastify.post('/user_login_failure_event_v2', async (request, reply) => {
  const login = request.body.login
  const exists = request.body.exists?.trim() === 'true'
  const metadata = request.body.metadata

  tracer.appsec.eventTrackingV2?.trackUserLoginFailure(login, exists, metadata)

  return 'OK'
})

fastify.get('/users', async (request, reply) => {
  const user = {}
  if (request.query.user) {
    user.id = request.query.user
  } else {
    user.id = 'anonymous'
  }

  tracer.setUser(user)

  const shouldBlock = tracer.appsec.isUserBlocked(user)
  if (shouldBlock) {
    tracer.appsec.blockRequest(request.raw, reply.raw)
  } else {
    return `Hello ${user.id}`
  }
})

fastify.get('/stub_dbm', async (request, reply) => {
  const integration = request.query.integration
  const operation = request.query.operation

  if (integration === 'pg') {
    tracer.use(integration, { dbmPropagationMode: 'full' })
    const dbmComment = await pgsql.doOperation(operation)
    return { status: 'ok', dbm_comment: dbmComment }
  } else if (integration === 'mysql2') {
    tracer.use(integration, { dbmPropagationMode: 'full' })
    const result = await mysql.doOperation(operation)
    return { status: 'ok', dbm_comment: result }
  } else if (integration === 'mssql') {
    tracer.use(integration, { dbmPropagationMode: 'full' })
    return await mssql.doOperation(operation)
  }
})

try {
  dsm.initRoutes(fastify, tracer)
} catch (e) {
  console.error('DSM routes initialization has failed', e)
}

try {
  apiGateway.initRoutes(fastify)
} catch (e) {
  console.error('Api Gateway routes initialization has failed', e)
}

fastify.get('/kafka/produce', async (request, reply) => {
  const topic = request.query.topic

  try {
    await kafkaProduce(topic, 'Hello from Kafka JS')
    reply.status(200)
    return '[Kafka] produce ok'
  } catch (error) {
    console.error(error)
    reply.status(500)
    return 'Internal Server Error during Kafka produce'
  }
})

fastify.get('/kafka/consume', async (request, reply) => {
  const topic = request.query.topic
  const timeout = request.query.timeout ? request.query.timeout * 1000 : 60000

  try {
    await kafkaConsume(topic, timeout)
    reply.status(200)
    return '[Kafka] consume ok'
  } catch (error) {
    console.error(error)
    reply.status(500)
    return 'Internal Server Error during Kafka consume'
  }
})

fastify.get('/log/library', (request, reply) => {
  const msg = request.query.msg || 'msg'
  const logger = (
    request.query.structured === true ||
    request.query.structured?.toString().toLowerCase() === 'true' ||
    request.query.structured === undefined
  )
    ? jsonLogger
    : plainLogger
  switch (request.query.level) {
    case 'warn':
      logger.warn(msg)
      break
    case 'error':
      logger.error(msg)
      break
    default:
      logger.info(msg)
  }
  return 'OK'
})

fastify.get('/sqs/produce', async (request, reply) => {
  const queue = request.query.queue
  const message = request.query.message
  console.log(`[SQS] Produce: ${message}`)

  try {
    await sqsProduce(queue, message)
    reply.status(200)
    return '[SQS] produce ok'
  } catch (error) {
    console.error(error)
    reply.status(500)
    return '[SQS] Internal Server Error during SQS produce'
  }
})

fastify.get('/sqs/consume', async (request, reply) => {
  const queue = request.query.queue
  const message = request.query.message
  const timeout = parseInt(request.query.timeout) ?? 5
  console.log(`[SQS] Consume, Expected: ${message}`)

  try {
    await sqsConsume(queue, timeout * 1000, message)
    reply.status(200)
    return '[SQS] consume ok'
  } catch (error) {
    console.error(error)
    reply.status(500)
    return '[SQS] Internal Server Error during SQS consume'
  }
})

fastify.get('/sns/produce', async (request, reply) => {
  const queue = request.query.queue
  const topic = request.query.topic
  const message = request.query.message
  console.log(`[SNS->SQS] Produce: ${message}`)

  try {
    await snsPublish(queue, topic, message)
    reply.status(200)
    return '[SNS] publish ok'
  } catch (error) {
    console.error(error)
    reply.status(500)
    return '[SNS] Internal Server Error during SNS publish'
  }
})

fastify.get('/sns/consume', async (request, reply) => {
  const queue = request.query.queue
  const timeout = parseInt(request.query.timeout) ?? 5
  const message = request.query.message
  console.log(`[SNS->SQS] Consume, Expected: ${message}`)

  try {
    await snsConsume(queue, timeout * 1000, message)
    reply.status(200)
    return '[SNS->SQS] consume ok'
  } catch (error) {
    console.error(error)
    reply.status(500)
    return '[SNS->SQS] Internal Server Error during SQS consume from SNS'
  }
})

fastify.get('/kinesis/produce', async (request, reply) => {
  const stream = request.query.stream
  const message = request.query.message
  console.log(`[Kinesis] Produce: ${message}`)

  try {
    await kinesisProduce(stream, message, '1', null)
    reply.status(200)
    return '[Kinesis] publish ok'
  } catch (error) {
    console.error(error)
    reply.status(500)
    return '[Kinesis] Internal Server Error during Kinesis publish'
  }
})

fastify.get('/kinesis/consume', async (request, reply) => {
  const stream = request.query.stream
  const timeout = parseInt(request.query.timeout) ?? 5
  const message = request.query.message
  console.log(`[Kinesis] Consume, Expected: ${message}`)

  try {
    await kinesisConsume(stream, timeout * 1000, message)
    reply.status(200)
    return '[Kinesis] consume ok'
  } catch (error) {
    console.error(error)
    reply.status(500)
    return '[Kinesis] Internal Server Error during Kinesis consume'
  }
})

fastify.get('/rabbitmq/produce', async (request, reply) => {
  const queue = request.query.queue
  const exchange = request.query.exchange
  const routingKey = 'systemTestDirectRoutingKeyContextPropagation'
  console.log('[RabbitMQ] produce')

  try {
    await rabbitmqProduce(queue, exchange, routingKey, 'Node.js Produce Context Propagation Test RabbitMQ')
    reply.status(200)
    return '[RabbitMQ] produce ok'
  } catch (error) {
    console.error(error)
    reply.status(500)
    return '[RabbitMQ] Internal Server Error during RabbitMQ produce'
  }
})

fastify.get('/rabbitmq/consume', async (request, reply) => {
  const queue = request.query.queue
  const timeout = parseInt(request.query.timeout) ?? 5
  console.log('[RabbitMQ] consume')

  try {
    await rabbitmqConsume(queue, timeout * 1000)
    reply.status(200)
    return '[RabbitMQ] consume ok'
  } catch (error) {
    console.error(error)
    reply.status(500)
    return '[RabbitMQ] Internal Server Error during RabbitMQ consume'
  }
})

fastify.get('/load_dependency', async (request, reply) => {
  console.log('Load dependency endpoint')
  require('glob')
  return 'Loaded a dependency'
})

fastify.all('/tag_value/:tag_value/:status_code', async (request, reply) => {
  const web = require('dd-trace/packages/dd-trace/src/plugins/util/web')
  web.root(request.raw).setTag('appsec.events.system_tests_appsec_event.value', request.params.tag_value)

  for (const [k, v] of Object.entries(request.query)) {
    reply.header(k, v)
  }

  reply.status(parseInt(request.params.status_code) || 200)

  if (request.params.tag_value.startsWith?.('payload_in_response_body') && request.method === 'POST') {
    return { payload: request.body }
  } else {
    return 'Value tagged'
  }
})

fastify.get('/db', async (request, reply) => {
  console.log('Service: ' + request.query.service)
  console.log('Operation: ' + request.query.operation)

  if (request.query.service === 'postgresql') {
    return await pgsql.doOperation(request.query.operation)
  } else if (request.query.service === 'mysql') {
    return await mysql.doOperation(request.query.operation)
  } else if (request.query.service === 'mssql') {
    return await mssql.doOperation(request.query.operation)
  }
})

fastify.get('/otel_drop_in_default_propagator_extract', async (request, reply) => {
  const api = require('@opentelemetry/api')
  const ctx = api.propagation.extract(api.context.active(), request.headers)
  const spanContext = api.trace.getSpan(ctx).spanContext()

  const result = {}
  result.trace_id = parseInt(spanContext.traceId.substring(16), 16)
  result.span_id = parseInt(spanContext.spanId, 16)
  result.tracestate = spanContext.traceState.serialize()

  return result
})

fastify.get('/otel_drop_in_default_propagator_inject', async (request, reply) => {
  const api = require('@opentelemetry/api')
  const otelTracer = api.trace.getTracer('my-application', '0.1.0')
  const span = otelTracer.startSpan('main')
  const result = {}

  api.propagation.inject(
    api.trace.setSpanContext(api.ROOT_CONTEXT, span.spanContext()),
    result,
    api.defaultTextMapSetter
  )
  return result
})

fastify.post('/shell_execution', async (request, reply) => {
  const { spawnSync } = require('child_process')
  const options = { shell: !!request?.body?.options?.shell }
  const reqArgs = request?.body?.args

  let args
  if (typeof reqArgs === 'string') {
    args = reqArgs.split(' ')
  } else {
    args = reqArgs
  }

  const response = spawnSync(request?.body?.command, args, options)
  return response
})

fastify.get('/createextraservice', async (request, reply) => {
  const serviceName = request.query.serviceName

  const span = tracer.scope().active()
  span.setTag('service.name', serviceName)

  return 'OK'
})

iast.initRoutes(fastify, tracer)

di.initRoutes(fastify)

fastify.get('/flush', async (request, reply) => {
  // doesn't have a callback :(
  // tracer._tracer?._dataStreamsProcessor?.writer?.flush?.()
  tracer.dogstatsd?.flush?.()
  tracer._pluginManager?._pluginsByName?.openai?.metrics?.flush?.()

  // does have a callback :)
  const promises = []

  try {
    const { profiler } = require('dd-trace/packages/dd-trace/src/profiling/')
    if (profiler?._collect) {
      promises.push(profiler._collect('on_shutdown'))
    }
  } catch (err) {
    console.error('Unable to flush profiler:', err)
  }

  if (tracer._tracer?._exporter?._writer?.flush) {
    promises.push(promisify((err) => tracer._tracer._exporter._writer.flush(err))())
  }

  if (tracer._pluginManager?._pluginsByName?.openai?.logger?.flush) {
    promises.push(promisify((err) => tracer._pluginManager._pluginsByName.openai.logger.flush(err))())
  }

  try {
    await Promise.all(promises)
    reply.status(200)
    return 'OK'
  } catch (err) {
    reply.status(500)
    return err
  }
})

fastify.get('/requestdownstream', async (request, reply) => {
  try {
    const resFetch = await axios.get('http://127.0.0.1:7777/returnheaders')
    return resFetch.data
  } catch (e) {
    reply.status(500)
    return e
  }
})

fastify.get('/vulnerablerequestdownstream', async (request, reply) => {
  try {
    crypto.createHash('md5').update('password').digest('hex')
    const resFetch = await axios.get('http://127.0.0.1:7777/returnheaders')
    return resFetch.data
  } catch (e) {
    reply.status(500)
    return e
  }
})

fastify.get('/returnheaders', async (request, reply) => {
  return { ...request.headers }
})

fastify.get('/set_cookie', async (request, reply) => {
  const name = request.query.name
  const value = request.query.value

  reply.header('Set-Cookie', `${name}=${value}`)
  return 'OK'
})

fastify.get('/add_event', async (request, reply) => {
  const rootSpan = tracer.scope().active().context()._trace.started[0]

  rootSpan.addEvent('span.event', { string: 'value', int: 1 }, Date.now())

  reply.status(200)
  return { message: 'Event added' }
})

const startServer = async () => {
  try {
    await fastify.listen({ port: 7777, host: '0.0.0.0' })
    tracer.trace('init.service', () => {})
    console.log('listening')
  } catch (err) {
    fastify.log.error(err)
    process.exit(1)
  }
}

const graphQLEnabled = false
const initGraphQL = () => {
  return graphQLEnabled
    ? require('./graphql')(fastify) // TODO: create graphql folder
    : Promise.resolve()
}

initGraphQL()
  .then(startServer)
  .catch(error => {
    console.error('Failed to start server:', error)
    process.exit(1)
  })
