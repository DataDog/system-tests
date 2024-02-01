'use strict'
const { readFileSync } = require('fs')

function init (app, tracer) {
  app.post('/iast/source/body/test', (req, res) => {
    try {
      readFileSync(req.body.name)
    } catch {
      // do nothing
    }
    res.send('OK')
  })

  app.get('/iast/source/headername/test', (req, res) => {
    let vulnParam = ''
    Object.keys(req.headers).forEach((key) => {
      vulnParam += key
    })
    try {
      readFileSync(vulnParam)
    } catch {
      // do nothing
    }
    res.send('OK')
  })

  app.get('/iast/source/header/test', (req, res) => {
    let vulnParam = ''
    Object.keys(req.headers).forEach((key) => {
      vulnParam += req.headers[key]
    })
    try {
      readFileSync(vulnParam)
    } catch {
      // do nothing
    }
    res.send('OK')
  })

  app.get('/iast/source/parametername/test', (req, res) => {
    let vulnParam = ''
    Object.keys(req.query).forEach((key) => {
      vulnParam += key
    })
    try {
      readFileSync(vulnParam)
    } catch {
      // do nothing
    }
    res.send('OK')
  })

  app.post('/iast/source/parameter/test', (req, res) => {
    let vulnParam = ''
    Object.keys(req.body).forEach((key) => {
      vulnParam += req.body[key]
    })
    try {
      readFileSync(vulnParam)
    } catch {
      // do nothing
    }
    res.send('OK')
  })

  app.get('/iast/source/parameter/test', (req, res) => {
    let vulnParam = ''
    Object.keys(req.query).forEach((key) => {
      vulnParam += req.query[key]
    })
    try {
      readFileSync(vulnParam)
    } catch {
      // do nothing
    }
    res.send('OK')
  })

  app.get('/iast/source/cookiename/test', (req, res) => {
    let vulnParam = ''
    Object.keys(req.cookies).forEach((key) => {
      vulnParam += key
    })
    try {
      readFileSync(vulnParam)
    } catch {
      // do nothing
    }
    res.send('OK')
  })

  app.get('/iast/source/cookievalue/test', (req, res) => {
    let vulnParam = ''
    Object.keys(req.cookies).forEach((key) => {
      vulnParam += req.cookies[key]
    })
    try {
      readFileSync(vulnParam)
    } catch {
      // do nothing
    }
    res.send('OK')
  })
}

module.exports = init
