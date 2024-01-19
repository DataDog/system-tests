import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

export async function GET (request, { params }) {
  const tracer = global._ddtrace
  const rootSpan = tracer?.scope().active()?.context()._trace.started[0]

  rootSpan?.setTag('appsec.events.system_tests_appsec_event.value', params.tag)

  if (params?.tag?.startsWith?.('payload_in_response_body') && request.method === 'POST') {
    return NextResponse.json({ payload: await request.json() })
  } else {
    return NextResponse.json('Value tagged')
  }
}
export const OPTIONS = GET
