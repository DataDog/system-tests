import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

export async function GET (request, { params }) {
  const tracer = global._ddtrace
  const rootSpan = tracer?.scope().active()?.context()._trace.started[0]

  rootSpan?.setTag('appsec.events.system_tests_appsec_event.value', params.tag)

  return NextResponse.json('Value tagged')
}
export const OPTIONS = GET
