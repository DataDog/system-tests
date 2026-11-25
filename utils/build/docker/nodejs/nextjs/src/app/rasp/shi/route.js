import { NextResponse } from 'next/server'
import { execSync } from 'child_process'
import { getParam } from '../getParam'

export const dynamic = 'force-dynamic'

async function handler (request) {
  const listDir = await getParam(request, 'list_dir')

  try {
    execSync(`ls ${listDir}`)
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
