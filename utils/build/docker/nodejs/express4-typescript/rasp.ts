'use strict'

import http from 'node:http';

import type { Express, NextFunction, Request, Response } from 'express';

const pg = require('pg')
const { statSync } = require('fs')
const { execFileSync, execSync } = require('child_process')

function initRaspEndpoints (app: Express) {
    const pool = new pg.Pool()

    app.get('/rasp/ssrf', (req: Request, res: Response, next: NextFunction) => {
        const clientRequest = http.get(`http://${req.query.domain}`, (response) => {
            response.resume()
            res.end('end')
        })
        clientRequest.on('error', (error: Error) => {
            if (error.name === 'DatadogRaspAbortError') {
                return next(error)
            }
            res.writeHead(500).end(error.message)
        })
    })

    app.post('/rasp/ssrf', (req: Request, res: Response, next: NextFunction) => {
        const clientRequest = http.get(`http://${req.body.domain}`, (response) => {
            response.resume()
            res.end('end')
        })
        clientRequest.on('error', (error: Error) => {
            if (error.name === 'DatadogRaspAbortError') {
                return next(error)
            }
            res.writeHead(500).end(error.message)
        })
    })

    app.get('/rasp/sqli', async (req: Request, res: Response, next: NextFunction) => {
        try {
            await pool.query(`SELECT * FROM users WHERE id='${req.query.user_id}'`)
        } catch (e: any) {
            if (e.name === 'DatadogRaspAbortError') {
                return next(e)
            }

            res.writeHead(500).end(e.message)
            return
        }

        res.end('end')
    })

    app.post('/rasp/sqli', async (req: Request, res: Response, next: NextFunction) => {
        try {
            await pool.query(`SELECT * FROM users WHERE id='${req.body.user_id}'`)
        } catch (e: any) {
            if (e.name === 'DatadogRaspAbortError') {
                return next(e)
            }

            res.writeHead(500).end(e.message)
            return
        }

        res.end('end')
    })

    app.get('/rasp/lfi', (req: Request, res: Response) => {
        let result
        try {
            result = JSON.stringify(statSync(req.query.file))
        } catch (e: any) {
            result = e.toString()

            if (e.name === 'DatadogRaspAbortError') {
                throw e
            }
        }

        res.send(result)
    })

    app.post('/rasp/lfi', (req: Request, res: Response) => {
        let result
        try {
            result = JSON.stringify(statSync(req.body.file))
        } catch (e: any) {
            result = e.toString()

            if (e.name === 'DatadogRaspAbortError') {
                throw e
            }
        }

        res.send(result)
    })

    app.get('/rasp/shi', (req: Request, res: Response) => {
        let result
        try {
            result = execSync(`ls ${req.query.list_dir}`)
        } catch (e: any) {
            result = e.toString()

            if (e.name === 'DatadogRaspAbortError') {
                throw e
            }
        }

        res.send(result)
    })

    app.post('/rasp/shi', (req: Request, res: Response) => {
        let result
        try {
            result = execSync(`ls ${req.body.list_dir}`)
        } catch (e: any) {
            result = e.toString()

            if (e.name === 'DatadogRaspAbortError') {
                throw e
            }
        }

        res.send(result)
    })

    app.get('/rasp/cmdi', (req: Request, res: Response) => {
        let result
        try {
            result = execFileSync(req.query.command)
        } catch (e: any) {
            result = e.toString()

            if (e.name === 'DatadogRaspAbortError') {
                throw e
            }
        }

        res.send(result)
    })

    app.post('/rasp/cmdi', (req: Request, res: Response) => {
        let result
        try {
            result = execFileSync(req.body.command)
        } catch (e: any) {
            result = e.toString()

            if (e.name === 'DatadogRaspAbortError') {
                throw e
            }
        }

        res.send(result)
    })

    app.get('/rasp/multiple', (req: Request, res: Response) => {
        try {
            statSync(req.query.file1)
        } catch (e: any) {}

        try {
            statSync(req.query.file2)
        } catch (e: any) {}

        try {
            statSync('../etc/passwd')
        } catch (e: any) {}

        res.send('OK')
    })
}

module.exports = initRaspEndpoints
