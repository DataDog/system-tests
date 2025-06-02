'use strict'

const tracer = require('dd-trace').init({
  debug: true,
  flushInterval: 5000
})

const { promisify } = require('util')
const fastify = require('fastify')({ logger: true })
const axios = require('axios')
const crypto = require('crypto')

// Register Fastify plugins for parsing
fastify.register(require('@fastify/formbody'))

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
  request.session.someData = 'blabla' // needed for the session to be saved
  return request.session.sessionId
})

fastify.get('/status', async (request, reply) => {
  reply.status(parseInt(request.query.code))
  return 'OK'
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



const graphQLEnabled = false;
const initGraphQL = () => {
  return graphQLEnabled
    ? require('./graphql')(fastify)
    : Promise.resolve()
}

initGraphQL()
  .then(startServer)
  .catch(error => {
    console.error('Failed to start server:', error)
    process.exit(1)
  }) 
