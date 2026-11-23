import { NextResponse } from 'next/server'
import pg from 'pg'
import { getParam } from '../getParam'

export const dynamic = 'force-dynamic'

const pool = new pg.Pool()

async function handler (request) {
  const userId = await getParam(request, 'user_id')

  try {
    await pool.query(`SELECT * FROM users WHERE id='${userId}'`)
  } catch (e) {
    if (e.name === 'DatadogRaspAbortError') {
      throw e
    }
  }

  return NextResponse.json({}, {
    status: 200
  })
}

export { handler as GET, handler as POST }
