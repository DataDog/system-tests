'use strict'

const opts = {
  debug: true,
  flushInterval: 5000
}

// This mimics a scenario where a user has one config setting set in multiple sources
// so that config chaining data is sent
if (process.env.CONFIG_CHAINING_TEST) {
  opts.logInjection = true
}

const tracer = require('dd-trace').init(opts)

const { promisify } = require('util')
const app = require('express')()
const axios = require('axios')
const http = require('http')
const fs = require('fs')
const crypto = require('crypto')
const winston = require('winston')
const api = require('@opentelemetry/api')

const iast = require('./iast')
const dsm = require('./dsm')
const di = require('./debugger')

const { spawnSync } = require('child_process')

const pgsql = require('./integrations/db/postgres')
const mysql = require('./integrations/db/mysql')
const mssql = require('./integrations/db/mssql')
const apiGateway = require('./integrations/api_gateway')
const { graphQLEnabled, unnamedWildcard } = require('./config')

const multer = require('multer')
const uploadToMemory = multer({ storage: multer.memoryStorage(), limits: { fileSize: 200000 } })

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

iast.initData().catch(() => {})

app.use(require('body-parser').json())
app.use(require('body-parser').urlencoded({ extended: true }))
app.use(require('express-xml-bodyparser')())
app.use(require('cookie-parser')())
iast.initMiddlewares(app)

require('./auth')(app, tracer)

app.get('/', (req, res) => {
  console.log('Received a request')
  res.send('Hello\n')
})

app.get('/healthcheck', (req, res) => {
  res.json({
    status: 'ok',
    library: {
      name: 'nodejs',
      version: require('dd-trace/package.json').version
    }
  })
})

app.post('/waf', uploadToMemory.single('foo'), (req, res) => {
  res.send('Hello\n')
})

const wafWildcardPath = unnamedWildcard ? '/waf/*' : '/waf/*name'
app.all(['/waf', wafWildcardPath], (req, res) => {
  res.send('Hello\n')
})

app.get('/sample_rate_route/:i', (req, res) => {
  res.send('OK')
})

app.get('/api_security/sampling/:status', (req, res) => {
  res.status(parseInt(req.params.status) || 200)
  res.send('Hello!')
})

app.get('/api_security_sampling/:i', (req, res) => {
  res.send('OK')
})

app.get('/params/:value', (req, res) => {
  res.send('OK')
})

app.get('/headers', (req, res) => {
  res.set({
    'content-type': 'text/plain',
    'content-length': '42',
    'content-language': 'en-US'
  })

  res.send('Hello, headers!')
})

app.get('/customResponseHeaders', (req, res) => {
  res.set({
    'content-type': 'text/plain',
    'content-language': 'en-US',
    'x-test-header-1': 'value1',
    'x-test-header-2': 'value2',
    'x-test-header-3': 'value3',
    'x-test-header-4': 'value4',
    'x-test-header-5': 'value5'
  })
  res.send('OK')
})

app.get('/authorization_related_headers', (req, res) => {
  res.set({
    'Authorization': 'value1',
    'Proxy-Authorization': 'value2',
    'WWW-Authenticate': 'value3',
    'Proxy-Authenticate': 'value4',
    'Authentication-Info': 'value5',
    'Proxy-Authentication-Info': 'value6',
    'Cookie': 'value7',
    'Set-Cookie': 'value8',
    'content-type': 'text/plain'
  })
  res.send('OK')
})

app.get('/exceedResponseHeaders', (req, res) => {
  res.set('content-language', 'text/plain')
  for (let i = 0; i < 50; i++) {
    res.set(`x-test-header-${i}`, `value${i}`)
  }
  res.set('content-language', 'en-US')
  res.send('OK')
})

app.get('/identify', (req, res) => {
  tracer.setUser({
    id: 'usr.id',
    email: 'usr.email',
    name: 'usr.name',
    session_id: 'usr.session_id',
    role: 'usr.role',
    scope: 'usr.scope'
  })

  res.send('OK')
})

app.get('/session/new', (req, res) => {
  req.session.someData = 'blabla' // needed for the session to be saved
  res.send(req.sessionID)
})

app.get('/status', (req, res) => {
  res.status(parseInt(req.query.code)).send('OK')
})

app.get('/make_distant_call', (req, res) => {
  const url = req.query.url
  console.log(url)

  const parsedUrl = new URL(url)

  const options = {
    hostname: parsedUrl.hostname,
    port: parsedUrl.port || 80, // Use default port if not provided
    path: parsedUrl.pathname,
    method: 'GET'
  }

  const request = http.request(options, (response) => {
    let responseBody = ''
    response.on('data', (chunk) => {
      responseBody += chunk
    })

    response.on('end', () => {
      res.json({
        url,
        status_code: response.statusCode,
        request_headers: response.req._headers,
        response_headers: response.headers,
        response_body: responseBody
      })
    })
  })

  // Handle errors
  request.on('error', (error) => {
    console.log(error)
    res.json({
      url,
      status_code: 500,
      request_headers: null,
      response_headers: null
    })
  })

  request.end()
})

app.get('/user_login_success_event', (req, res) => {
  const userId = req.query.event_user_id || 'system_tests_user'

  tracer.appsec.trackUserLoginSuccessEvent({
    id: userId,
    email: 'system_tests_user@system_tests_user.com',
    name: 'system_tests_user'
  }, { metadata0: 'value0', metadata1: 'value1' })

  res.send('OK')
})

app.get('/user_login_failure_event', (req, res) => {
  const userId = req.query.event_user_id || 'system_tests_user'
  let exists = true
  const query = req.query
  if (query && 'event_user_exists' in query) {
    exists = req.query.event_user_exists.toLowerCase() === 'true'
  }

  tracer.appsec.trackUserLoginFailureEvent(userId, exists, { metadata0: 'value0', metadata1: 'value1' })

  res.send('OK')
})

app.get('/custom_event', (req, res) => {
  const eventName = req.query.event_name || 'system_tests_event'

  tracer.appsec.trackCustomEvent(eventName, { metadata0: 'value0', metadata1: 'value1' })

  res.send('OK')
})

app.post('/user_login_success_event_v2', (req, res) => {
  const login = req.body.login
  const userId = req.body.user_id
  const metadata = req.body.metadata

  tracer.appsec.eventTrackingV2?.trackUserLoginSuccess(login, userId, metadata)

  res.send('OK')
})

app.post('/user_login_failure_event_v2', (req, res) => {
  const login = req.body.login
  const exists = req.body.exists?.trim() === 'true'
  const metadata = req.body.metadata

  tracer.appsec.eventTrackingV2?.trackUserLoginFailure(login, exists, metadata)

  res.send('OK')
})

app.get('/users', (req, res) => {
  const user = {}
  if (req.query.user) {
    user.id = req.query.user
  } else {
    user.id = 'anonymous'
  }

  tracer.setUser(user)

  const shouldBlock = tracer.appsec.isUserBlocked(user)
  if (shouldBlock) {
    tracer.appsec.blockRequest(req, res)
  } else {
    res.send(`Hello ${user.id}`)
  }
})

app.get('/stub_dbm', async (req, res) => {
  const integration = req.query.integration
  const operation = req.query.operation

  if (integration === 'pg') {
    tracer.use(integration, { dbmPropagationMode: 'full' })
    const dbmComment = await pgsql.doOperation(operation)
    res.send({ status: 'ok', dbm_comment: dbmComment })
  } else if (integration === 'mysql2') {
    tracer.use(integration, { dbmPropagationMode: 'full' })
    const result = await mysql.doOperation(operation)
    res.send({ status: 'ok', dbm_comment: result })
  } else if (integration === 'mssql') {
    tracer.use(integration, { dbmPropagationMode: 'full' })
    res.send(await mssql.doOperation(operation))
  }
})

try {
  dsm.initRoutes(app, tracer)
} catch (e) {
  console.error('DSM routes initialization has failed', e)
}

try {
  apiGateway.initRoutes(app, tracer)
} catch (e) {
  console.error('Api Gateway routes initialization has failed', e)
}

app.get('/kafka/produce', (req, res) => {
  const topic = req.query.topic

  kafkaProduce(topic, 'Hello from Kafka JS')
    .then(() => {
      res.status(200).send('[Kafka] produce ok')
    })
    .catch((error) => {
      console.error(error)
      res.status(500).send('Internal Server Error during Kafka produce')
    })
})

app.get('/kafka/consume', (req, res) => {
  const topic = req.query.topic
  const timeout = req.query.timeout ? req.query.timeout * 1000 : 60000

  kafkaConsume(topic, timeout)
    .then(() => {
      res.status(200).send('[Kafka] consume ok')
    })
    .catch((error) => {
      console.error(error)
      res.status(500).send('Internal Server Error during Kafka consume')
    })
})

app.get('/log/library', (req, res) => {
  const msg = req.query.msg || 'msg'
  const logger = (
    req.query.structured === true ||
    req.query.structured?.toString().toLowerCase() === 'true' ||
    req.query.structured === undefined
  )
    ? jsonLogger
    : plainLogger
  switch (req.query.level) {
    case 'warn':
      logger.warn(msg)
      break
    case 'error':
      logger.error(msg)
      break
    default:
      logger.info(msg)
  }
  res.send('OK')
})

app.get('/sqs/produce', (req, res) => {
  const queue = req.query.queue
  const message = req.query.message
  console.log(`[SQS] Produce: ${message}`)

  sqsProduce(queue, message)
    .then(() => {
      res.status(200).send('[SQS] produce ok')
    })
    .catch((error) => {
      console.error(error)
      res.status(500).send('[SQS] Internal Server Error during SQS produce')
    })
})

app.get('/sqs/consume', (req, res) => {
  const queue = req.query.queue
  const message = req.query.message
  const timeout = parseInt(req.query.timeout) ?? 5
  console.log(`[SQS] Consume, Expected: ${message}`)

  sqsConsume(queue, timeout * 1000, message)
    .then(() => {
      res.status(200).send('[SQS] consume ok')
    })
    .catch((error) => {
      console.error(error)
      res.status(500).send('[SQS] Internal Server Error during SQS consume')
    })
})

app.get('/sns/produce', (req, res) => {
  const queue = req.query.queue
  const topic = req.query.topic
  const message = req.query.message
  console.log(`[SNS->SQS] Produce: ${message}`)

  snsPublish(queue, topic, message)
    .then(() => {
      res.status(200).send('[SNS] publish ok')
    })
    .catch((error) => {
      console.error(error)
      res.status(500).send('[SNS] Internal Server Error during SNS publish')
    })
})

app.get('/sns/consume', (req, res) => {
  const queue = req.query.queue
  const timeout = parseInt(req.query.timeout) ?? 5
  const message = req.query.message
  console.log(`[SNS->SQS] Consume, Expected: ${message}`)

  snsConsume(queue, timeout * 1000, message)
    .then(() => {
      res.status(200).send('[SNS->SQS] consume ok')
    })
    .catch((error) => {
      console.error(error)
      res.status(500).send('[SNS->SQS] Internal Server Error during SQS consume from SNS')
    })
})

app.get('/kinesis/produce', (req, res) => {
  const stream = req.query.stream
  const message = req.query.message
  console.log(`[Kinesis] Produce: ${message}`)

  kinesisProduce(stream, message, '1', null)
    .then(() => {
      res.status(200).send('[Kinesis] publish ok')
    })
    .catch((error) => {
      console.error(error)
      res.status(500).send('[Kinesis] Internal Server Error during Kinesis publish')
    })
})

app.get('/kinesis/consume', (req, res) => {
  const stream = req.query.stream
  const timeout = parseInt(req.query.timeout) ?? 5
  const message = req.query.message
  console.log(`[Kinesis] Consume, Expected: ${message}`)

  kinesisConsume(stream, timeout * 1000, message)
    .then(() => {
      res.status(200).send('[Kinesis] consume ok')
    })
    .catch((error) => {
      console.error(error)
      res.status(500).send('[Kinesis] Internal Server Error during Kinesis consume')
    })
})

app.get('/rabbitmq/produce', (req, res) => {
  const queue = req.query.queue
  const exchange = req.query.exchange
  const routingKey = 'systemTestDirectRoutingKeyContextPropagation'
  console.log('[RabbitMQ] produce')

  rabbitmqProduce(queue, exchange, routingKey, 'Node.js Produce Context Propagation Test RabbitMQ')
    .then(() => {
      res.status(200).send('[RabbitMQ] produce ok')
    })
    .catch((error) => {
      console.error(error)
      res.status(500).send('[RabbitMQ] Internal Server Error during RabbitMQ produce')
    })
})

app.get('/rabbitmq/consume', (req, res) => {
  const queue = req.query.queue
  const timeout = parseInt(req.query.timeout) ?? 5
  console.log('[RabbitMQ] consume')

  rabbitmqConsume(queue, timeout * 1000)
    .then(() => {
      res.status(200).send('[RabbitMQ] consume ok')
    })
    .catch((error) => {
      console.error(error)
      res.status(500).send('[RabbitMQ] Internal Server Error during RabbitMQ consume')
    })
})

app.get('/load_dependency', (req, res) => {
  console.log('Load dependency endpoint')
  require('glob')
  res.send('Loaded a dependency')
})

app.all('/tag_value/:tag_value/:status_code', (req, res) => {
  require('dd-trace/packages/dd-trace/src/plugins/util/web')
    .root(req).setTag('appsec.events.system_tests_appsec_event.value', req.params.tag_value)

  for (const [k, v] of Object.entries(req.query)) {
    res.set(k, v)
  }

  res.status(parseInt(req.params.status_code) || 200)

  if (req.params.tag_value.startsWith?.('payload_in_response_body') && req.method === 'POST') {
    res.send({ payload: req.body })
  } else {
    res.send('Value tagged')
  }
})

app.get('/read_file', (req, res) => {
  const path = req.query.file
  fs.readFile(path, (err, data) => {
    if (err) {
      console.error(err)
      res.status(500).send('ko')
    }
    res.send(data)
  })
})

app.get('/db', async (req, res) => {
  console.log('Service: ' + req.query.service)
  console.log('Operation: ' + req.query.operation)

  if (req.query.service === 'postgresql') {
    res.send(await pgsql.doOperation(req.query.operation))
  } else if (req.query.service === 'mysql') {
    res.send(await mysql.doOperation(req.query.operation))
  } else if (req.query.service === 'mssql') {
    res.send(await mssql.doOperation(req.query.operation))
  }
})

app.get('/otel_drop_in_default_propagator_extract', (req, res) => {
  const ctx = api.propagation.extract(api.context.active(), req.headers)
  const spanContext = api.trace.getSpan(ctx).spanContext()

  const result = {}
  result.trace_id = parseInt(spanContext.traceId.substring(16), 16)
  result.span_id = parseInt(spanContext.spanId, 16)
  result.tracestate = spanContext.traceState.serialize()
  // result.baggage = api.propagation.getBaggage(spanContext).toString()

  res.json(result)
})

app.get('/otel_drop_in_default_propagator_inject', (req, res) => {
  const tracer = api.trace.getTracer('my-application', '0.1.0')
  const span = tracer.startSpan('main')
  const result = {}

  api.propagation.inject(
    api.trace.setSpanContext(api.ROOT_CONTEXT, span.spanContext()), result, api.defaultTextMapSetter)
  res.json(result)
})

app.post('/shell_execution', (req, res) => {
  const options = { shell: !!req?.body?.options?.shell }
  const reqArgs = req?.body?.args

  let args
  if (typeof reqArgs === 'string') {
    args = reqArgs.split(' ')
  } else {
    args = reqArgs
  }

  const response = spawnSync(req?.body?.command, args, options)

  res.send(response)
})

app.get('/createextraservice', (req, res) => {
  const serviceName = req.query.serviceName

  const span = tracer.scope().active()
  span.setTag('service.name', serviceName)

  res.send('OK')
})

iast.initRoutes(app, tracer)

di.initRoutes(app)

// try to flush as much stuff as possible from the library
app.get('/flush', (req, res) => {
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
    promises.push(promisify((err) => tracer._tracer._exporter._writer.flush(err)))
  }

  if (tracer._pluginManager?._pluginsByName?.openai?.logger?.flush) {
    promises.push(promisify((err) => tracer._pluginManager._pluginsByName.openai.logger.flush(err)))
  }

  Promise.all(promises).then(() => {
    res.status(200).send('OK')
  }).catch((err) => {
    res.status(500).send(err)
  })
})

app.get('/requestdownstream', async (req, res) => {
  try {
    const resFetch = await axios.get('http://127.0.0.1:7777/returnheaders')
    return res.json(resFetch.data)
  } catch (e) {
    return res.status(500).send(e)
  }
})

app.get('/vulnerablerequestdownstream', async (req, res) => {
  try {
    crypto.createHash('md5').update('password').digest('hex')
    const resFetch = await axios.get('http://127.0.0.1:7777/returnheaders')
    return res.json(resFetch.data)
  } catch (e) {
    return res.status(500).send(e)
  }
})

app.get('/returnheaders', (req, res) => {
  res.json({ ...req.headers })
})

app.get('/set_cookie', (req, res) => {
  const name = req.query.name
  const value = req.query.value

  res.header('Set-Cookie', `${name}=${value}`)
  res.send('OK')
})

app.get('/add_event', (req, res) => {
  const rootSpan = tracer.scope().active().context()._trace.started[0]

  rootSpan.addEvent('span.event', { string: 'value', int: 1 }, Date.now())

  res.status(200).json({ message: 'Event added' })
})

require('./rasp')(app)

const startServer = () => {
  return new Promise((resolve) => {
    app.listen(7777, '0.0.0.0', () => {
      tracer.trace('init.service', () => {})
      console.log('listening')
      resolve()
    })
  })
}

// apollo-server does not support Express 5 yet https://github.com/apollographql/apollo-server/issues/7928
const initGraphQL = () => {
  return graphQLEnabled
    ? require('./graphql')(app)
    : Promise.resolve()
}

initGraphQL()
  .then(startServer)
  .catch(error => {
    console.error('Failed to start server:', error)
    process.exit(1)
  })
