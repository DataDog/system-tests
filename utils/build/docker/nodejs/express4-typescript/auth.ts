'use strict'

import type { Express, Request, Response, NextFunction } from "express";
import type { Tracer } from "dd-trace";
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

module.exports = function (app: Express, passport: any, tracer: Tracer) {
  passport.use(new LocalStrategy({ usernameField: 'username', passwordField: 'password' },
    (username: string, password: string, done: any) => {
      const user = users.find(user => (user.username === username) && (user.password === password))
      if (!user) {
        return done(null, false)
      } else {
        return done(null, user)
      }
    })
  )

  passport.use(new BasicStrategy((username: string, password: string, done: any) => {
    const user = users.find(user => (user.username === username) && (user.password === password))
    if (!user) {
      return done(null, false)
    } else {
      return done(null, user)
    }
  }
  ))

  function handleAuthentication (req: Request, res: Response, next: NextFunction, err: any, user: any, info: any) {
    const event = req.query.sdk_event
    const userId: string = req.query.sdk_user as string || 'sdk_user'
    const userMail = req.query.sdk_mail as  string || 'system_tests_user@system_tests_user.com'
    const exists = req.query.sdk_user_exists === 'true'

    if (err) {
      console.error('unexpected login error', err)
      return next(err)
    }
    if (!user) {
      if (event === 'failure') {
        tracer.appsec.trackUserLoginFailureEvent(userId, exists, { metadata0: "value0", metadata1: "value1" });
      }

      res.sendStatus(401)
    } else if (event === 'success') {
        tracer.appsec.trackUserLoginSuccessEvent(
          {
            id: userId,
            email: userMail,
            name: "system_tests_user"
          },
          {
            metadata0: "value0",
            metadata1: "value1"
          }
        )

        res.sendStatus(200)
      } else {
        res.sendStatus(200)
      }
  }

  function getStrategy (req: Request, res: Response, next: NextFunction) {
    const auth = req.query && req.query.auth
    if (auth === 'local') {
      return passport.authenticate('local', { session: false }, function (err: any, user: any, info: any) {
        handleAuthentication(req, res, next, err, user, info)
      })(req, res, next)
    } else {
      return passport.authenticate('basic', { session: false }, function (err: any, user: any, info: any) {
        handleAuthentication(req, res, next, err, user, info)
      })(req, res, next)
    }
  }


  app.use(passport.initialize())
  app.all('/login',
    getStrategy,
    (req: Request, res: Response, next: NextFunction) => {
      res.sendStatus(200)
    }
  )
}
