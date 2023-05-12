'use strict'
const { execSync } = require('child_process')

function init (app, tracer) {
    
    app.post('/iast/source/body/test', (req, res) => {
        execSync('ls #' + req.body.name)
        res.send('OK')
    });

    app.get('/iast/source/headername/test', (req, res) => {
        let vulnParam = ''
        Object.keys(req.headers).forEach((key) => {
            vulnParam += key
        })
        execSync('ls #' + vulnParam)
        res.send('OK')
    });

    app.get('/iast/source/header/test', (req, res) => {
        let vulnParam = ''
        Object.keys(req.headers).forEach((key) => {
            vulnParam += req.headers[key]
        })
        execSync('ls #' + vulnParam)
        res.send('OK')
    });

    app.get('/iast/source/parametername/test', (req, res) => {
        let vulnParam = ''
        Object.keys(req.query).forEach((key) => {
            vulnParam += key
        })
        execSync('ls #' + vulnParam)
        res.send('OK')
    });

    app.post('/iast/source/parameter/test', (req, res) => {
        let vulnParam = ''
        Object.keys(req.body).forEach((key) => {
            vulnParam += req.body[key]
        })
        execSync('ls #' + vulnParam)
        res.send('OK')
    });

    app.get('/iast/source/parameter/test', (req, res) => {
        let vulnParam = ''
        Object.keys(req.query).forEach((key) => {
            vulnParam += req.query[key]
        })
        execSync('ls #' + vulnParam)
        res.send('OK')
    });

    app.get('/iast/source/cookiename/test', (req, res) => {
        let vulnParam = ''
        console.log('req.cookies', req.query)
        Object.keys(req.cookies).forEach((key) => {
            vulnParam += key
        })
        console.log('vulnParam', vulnParam)
        execSync('ls #' + vulnParam)
        res.send('OK')
    });

    app.get('/iast/source/cookievalue/test', (req, res) => {
        let vulnParam = ''
        console.log('req.cookies', req.query)
        Object.keys(req.cookies).forEach((key) => {
            vulnParam += req.cookies[key]
        })
        console.log('vulnParam', vulnParam)
        execSync('ls #' + vulnParam)
        res.send('OK')
    });
}

module.exports = init