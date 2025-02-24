'use strict'

const semver = require('semver')
const libraryVersion = require('dd-trace/package.json').version

const shouldUseSession = semver.satisfies(libraryVersion, '>=5.35.0', { includePrerelease: true })

const passport = require('passport')
const { Strategy: LocalStrategy } = require('passport-local')
const { BasicStrategy } = require('passport-http')

const users = [
  {
    id: 'social-security-id',
    username: 'test',
    password: '1234',
    email: 'testuser@ddog.com'
  },
  {
    id: '591dc126-8431-4d0f-9509-b23318d3dce4',
    username: 'testuuid',
    password: '1234',
    email: 'testuseruuid@ddog.com'
  }
]

function findUser (fields) {
  return users.find((user) => {
    return Object.entries(fields).every(([field, value]) => user[field] === value)
  })
}

module.exports = function (app, tracer) {
  function shouldSdkBlock (req, res) {
    const event = req.query.sdk_event
    const userId = req.query.sdk_user || 'sdk_user'
    const userMail = req.query.sdk_mail || 'system_tests_user@system_tests_user.com'
    const exists = req.query.sdk_user_exists === 'true'

    res.statusCode = req.user ? 200 : 401

    if (event === 'failure') {
      tracer.appsec.trackUserLoginFailureEvent(userId, exists, { metadata0: 'value0', metadata1: 'value1' })

      res.statusCode = 401
    } else if (event === 'success') {
      const sdkUser = {
        id: userId,
        email: userMail,
        name: 'system_tests_user'
      }

      tracer.appsec.trackUserLoginSuccessEvent(sdkUser, { metadata0: 'value0', metadata1: 'value1' })

      const isUserBlocked = tracer.appsec.isUserBlocked(sdkUser)
      if (isUserBlocked && tracer.appsec.blockRequest(req, res)) {
        return true
      }

      res.statusCode = 200
    }
  }

  app.use(passport.initialize())

  if (shouldUseSession) {
    app.use(require('express-session')({
      secret: 'secret',
      resave: false,
      rolling: true,
      saveUninitialized: false
    }))

    app.use(passport.session())
  }

  passport.serializeUser((user, done) => {
    done(null, user.id)
  })

  passport.deserializeUser((id, done) => {
    const user = findUser({ id })

    done(null, user)
  })

  passport.use(new LocalStrategy((username, password, done) => {
    const user = findUser({ username, password })

    done(null, user)
  }))

  passport.use(new BasicStrategy((username, password, done) => {
    const user = findUser({ username, password })

    done(null, user)
  }))

  // rewrite url depending on which strategy to use
  app.all('/login', (req, res, next) => {
    if (req.query.sdk_trigger === 'before' && shouldSdkBlock(req, res)) {
      return
    }

    let newRoute

    switch (req.query?.auth) {
      case 'basic':
        newRoute = '/login/basic'
        break

      case 'local':
      default:
        newRoute = '/login/local'
    }

    req.url = req.url.replace('/login', newRoute)

    next()
  })

  app.use('/login/local', passport.authenticate('local', {
    session: shouldUseSession,
    failWithError: true
  }), handleError)
  app.use('/login/basic', passport.authenticate('basic', {
    session: shouldUseSession,
    failWithError: true
  }), handleError)

  // only stop if unexpected error
  function handleError (err, req, res, next) {
    if (err?.name !== 'AuthenticationError') {
      console.error('unexpected login error', err)
      next(err)
    } else {
      next()
    }
  }

  // callback for all strategies to run SDK
  // regex is required to be compatible with both express v4 and v5
  app.all(/^\/login\/.*$/i, (req, res) => {
    if (req.query.sdk_trigger !== 'before' && shouldSdkBlock(req, res)) {
      return
    }

    res.sendStatus(res.statusCode || 200)
  })
}
