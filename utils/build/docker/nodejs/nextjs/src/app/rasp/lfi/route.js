import { NextResponse } from 'next/server'
import { statSync } from 'fs'

export const dynamic = 'force-dynamic'

export function GET (request) {
  try {
    statSync(request.nextUrl.searchParams.get('file'))
  } catch (e) {
    if (e.name === 'DatadogRaspAbortError') {
      throw e
    }
  }

  return NextResponse.json({}, {
    status: 200
  })
}
