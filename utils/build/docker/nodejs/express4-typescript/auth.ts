'use strict'

import type { Express, Request, Response, NextFunction } from "express";
 // @ts-ignore
import type { Tracer } from "dd-trace";

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

function findUser (fields: {[key: string]: string}) : any {
  return users.find((user) => {
    return Object.entries(fields).every(([field, value]) => user[field] === value)
  })
}

module.exports = function (app: Express, tracer: Tracer) {
  function shouldSdkBlock (req: Request, res: Response) : boolean {
      const event = req.query.sdk_event
      const userId: string = req.query.sdk_user as string || 'sdk_user'
      const userMail = req.query.sdk_mail as  string || 'system_tests_user@system_tests_user.com'
      const exists = req.query.sdk_user_exists === 'true'

    res.statusCode = req.user ? 200 : 401

    if (event === 'failure') {
      tracer.appsec.trackUserLoginFailureEvent(userId, exists, { metadata0: "value0", metadata1: "value1" });

      res.statusCode = 401
    } else if (event === 'success') {
      const sdkUser = {
        id: userId,
        email: userMail,
        name: "system_tests_user"
      }

      tracer.appsec.trackUserLoginSuccessEvent(sdkUser, { metadata0: "value0", metadata1: "value1" })

      const isUserBlocked: boolean = tracer.appsec.isUserBlocked(sdkUser)
      if (isUserBlocked && tracer.appsec.blockRequest(req, res)) {
        return true
      }

      res.statusCode = 200
    }
  }

  app.use(passport.initialize())
  app.use(passport.session())

  passport.serializeUser((user: object, done: Function) => {
    done(null, user.id)
  })

  passport.deserializeUser((id: string, done: Function) => {
    const user: any = findUser({ id })

    done(null, user)
  })

  passport.use(new LocalStrategy((username: string, password: string, done: Function) => {
    const user: any = findUser({ username, password })

    done(null, user)
  }))

  passport.use(new BasicStrategy((username: string, password: string, done: Function) => {
    const user = findUser({ username, password })

    done(null, user)
  }))

  // rewrite url depending on which strategy to use
  app.all('/login', (req: Request, res: Response, next: NextFunction) => {
    if (req.query.sdk_trigger === 'before' && shouldSdkBlock(req, res)) {
      return
    }

    let newRoute: string = ''

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
  function handleError (err: any, req: Request, res: Response, next: NextFunction) : void {
    if (err?.name !== 'AuthenticationError') {
      console.error('unexpected login error', err)
      next(err)
    } else {
      next()
    }
  }

  // callback for all strategies to run SDK
  app.all('/login/*', (req: Request, res: Response) => {
    if (req.query.sdk_trigger !== 'before' && shouldSdkBlock(req, res)) {
      return
    }

    res.sendStatus(res.statusCode || 200)
  })
}
