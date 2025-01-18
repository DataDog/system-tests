'use strict'

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

module.exports = function (app, tracer) {
  app.use(passport.initialize())
  app.use(passport.session())

  passport.serializeUser((user, done) => {
    done(null, user.id)
  })

  passport.deserializeUser((userId, done) => {
    const user = users.find(user => user.id === userId)

    done(null, user)
  })

  passport.use(new LocalStrategy((username, password, done) => {
    const user = users.find(user => user.username === username && user.password === password)

    done(null, user)
  }))

  passport.use(new BasicStrategy((username, password, done) => {
    const user = users.find(user => user.username === username && user.password === password)

    done(null, user)
  }))

  // rewrite url depending on which strategy to use
  app.all('/login', (req, res, next) => {
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

  app.use('/login/local', passport.authenticate('local', { failWithError: true }), handleError)
  app.use('/login/basic', passport.authenticate('basic', { failWithError: true }), handleError)

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
  app.all('/login/*', (req, res) => {
    const event = req.query.sdk_event
    const userId = req.query.sdk_user || 'sdk_user'
    const userMail = req.query.sdk_mail || 'system_tests_user@system_tests_user.com'
    const exists = req.query.sdk_user_exists === 'true'

    let statusCode = req.user ? 200 : 401

    if (event === 'failure') {
      tracer.appsec.trackUserLoginFailureEvent(userId, exists, { metadata0: 'value0', metadata1: 'value1' })

      statusCode = 401
    } else if (event === 'success') {
      const sdkUser = {
        id: userId,
        email: userMail,
        name: 'system_tests_user'
      }

      tracer.appsec.trackUserLoginSuccessEvent(sdkUser, { metadata0: 'value0', metadata1: 'value1' })

      const isUserBlocked = tracer.appsec.isUserBlocked(sdkUser)
      if (isUserBlocked && tracer.appsec.blockRequest(req, res)) {
        return
      }

      statusCode = 200
    }

    res.sendStatus(statusCode)
  })
}
