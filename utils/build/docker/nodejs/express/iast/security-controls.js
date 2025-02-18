'use strict'

const { Client } = require('pg')
const { execSync } = require('child_process')
const SecurityControlUtil = require('./utils/securityControlUtil')

function execQuery (user, password) {
  const sql = 'SELECT * FROM IAST_USER WHERE USERNAME = \'' + user +
    '\' AND PASSWORD = \'' + password + '\''

  const client = new Client()
  return client.connect().then(() => {
    return client.query(sql)
  })
}

function init (app, tracer) {
  app.post('/iast/sc/s/configured', (req, res) => {
    const sanitized = SecurityControlUtil.sanitize(req.body.param)
    try {
      execSync(sanitized)
    } catch (e) {
      // ignore
    }
    res.send('OK')
  })

  app.post('/iast/sc/s/not-configured', (req, res) => {
    const sanitized = SecurityControlUtil.sanitize(req.body.param)
    execQuery(sanitized, 'password').then((queryResult) => {
      res.send('OK')
    }).catch((err) => {
      res.send('Error: ' + err)
    })
  })

  app.post('/iast/sc/s/all', (req, res) => {
    const sanitized = SecurityControlUtil.sanitizeForAllVulns(req.body.param)
    execQuery(sanitized, 'password').then((queryResult) => {
      res.send('OK')
    }).catch((err) => {
      res.send('Error: ' + err)
    })
  })

  app.post('/iast/sc/s/overloaded/secure', (req, res) => {
    const sanitized = SecurityControlUtil.overloadedSanitize(req.body.param)
    try {
      execSync(sanitized)
    } catch (e) {
      // ignore
    }
    res.send('OK')
  })

  app.post('/iast/sc/s/overloaded/insecure', (req, res) => {
    const sanitized = SecurityControlUtil.overloadedSanitize(null, req.body.param)
    try {
      execSync(sanitized)
    } catch (e) {
      // ignore
    }
    res.send('OK')
  })

  app.post('/iast/sc/iv/configured', (req, res) => {
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

  app.post('/iast/sc/iv/not-configured', (req, res) => {
    if (SecurityControlUtil.validate(req.body.param)) {
      execQuery(req.body.param, 'password').then((queryResult) => {
        res.send('OK')
      }).catch((err) => {
        res.send('Error: ' + err)
      })
    }
  })

  app.post('/iast/sc/iv/all', (req, res) => {
    if (SecurityControlUtil.validateForAllVulns(req.body.param)) {
      execQuery(req.body.param, 'password').then((queryResult) => {
        res.send('OK')
      }).catch((err) => {
        res.send('Error: ' + err)
      })
    }
  })

  app.post('/iast/sc/iv/overloaded/secure', (req, res) => {
    const { user, password } = req.body
    if (SecurityControlUtil.overloadedValidation(null, user, password)) {
      execQuery(user, password).then((queryResult) => {
        res.send('OK')
      }).catch((err) => {
        res.send('Error: ' + err)
      })
    }
  })

  app.post('/iast/sc/iv/overloaded/insecure', (req, res) => {
    const { user, password } = req.body
    if (SecurityControlUtil.overloadedValidation(user, password, null)) {
      execQuery(user, password).then((queryResult) => {
        res.send('OK')
      }).catch((err) => {
        res.send('Error: ' + err)
      })
    }
  })
}

module.exports = init
