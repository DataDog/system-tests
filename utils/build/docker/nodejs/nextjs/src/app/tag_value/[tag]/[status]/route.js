import { NextResponse } from 'next/server'
import { headers } from 'next/headers'

export const dynamic = 'force-dynamic'

export async function GET (request, { params }) {
  if (process.env.DD_API_SECURITY_PARSE_RESPONSE_BODY != null) {
    return NextResponse.json('{"error": "DD_API_SECURITY_PARSE_RESPONSE_BODY not implemented"}', { status: 501 })
  }

  const tracer = global._ddtrace
  const rootSpan = tracer?.scope().active()?.context()._trace.started[0]

  rootSpan?.setTag('appsec.events.system_tests_appsec_event.value', params.tag)

  // read querystring
  const query = Object.fromEntries(new URL(request.url).searchParams)

  // always read body for API sec
  const body = await getBody(request)

  let response

  if (params?.tag?.startsWith?.('payload_in_response_body') && request.method === 'POST') {
    response = { payload: body }
  } else {
    response = 'Value tagged'
  }

  return NextResponse.json(response, {
    status: params.status || 200,
    headers: new Headers(query)
  })
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
