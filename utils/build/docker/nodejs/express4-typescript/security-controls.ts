'use strict'

import type { Express, NextFunction, Request, Response } from 'express'
const { Client } = require('pg')
const { execSync } = require('child_process')
const SecurityControlUtil = require('./utils/securityControlUtil')

function execQuery (user: string, password: string) {
  const sql = 'SELECT * FROM IAST_USER WHERE USERNAME = \'' + user +
    '\' AND PASSWORD = \'' + password + '\''

  const client = new Client()
  return client.connect().then(() => {
    return client.query(sql)
  })
}

function initSecurityControls (app: Express) {
  app.post('/iast/sc/s/configured', (req: Request, res: Response): void => {
    const sanitized = SecurityControlUtil.sanitize(req.body.param)
    try {
      execSync(sanitized)
    } catch (e) {
      // ignore
    }
    res.send('OK')
  })

  app.post('/iast/sc/s/not-configured', (req: Request, res: Response): void => {
    const sanitized = SecurityControlUtil.sanitize(req.body.param)
    execQuery(sanitized, 'password').then((queryResult: any) => {
      res.send('OK')
    }).catch((err: Error) => {
      res.send('Error: ' + err)
    })
  })

  app.post('/iast/sc/s/all', (req: Request, res: Response): void => {
    const sanitized = SecurityControlUtil.sanitizeForAllVulns(req.body.param)
    execQuery(sanitized, 'password').then((queryResult: any) => {
      res.send('OK')
    }).catch((err: Error) => {
      res.send('Error: ' + err)
    })
  })

  app.post('/iast/sc/s/overloaded/secure', (req: Request, res: Response): void => {
    const sanitized = SecurityControlUtil.overloadedSanitize(req.body.param)
    try {
      execSync(sanitized)
    } catch (e) {
      // ignore
    }
    res.send('OK')
  })

  app.post('/iast/sc/s/overloaded/insecure', (req: Request, res: Response): void => {
    const sanitized = SecurityControlUtil.overloadedSanitize(null, req.body.param)
    try {
      execSync(sanitized)
    } catch (e) {
      // ignore
    }
    res.send('OK')
  })

  app.post('/iast/sc/iv/configured', (req: Request, res: Response): void => {
    // TODO: problem in express5?
    if (SecurityControlUtil.validate(req.body.param)) {
      try {
        execSync(req.body.param)
      } catch (e) {
        // ignore
      }
    }
    res.send('OK')
  })

  app.post('/iast/sc/iv/not-configured', (req: Request, res: Response): void => {
    if (SecurityControlUtil.validate(req.body.param)) {
      execQuery(req.body.param, 'password').then((queryResult: any) => {
        res.send('OK')
      }).catch((err: Error) => {
        res.send('Error: ' + err)
      })
    }
  })

  app.post('/iast/sc/iv/all', (req: Request, res: Response): void => {
    if (SecurityControlUtil.validateForAllVulns(req.body.param)) {
      execQuery(req.body.param, 'password').then((queryResult: any) => {
        res.send('OK')
      }).catch((err: Error) => {
        res.send('Error: ' + err)
      })
    }
  })

  app.post('/iast/sc/iv/overloaded/secure', (req: Request, res: Response): void => {
    const { user, password } = req.body
    if (SecurityControlUtil.overloadedValidation(null, user, password)) {
      execQuery(user, password).then((queryResult: any) => {
        res.send('OK')
      }).catch((err: Error) => {
        res.send('Error: ' + err)
      })
    }
  })

  app.post('/iast/sc/iv/overloaded/insecure', (req: Request, res: Response): void => {
    const { user, password } = req.body
    if (SecurityControlUtil.overloadedValidation(user, password, null)) {
      execQuery(user, password).then((queryResult: any) => {
        res.send('OK')
      }).catch((err: Error) => {
        res.send('Error: ' + err)
      })
    }
  })
}

module.exports = initSecurityControls
