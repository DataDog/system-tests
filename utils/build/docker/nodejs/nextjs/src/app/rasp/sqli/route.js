import { NextResponse } from 'next/server'
import pg from 'pg'

export const dynamic = 'force-dynamic'

const pool = new pg.Pool()

export async function GET (request) {
  try {
    await pool.query(`SELECT * FROM users WHERE id='${request.nextUrl.searchParams.get('user_id')}'`)
  } catch (e) {
    if (e.name === 'DatadogRaspAbortError') {
      throw e
    }
  }

  return NextResponse.json({}, {
    status: 200
  })
}
