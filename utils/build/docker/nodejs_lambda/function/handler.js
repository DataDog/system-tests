'use strict'

const http = require('http')
const { URL } = require('url')
const querystring = require('querystring')

const LAMBDA_EVENT_TYPE = process.env.SYSTEM_TEST_WEBLOG_LAMBDA_EVENT_TYPE || 'apigateway-rest'
const TRACK_CUSTOM_APPSEC_EVENT_NAME = 'system_tests_appsec_event'
const TRACK_USER = 'system_tests_user'
const MAGIC_SESSION_KEY = 'random_session_id'

function getTracer () {
  try {
    return require('dd-trace')
  } catch (e) {
    console.error('Failed to load dd-trace:', e.message)
    return undefined
  }
}

function getDatadogLambdaVersion () {
  const paths = [
    '/opt/nodejs/node_modules/datadog-lambda-js/package.json',
    'datadog-lambda-js/package.json'
  ]
  for (const p of paths) {
    try {
      return require(p).version
    } catch (e) { /* try next */ }
  }
  // Return a valid semver fallback so the test framework can parse it
  return '0.0.0'
}

function versionInfo () {
  return {
    status: 'ok',
    library: {
      name: 'nodejs_lambda',
      version: getDatadogLambdaVersion()
    }
  }
}

function parseEvent (event) {
  if (LAMBDA_EVENT_TYPE === 'apigateway-rest') {
    return {
      path: event.path || '/',
      method: event.httpMethod || 'GET',
      headers: event.headers || {},
      queryStringParameters: event.queryStringParameters || {},
      multiValueQueryStringParameters: event.multiValueQueryStringParameters || {},
      body: event.body || null
    }
  }

  if (LAMBDA_EVENT_TYPE === 'apigateway-http' || LAMBDA_EVENT_TYPE === 'function-url') {
    const rc = event.requestContext || {}
    const httpInfo = rc.http || {}
    return {
      path: event.rawPath || '/',
      method: httpInfo.method || 'GET',
      headers: event.headers || {},
      queryStringParameters: event.queryStringParameters || {},
      multiValueQueryStringParameters: {},
      body: event.body || null
    }
  }

  if (LAMBDA_EVENT_TYPE === 'application-load-balancer' || LAMBDA_EVENT_TYPE === 'application-load-balancer-multi') {
    return {
      path: event.path || '/',
      method: event.httpMethod || 'GET',
      headers: event.headers || {},
      queryStringParameters: event.queryStringParameters || {},
      multiValueQueryStringParameters: event.multiValueQueryStringParameters || {},
      body: event.body || null
    }
  }

  return {
    path: event.path || event.rawPath || '/',
    method: event.httpMethod || (event.requestContext && event.requestContext.http && event.requestContext.http.method) || 'GET',
    headers: event.headers || {},
    queryStringParameters: event.queryStringParameters || {},
    multiValueQueryStringParameters: event.multiValueQueryStringParameters || {},
    body: event.body || null
  }
}

function getQueryParam (parsed, key) {
  if (parsed.queryStringParameters && parsed.queryStringParameters[key]) {
    return parsed.queryStringParameters[key]
  }
  const mv = parsed.multiValueQueryStringParameters
  if (mv && mv[key] && mv[key].length > 0) {
    return mv[key][0]
  }
  return undefined
}

function getQueryParams (parsed) {
  const params = {}
  if (parsed.queryStringParameters) {
    for (const [k, v] of Object.entries(parsed.queryStringParameters)) {
      params[k] = v
    }
  } else if (parsed.multiValueQueryStringParameters) {
    for (const [k, v] of Object.entries(parsed.multiValueQueryStringParameters)) {
      params[k] = Array.isArray(v) ? v[0] : v
    }
  }
  return params
}

function retrieveArg (key, parsed) {
  if (parsed.method === 'GET') {
    return getQueryParam(parsed, key)
  }

  if (parsed.method === 'POST' && parsed.body) {
    const body = parsed.body

    try {
      const formData = querystring.parse(body)
      if (formData[key]) return formData[key]
    } catch (e) { /* ignore */ }

    try {
      const jsonData = JSON.parse(body)
      if (typeof jsonData === 'object' && jsonData !== null && jsonData[key] !== undefined) {
        return jsonData[key]
      }
    } catch (e) { /* ignore */ }

    try {
      // Basic XML value extraction: <key>value</key>
      const match = body.match(new RegExp(`<${key}>([^<]*)</${key}>`))
      if (match) return match[1]
    } catch (e) { /* ignore */ }
  }

  return undefined
}

function createResponse (statusCode, body, headers) {
  const responseHeaders = headers || {}

  if (LAMBDA_EVENT_TYPE === 'apigateway-http' || LAMBDA_EVENT_TYPE === 'function-url') {
    return {
      statusCode,
      headers: responseHeaders,
      body: typeof body === 'object' ? JSON.stringify(body) : body
    }
  }

  return {
    statusCode,
    headers: responseHeaders,
    body: typeof body === 'object' ? JSON.stringify(body) : body
  }
}

function createResponseWithCookies (statusCode, body, headers, cookies) {
  const responseHeaders = headers || {}

  if (LAMBDA_EVENT_TYPE === 'apigateway-http' || LAMBDA_EVENT_TYPE === 'function-url') {
    return {
      statusCode,
      headers: responseHeaders,
      cookies: cookies || [],
      body: typeof body === 'object' ? JSON.stringify(body) : body
    }
  }

  const multiValueHeaders = {}
  if (cookies && cookies.length > 0) {
    multiValueHeaders['Set-Cookie'] = cookies
  }

  return {
    statusCode,
    headers: responseHeaders,
    multiValueHeaders,
    body: typeof body === 'object' ? JSON.stringify(body) : body
  }
}

function matchRoute (path) {
  if (path === '/' || path === '') return { route: 'root' }
  if (path === '/headers') return { route: 'headers' }
  if (path === '/healthcheck') return { route: 'healthcheck' }
  if (path === '/session/new') return { route: 'session_new' }
  if (path === '/user_login_success_event') return { route: 'user_login_success_event' }
  if (path === '/external_request') return { route: 'external_request' }
  if (path === '/users') return { route: 'users' }

  const tagValueMatch = path.match(/^\/tag_value\/([^/]+)\/(\d+)$/)
  if (tagValueMatch) {
    return { route: 'tag_value', tagValue: tagValueMatch[1], statusCode: parseInt(tagValueMatch[2], 10) }
  }

  if (path.startsWith('/params/') || path === '/waf' || path === '/waf/' || path.startsWith('/waf/')) {
    return { route: 'waf_params' }
  }

  return { route: 'not_found' }
}

function handleRoot () {
  return createResponse(200, 'Hello, World!\n')
}

function handleHeaders () {
  return createResponse(200, 'OK', { 'Content-Language': 'en-US' })
}

function handleHealthcheck () {
  return createResponse(200, JSON.stringify(versionInfo()), { 'Content-Type': 'application/json' })
}

function handleWafParams () {
  return createResponse(200, 'Hello, World!\n')
}

function handleSessionNew () {
  return createResponseWithCookies(
    200,
    MAGIC_SESSION_KEY,
    {},
    [`session_id=${MAGIC_SESSION_KEY}; Path=/; HttpOnly`]
  )
}

function handleTagValue (tagValue, statusCode, parsed) {
  const tracer = getTracer()
  if (tracer?.appsec) {
    tracer.appsec.trackCustomEvent(TRACK_CUSTOM_APPSEC_EVENT_NAME, { value: tagValue })
  }

  const responseHeaders = {}
  if (parsed.queryStringParameters) {
    for (const [k, v] of Object.entries(parsed.queryStringParameters)) {
      responseHeaders[k] = v
    }
  }

  if (parsed.method === 'POST' && tagValue.startsWith('payload_in_response_body')) {
    const formData = parsed.body ? querystring.parse(parsed.body) : {}
    return createResponse(statusCode, JSON.stringify({ payload: formData }), {
      ...responseHeaders,
      'Content-Type': 'application/json'
    })
  }

  return createResponse(statusCode, 'Value tagged', responseHeaders)
}

function handleUserLoginSuccessEvent () {
  const tracer = getTracer()
  if (tracer?.appsec) {
    tracer.appsec.trackUserLoginSuccessEvent(
      { id: TRACK_USER, login: TRACK_USER, name: TRACK_USER },
      { metadata0: 'value0', metadata1: 'value1' }
    )
  }
  return createResponse(200, 'OK')
}

function handleExternalRequest (parsed) {
  const params = getQueryParams(parsed)
  const body = parsed.body || null

  if (body) {
    const contentType = parsed.headers['content-type'] || parsed.headers['Content-Type'] || 'application/json'
    params['Content-Type'] = contentType
  }

  const status = params.status || '200'
  const urlExtra = params.url_extra || ''
  delete params.status
  delete params.url_extra

  const fullUrl = `http://internal_server:8089/mirror/${status}${urlExtra}`
  const method = parsed.method

  return new Promise((resolve) => {
    const parsedUrl = new URL(fullUrl)
    const options = {
      hostname: parsedUrl.hostname,
      port: parsedUrl.port || 8089,
      path: parsedUrl.pathname + parsedUrl.search,
      method,
      headers: params
    }

    const req = http.request(options, (res) => {
      let responseBody = ''
      res.on('data', (chunk) => { responseBody += chunk })
      res.on('end', () => {
        let payload
        try {
          payload = JSON.parse(responseBody)
        } catch (e) {
          payload = responseBody
        }
        resolve(createResponse(200, JSON.stringify({
          status: res.statusCode,
          headers: res.headers,
          payload
        }), { 'Content-Type': 'application/json' }))
      })
    })

    req.on('error', (e) => {
      resolve(createResponse(500, JSON.stringify({ error: e.message }), { 'Content-Type': 'application/json' }))
    })

    if (body) req.write(body)
    req.end()
  })
}

function handleUsers (parsed) {
  const user = getQueryParam(parsed, 'user')
  const tracer = getTracer()
  if (tracer && user) {
    tracer.setUser({
      id: user,
      email: 'usr.email',
      name: 'usr.name',
      session_id: 'usr.session_id',
      role: 'usr.role',
      scope: 'usr.scope'
    })
  }
  return createResponse(200, 'Ok')
}

exports.handler = function handler (event, context) {
  if (event.healthcheck) {
    return versionInfo()
  }

  const parsed = parseEvent(event)
  const matched = matchRoute(parsed.path)

  switch (matched.route) {
    case 'root':
      return handleRoot()
    case 'headers':
      return handleHeaders()
    case 'healthcheck':
      return handleHealthcheck()
    case 'waf_params':
      return handleWafParams()
    case 'session_new':
      return handleSessionNew()
    case 'tag_value':
      return handleTagValue(matched.tagValue, matched.statusCode, parsed)
    case 'user_login_success_event':
      return handleUserLoginSuccessEvent()
    case 'external_request':
      return handleExternalRequest(parsed)
    case 'users':
      return handleUsers(parsed)
    default:
      return createResponse(404, 'Not Found')
  }
}
