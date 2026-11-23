import { NextResponse } from 'next/server'
import { execFileSync } from 'child_process'
import { getParam } from '../getParam'

export const dynamic = 'force-dynamic'

async function handler (request) {
  const command = await getParam(request, 'command')

  try {
    execFileSync(command)
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
