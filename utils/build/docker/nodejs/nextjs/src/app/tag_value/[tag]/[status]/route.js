import { NextResponse } from 'next/server'
import { headers } from 'next/headers'

export const dynamic = 'force-dynamic'

export async function GET (request, { params }) {
  if (process.env.DD_API_SECURITY_PARSE_RESPONSE_BODY != null) {
    return NextResponse.json('{"error": "DD_API_SECURITY_PARSE_RESPONSE_BODY not implemented"}', { status: 501 })
  }

  // always read body for API sec, before processing the request as the other weblogs do: a blocked body must not set
  // the tag below
  const body = await getBody(request)

  const tracer = global._ddtrace
  const rootSpan = tracer?.scope().active()?.context()._trace.started[0]

  rootSpan?.setTag('appsec.events.system_tests_appsec_event.value', params.tag)

  // read querystring
  const query = Object.fromEntries(new URL(request.url).searchParams)

  const init = {
    status: params.status || 200,
    headers: new Headers(query)
  }

  if (params?.tag?.startsWith?.('payload_in_response_body') && request.method === 'POST') {
    return NextResponse.json({ payload: body }, init)
  }

  return new NextResponse('Value tagged', init)
}
export const OPTIONS = GET
export const POST = GET

async function getBody (request) {
  const contentType = headers().get('content-type')
  if (contentType?.toLowerCase() === 'application/json') {
    return await request.json()
  }
  if (['multipart/form-data', 'application/x-www-form-urlencoded'].includes(contentType?.toLowerCase())) {
    return Object.fromEntries(await request.formData())
  }
  return null
}
