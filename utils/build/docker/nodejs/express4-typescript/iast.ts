'use strict'

import type { Express, Request, Response } from 'express'

const crypto = require('crypto')

module.exports = function (app: Express) {
  app.get('/iast/weak_randomness/test_insecure', (req: Request, res: Response) => {
    const randomNumber = Math.random()
    res.send(`OK:${randomNumber}`)
  })

  app.get('/iast/weak_randomness/test_secure', (req: Request, res: Response) => {
    const randomBytes = crypto.randomBytes(256).toString('hex')
    res.send(`OK:${randomBytes}`)
  })
}
