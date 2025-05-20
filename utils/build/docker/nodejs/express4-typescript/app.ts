'use strict'

import { Request, Response } from "express";
import http from 'http';

const tracer = require('dd-trace').init({ debug: true, flushInterval: 5000 });

const { promisify } = require('util')
const app = require('express')()
const axios = require('axios')
const { Kafka } = require("kafkajs")
const { spawnSync } = require('child_process')
const crypto = require('crypto')

const multer = require('multer')
const uploadToMemory = multer({ storage: multer.memoryStorage(), limits: { fileSize: 200000 } })

const iast = require('./iast')
const di = require('./debugger')

iast.initData().catch(() => {})

app.use(require('body-parser').json());
app.use(require('body-parser').urlencoded({ extended: true }));
app.use(require('express-xml-bodyparser')());
app.use(require('cookie-parser')());

iast.initMiddlewares(app)

require('./auth')(app, tracer)
iast.initRoutes(app)

di.initRoutes(app)

app.get('/', (req: Request, res: Response) => {
  console.log('Received a request');
  res.send('Hello\n');
});

app.get('/healthcheck', (req: Request, res: Response) => {
  res.json({
    status: 'ok',
    library: {
      name: 'nodejs',
      version: require('dd-trace/package.json').version
    }
  });
})

app.post('/waf', uploadToMemory.single('foo'), (req: Request, res: Response) => {
  res.send('Hello\n')
})


app.all(['/waf', '/waf/*'], (req: Request, res: Response) => {
  res.send('Hello\n');
});

app.get('/sample_rate_route/:i', (req: Request, res: Response) => {
  res.send('OK');
});

app.get('/api_security/sampling/:status', (req: Request, res: Response) => {
  res.status(parseInt(req.params.status) || 200)
  res.send('Hello!')
})

app.get('/api_security_sampling/:i', (req: Request, res: Response) => {
  res.send('OK')
})

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

app.get('/customResponseHeaders', (req: Request, res: Response) => {
  res.set({
    'content-type': 'text/plain',
    'content-language': 'en-US',
    'x-test-header-1': 'value1',
    'x-test-header-2': 'value2',
    'x-test-header-3': 'value3',
    'x-test-header-4': 'value4',
    'x-test-header-5': 'value5',
  });
  
  res.send('OK');
});

app.get('/exceedResponseHeaders', (req: Request, res: Response) => {
  res.set('content-language', 'text/plain');
  for (let i: number = 0; i < 50; i++) {
    res.set(`x-test-header-${i}`, `value${i}`);
  }
  res.set('content-language', 'en-US');
  
  res.send('OK');
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

app.get('/session/new', (req: Request, res: Response) => {
  // I'm using assign otherwise typescript complains about the unknnown property
  Object.assign(req.session, { someData: 'blabla' }) // needed for the session to be saved
  res.send(req.sessionID)
})

app.get('/status', (req: Request, res: Response) => {
  res.status(parseInt('' + req.query.code)).send('OK');
});

app.get("/make_distant_call", (req: Request, res: Response) => {
  const url = req.query.url
  console.log(url)

  const parsedUrl = new URL(url as string)

  const options = {
    hostname: parsedUrl.hostname,
    port: parsedUrl.port || 80, // Use default port if not provided
    path: parsedUrl.pathname,
    method: 'GET'
  }

  const request = http.request(options, (response: http.IncomingMessage) => {
    let responseBody = ''
    response.on('data', (chunk) => {
      responseBody += chunk
    })

    response.on('end', () => {
      res.json({
        url,
        status_code: response.statusCode,
        request_headers: (response as any).req._headers,
        response_headers: response.headers,
        response_body: responseBody
      })
    })
  })

  // Handle errors
  request.on('error', (error: Error) => {
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

app.post('/user_login_success_event_v2', (req: Request, res: Response) => {
  const login = req.body.login;
  const userId = req.body.user_id;
  const metadata = req.body.metadata;

  tracer.appsec.eventTrackingV2?.trackUserLoginSuccess(login, userId, metadata);

  res.send('OK');
});

app.post('/user_login_failure_event_v2', (req: Request, res: Response) => {
  const login = req.body.login;
  const exists = req.body.exists?.trim() === 'true';
  const metadata = req.body.metadata;

  tracer.appsec.eventTrackingV2?.trackUserLoginFailure(login, exists, metadata);

  res.send('OK');
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

  tracer.setUser(user)

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

app.all('/tag_value/:tag_value/:status_code', (req: Request, res: Response) => {
  require('dd-trace/packages/dd-trace/src/plugins/util/web')
    .root(req).setTag('appsec.events.system_tests_appsec_event.value', req.params.tag_value);

  for (const [k, v] of Object.entries(req.query)) {
    res.set(k, v && v.toString());
  }

  res.status(parseInt(req.params.status_code) || 200)

  if (req.params.tag_value.startsWith?.('payload_in_response_body') && req.method === 'POST') {
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

// try to flush as much stuff as possible from the library
app.get('/flush', (req: Request, res: Response) => {
  // doesn't have a callback :(
  // tracer._tracer?._dataStreamsProcessor?.writer?.flush?.()
  tracer.dogstatsd?.flush?.()
  tracer._pluginManager?._pluginsByName?.openai?.metrics?.flush?.()

  // does have a callback :)
  const promises = []

  const { profiler } = require('dd-trace/packages/dd-trace/src/profiling/')
  if (profiler?._collect) {
    promises.push(profiler._collect('on_shutdown'))
  }

  if (tracer._tracer?._exporter?._writer?.flush) {
    promises.push(promisify((err: any) => tracer._tracer._exporter._writer.flush(err)))
  }

  if (tracer._pluginManager?._pluginsByName?.openai?.logger?.flush) {
    promises.push(promisify((err: any) => tracer._pluginManager._pluginsByName.openai.logger.flush(err)))
  }

  Promise.all(promises).then(() => {
    res.status(200).send('OK')
  }).catch((err) => {
    res.status(500).send(err)
  })
})

app.get('/requestdownstream', async (req: Request, res: Response) => {
  try {
    const resFetch = await axios.get('http://127.0.0.1:7777/returnheaders')
    return res.json(resFetch.data)
  } catch (e) {
    return res.status(500).send(e)
  }
})

app.get('/returnheaders', (req: Request, res: Response) => {
  res.json({ ...req.headers })
})

app.get('/vulnerablerequestdownstream', async (req: Request, res: Response) => {
  try {
    crypto.createHash('md5').update('password').digest('hex')
    const resFetch = await axios.get('http://127.0.0.1:7777/returnheaders')
    return res.json(resFetch.data)
  } catch (e) {
    return res.status(500).send(e)
  }
})

app.get('/set_cookie', (req: Request, res: Response) => {
  const name = req.query['name']
  const value = req.query['value']

  res.header('Set-Cookie', `${name}=${value}`)
  res.send('OK')
})

require('./rasp')(app)

require('./graphql')(app).then(() => {
  app.listen(7777, '0.0.0.0', () => {
    tracer.trace('init.service', () => {})
    console.log('listening')
  })
})
