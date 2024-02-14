'use strict'

const tracer = require('dd-trace').init({
  debug: true
})

const app = require('express')()
const axios = require('axios')
const fs = require('fs')
const passport = require('passport')

const iast = require('./iast')
const { spawnSync } = require('child_process')

const { kinesisProduce, kinesisConsume } = require('./integrations/messaging/aws/kinesis')
const { snsPublish, snsConsume } = require('./integrations/messaging/aws/sns')
const { sqsProduce, sqsConsume } = require('./integrations/messaging/aws/sqs')
const { kafkaProduce, kafkaConsume } = require('./integrations/messaging/kafka/kafka')
const { rabbitmqProduce, rabbitmqConsume } = require('./integrations/messaging/rabbitmq/rabbitmq')

iast.initData().catch(() => {})

app.use(require('body-parser').json())
app.use(require('body-parser').urlencoded({ extended: true }))
app.use(require('express-xml-bodyparser')())
app.use(require('cookie-parser')())
iast.initMiddlewares(app)

app.get('/', (req, res) => {
  console.log('Received a request')
  res.send('Hello\n')
})

app.all(['/waf', '/waf/*'], (req, res) => {
  res.send('Hello\n')
})

app.get('/sample_rate_route/:i', (req, res) => {
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

app.get('/status', (req, res) => {
  res.status(parseInt(req.query.code)).send('OK')
})

app.get('/make_distant_call', (req, res) => {
  const url = req.query.url
  console.log(url)

  axios.get(url)
    .then(response => {
      res.json({
        url,
        status_code: response.statusCode,
        request_headers: null,
        response_headers: null
      })
    })
    .catch(error => {
      console.log(error)
      res.json({
        url,
        status_code: 500,
        request_headers: null,
        response_headers: null
      })
    })
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
  if (req.query && req.query.hasOwnProperty('event_user_exists')) {
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

app.get('/users', (req, res) => {
  const user = {}
  if (req.query.user) {
    user.id = req.query.user
  } else {
    user.id = 'anonymous'
  }

  const shouldBlock = tracer.appsec.isUserBlocked(user)
  if (shouldBlock) {
    tracer.appsec.blockRequest(req, res)
  } else {
    res.send(`Hello ${user.id}`)
  }
})

app.get('/dsm', (req, res) => {
  const integration = req.query.integration

  if (integration === 'kafka') {
    const topic = 'dsm-system-tests-queue'
    const message = 'hello from kafka DSM JS'
    const timeout = req.query.timeout ? req.query.timeout * 10000 : 60000

    kafkaProduce(topic, message)
      .then(() => {
        kafkaConsume(topic, timeout)
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
    const queue = 'dsm-system-tests-queue'
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
    const queue = 'dsm-system-tests-queue-sns'
    const topic = 'dsm-system-tests-topic-sns'
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
    const queue = 'dsm-system-tests-queue'
    const message = 'hello from SQS DSM JS'
    const timeout = req.query.timeout ?? 5
    const exchange = 'systemTestDirectExchange'
    const routingKey = 'systemTestDirectRoutingKey'

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
  } else {
    res.status(400).send('[DSM] Wrong or missing integration, available integrations are [Kafka, RabbitMQ, SNS, SQS]')
  }
})

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

app.get('/sqs/produce', (req, res) => {
  const queue = req.query.queue
  console.log('sqs produce')

  sqsProduce(queue)
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
  const timeout = parseInt(req.query.timeout) ?? 5
  console.log('sqs consume')

  sqsConsume(queue, timeout * 1000)
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

  snsPublish(queue, topic)
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

  snsConsume(queue, timeout * 1000)
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

  kinesisProduce(stream, null, '1', null)
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

  kinesisConsume(stream, timeout * 1000)
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

  rabbitmqProduce(queue, exchange, routingKey, 'NodeJS Produce Context Propagation Test RabbitMQ')
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

app.all('/tag_value/:tag/:status', (req, res) => {
  require('dd-trace/packages/dd-trace/src/plugins/util/web')
    .root(req).setTag('appsec.events.system_tests_appsec_event.value', req.params.tag)

  for (const [k, v] of Object.entries(req.query)) {
    res.set(k, v)
  }

  res.status(req.params.status || 200)

  if (req.params?.tag?.startsWith?.('payload_in_response_body') && req.method === 'POST') {
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

  const pgsql = require('./integrations/db/postgres')
  const mysql = require('./integrations/db/mysql')
  const mssql = require('./integrations/db/mssql')

  if (req.query.service === 'postgresql') {
    res.send(await pgsql.doOperation(req.query.operation))
  } else if (req.query.service === 'mysql') {
    res.send(await mysql.doOperation(req.query.operation))
  } else if (req.query.service === 'mssql') {
    res.send(await mssql.doOperation(req.query.operation))
  }
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

require('./auth')(app, passport, tracer)
require('./graphql')(app).then(() => {
  app.listen(7777, '0.0.0.0', () => {
    tracer.trace('init.service', () => {})
    console.log('listening')
  })
})
