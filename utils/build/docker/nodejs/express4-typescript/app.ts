'use strict'

import { Request, Response } from "express";

const tracer = require('dd-trace').init({ debug: true });

const app = require('express')();
const axios = require('axios');
const passport = require('passport')
const { Kafka } = require("kafkajs")
const { spawnSync } = require('child_process');

const iast = require('./iast')

iast.initData().catch(() => {})

app.use(require('body-parser').json());
app.use(require('body-parser').urlencoded({ extended: true }));
app.use(require('express-xml-bodyparser')());
app.use(require('cookie-parser')());

iast.initMiddlewares(app)

require('./auth')(app, passport, tracer)
iast.initRoutes(app)

app.get('/', (req: Request, res: Response) => {
  console.log('Received a request');
  res.send('Hello\n');
});

app.all(['/waf', '/waf/*'], (req: Request, res: Response) => {
  res.send('Hello\n');
});

app.get('/sample_rate_route/:i', (req: Request, res: Response) => {
  res.send('OK');
});

app.get('/params/:value', (req: Request, res: Response) => {
  res.send('OK');
});

app.get('/headers', (req: Request, res: Response) => {
  res.set({
    'content-type': 'text/plain',
    'content-length': '42',
    'content-language': 'en-US',
  });

  res.send('Hello, headers!');
});

app.get('/identify', (req: Request, res: Response) => {
  tracer.setUser({
    id: 'usr.id',
    email: 'usr.email',
    name: 'usr.name',
    session_id: 'usr.session_id',
    role: 'usr.role',
    scope: 'usr.scope'
  });

  res.send('OK');
});

app.get('/status', (req: Request, res: Response) => {
  res.status(parseInt('' + req.query.code)).send('OK');
});

app.get("/make_distant_call", (req: Request, res: Response) => {
  const url = req.query.url;
  console.log(url);

  axios.get(url)
    .then((response: Response) => {
      res.json({
        url: url,
        status_code: response.statusCode,
        request_headers: null,
        response_headers: null,
      });
    })
    .catch((error: Error) => {
      console.log(error);
      res.json({
        url: url,
        status_code: 500,
        request_headers: null,
        response_headers: null,
      });
    });
});

app.get("/user_login_success_event", (req: Request, res: Response) => {
  const userId = req.query.event_user_id || "system_tests_user";

  tracer.appsec.trackUserLoginSuccessEvent({
    id: userId,
    email: "system_tests_user@system_tests_user.com",
    name: "system_tests_user"
  }, { metadata0: "value0", metadata1: "value1" });

  res.send("OK");
});

app.get("/user_login_failure_event", (req: Request, res: Response) => {
  const userId = req.query.event_user_id || "system_tests_user";
  let exists = true;
  if (req.query && req.query.hasOwnProperty("event_user_exists")) {
    exists = (req.query.event_user_exists + "").toLowerCase() === "true"
  }

  tracer.appsec.trackUserLoginFailureEvent(userId, exists, { metadata0: "value0", metadata1: "value1" });

  res.send("OK");
});

app.get("/custom_event", (req: Request, res: Response) => {
  const eventName = req.query.event_name || "system_tests_event";

  tracer.appsec.trackCustomEvent(eventName, { metadata0: "value0", metadata1: "value1" });

  res.send("OK");
});

app.get("/users", (req: Request, res: Response) => {
  let user: { id?: any } = {}
  if (req.query['user']) {
    user.id = req.query['user']
  } else {
    user.id = 'anonymous'
  }

  const shouldBlock = tracer.appsec.isUserBlocked(user)
  if (shouldBlock) {
    tracer.appsec.blockRequest(req, res)
  } else {
    res.send(`Hello ${user.id}`)
  }
});

app.get("/dsm", (req: Request, res: Response) => {
  const kafka = new Kafka({
    clientId: 'my-app',
    brokers: ['kafka:9092'],
    retry: {
      initialRetryTime: 100, // Time to wait in milliseconds before the first retry
      retries: 20, // Number of retries before giving up
    },
  })
  const producer = kafka.producer()
  const doKafkaOperations = async () => {
    await producer.connect()
    await producer.send({
      topic: 'dsm-system-tests-queue',
      messages: [
        { value: 'hello world!' },
      ],
    })
    await producer.disconnect()

    const consumer = kafka.consumer({ groupId: 'testgroup1' })

    await consumer.connect()
    await consumer.subscribe({ topic: 'dsm-system-tests-queue', fromBeginning: true })

    await consumer.run({
      eachMessage: async () => {
        await consumer.stop();
        await consumer.disconnect();
      },
    })
  }
  doKafkaOperations()
    .then(() => {
      res.send('ok');
    })
    .catch((error: Error) => {
      console.error(error);
      res.status(500).send('Internal Server Error');
    });
});

app.get('/load_dependency', (req: Request, res: Response) => {
  console.log('Load dependency endpoint');
  const glob = require("glob")
  res.send("Loaded a dependency")
});

app.all('/tag_value/:tag/:status', (req: Request, res: Response) => {
  require('dd-trace/packages/dd-trace/src/plugins/util/web').root(req).setTag('appsec.events.system_tests_appsec_event.value', req.params.tag);

  for (const [k, v] of Object.entries(req.query)) {
    res.set(k, v && v.toString());
  }

  res.status(parseInt(req.params.status) || 200)

  if (req.params?.tag?.startsWith?.('payload_in_response_body') && req.method === 'POST') {
    res.send({ payload: req.body });
  } else {
    res.send('Value tagged');
  }
});

app.post('/shell_execution', (req: Request, res: Response) => {
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

app.get('/createextraservice', (req: Request, res: Response) => {
  const serviceName = req.query['serviceName']

  const span = tracer.scope().active()
  span.setTag('service.name', serviceName)

  res.send('OK')
})

require('./graphql')(app).then(() => {
  app.listen(7777, '0.0.0.0', () => {
    tracer.trace('init.service', () => { })
    console.log('listening')
  })
})
