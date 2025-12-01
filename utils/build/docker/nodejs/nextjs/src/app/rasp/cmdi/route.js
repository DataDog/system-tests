import { NextResponse } from 'next/server'
import { execFileSync } from 'child_process'

export const dynamic = 'force-dynamic'

export function GET (request) {
  try {
    execFileSync(request.nextUrl.searchParams.get('command'))
  } catch (e) {
    if (e.name === 'DatadogRaspAbortError') {
      throw e
    }
  }

  return NextResponse.json({}, {
    status: 200
  })
}
