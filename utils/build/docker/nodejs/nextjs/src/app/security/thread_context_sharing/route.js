import { NextResponse } from 'next/server'
import { writeFileSync } from 'fs'

export const dynamic = 'force-dynamic'

export async function GET (request) {
  const path = request.nextUrl.searchParams.get('path')
  if (!path) {
    return new NextResponse('missing path query parameter', { status: 400 })
  }

  // Synchronous on purpose: async fs opens the file on a libuv worker thread, which does not carry
  // the request's thread context that the security agent reads.
  writeFileSync(path, 'thread context sharing')

  const context = global._ddtrace.scope().active().context()
  return NextResponse.json({
    trace_id: BigInt(`0x${context.toTraceId(true)}`).toString(),
    span_id: context.toSpanId()
  })
}
