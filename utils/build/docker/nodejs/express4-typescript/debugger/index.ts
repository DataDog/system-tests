import type { Express } from 'express'
import { logHandler } from './log_handler'

export function initRoutes (app: Express) {
  app.get('/log', logHandler)
}
