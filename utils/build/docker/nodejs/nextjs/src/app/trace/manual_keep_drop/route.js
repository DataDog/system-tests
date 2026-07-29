import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

export async function GET (request) {
  const decision = request.nextUrl.searchParams.get('decision')

  if (decision !== 'keep' && decision !== 'drop') {
    return new NextResponse('decision must be keep or drop', { status: 400 })
  }

  const tracer = global._ddtrace
  tracer?.scope().active()?.setTag(decision === 'keep' ? 'manual.keep' : 'manual.drop', true)

  return new NextResponse('OK')
}
