'use strict'

import type { Express, Request, Response } from 'express';

const http = require('http')
function initRaspEndpoints (app: Express) {
    app.get('/rasp/ssrf', (req: Request, res: Response) => {
        const clientRequest = http.get(`http://${req.query.domain}`, () => {
            res.end('end')
        })
        clientRequest.on('error', (e: any) => {
            // TODO when blocking is supported, throw e when is aborted
            //  to check that we are blocking as expected
            res.writeHead(500).end(e.message)
        })
    })

    app.post('/rasp/ssrf', (req: Request, res: Response) => {
        const clientRequest = http.get(`http://${req.body.domain}`, () => {
            res.end('end')
        })
        clientRequest.on('error', (e: any) => {
            // TODO when blocking is supported, throw e when is aborted
            //  to check that we are blocking as expected
            res.writeHead(500).end(e.message)
        })
    })
}
module.exports = initRaspEndpoints
