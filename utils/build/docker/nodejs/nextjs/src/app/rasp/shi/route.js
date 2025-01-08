import { NextResponse } from 'next/server'
import { execSync } from 'child_process'

export const dynamic = 'force-dynamic'

export function GET (request) {
  try {
    execSync(request.nextUrl.searchParams.get('list_dir'))
  } catch (e) {
    if (e.name === 'DatadogRaspAbortError') {
      throw e
    }
  }

  return NextResponse.json({}, {
    status: 200
  })
}
