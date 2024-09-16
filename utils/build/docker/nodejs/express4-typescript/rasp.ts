'use strict'

import type { Express, Request, Response } from 'express';

const http = require('http')
const pg = require('pg')

function initRaspEndpoints (app: Express) {
    const pool = new pg.Pool()

    app.get('/rasp/ssrf', (req: Request, res: Response) => {
        const clientRequest = http.get(`http://${req.query.domain}`, () => {
            res.end('end')
        })
        clientRequest.on('error', (e: any) => {
            if (e.name === 'DatadogRaspAbortError') {
                throw e
            }
            res.writeHead(500).end(e.message)
        })
    })

    app.post('/rasp/ssrf', (req: Request, res: Response) => {
        const clientRequest = http.get(`http://${req.body.domain}`, () => {
            res.end('end')
        })
        clientRequest.on('error', (e: any) => {
            if (e.name === 'DatadogRaspAbortError') {
                throw e
            }
            res.writeHead(500).end(e.message)
        })
    })

    app.get('/rasp/sqli', async (req: Request, res: Response) => {
        try {
            await pool.query(`SELECT * FROM users WHERE id='${req.query.user_id}'`)
        } catch (e: any) {
            if (e.name === 'DatadogRaspAbortError') {
                throw e
            }

            res.writeHead(500).end(e.message)
            return
        }

        res.end('end')
    })

    app.post('/rasp/sqli', async (req: Request, res: Response) => {
        try {
            await pool.query(`SELECT * FROM users WHERE id='${req.body.user_id}'`)
        } catch (e: any) {
            if (e.name === 'DatadogRaspAbortError') {
                throw e
            }

            res.writeHead(500).end(e.message)
            return
        }

        res.end('end')
    })
}
module.exports = initRaspEndpoints
