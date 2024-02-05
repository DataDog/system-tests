import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

export async function GET (request, { params }) {
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

// this function works but only when formData() is called before json()
// because formData doesn't try to read the body if it's not has form data headers
async function getBody (request) {
  try {
    return Object.fromEntries(await request.formData())
  } catch (err) {}

  try {
    return await request.json()
  } catch (err) {}

  return null
}
