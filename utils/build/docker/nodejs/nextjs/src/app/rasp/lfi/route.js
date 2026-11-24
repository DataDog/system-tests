import { NextResponse } from 'next/server'
import { statSync } from 'fs'
import { getParam } from '../getParam'

export const dynamic = 'force-dynamic'

async function handler (request) {
  const file = await getParam(request, 'file')

  try {
    statSync(file)
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
