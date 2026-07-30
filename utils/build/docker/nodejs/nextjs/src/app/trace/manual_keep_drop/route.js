import { NextResponse } from 'next/server'
import http from 'http'

export const dynamic = 'force-dynamic'

export async function GET (request) {
  const decision = request.nextUrl.searchParams.get('decision')

  if (decision !== 'keep' && decision !== 'drop') {
    return new NextResponse('decision must be keep or drop', { status: 400 })
  }

  const tracer = global._ddtrace
  tracer?.scope().active()?.setTag(decision === 'keep' ? 'manual.keep' : 'manual.drop', true)

  // Call downstream so that tests can assert on the sampling decision that gets propagated
  const url = 'http://localhost:7777/'
  return new Promise((resolve) => {
    const downstream = http.request({ hostname: 'localhost', port: 7777, path: '/', method: 'GET' }, (response) => {
      response.on('data', () => {})

      response.on('end', () => {
        resolve(NextResponse.json({
          url,
          status_code: response.statusCode,
          request_headers: response.req.getHeaders(),
          response_headers: response.headers
        }))
      })
    })

    downstream.on('error', (error) => {
      console.log(error)
      resolve(new NextResponse(error.message, { status: 500 }))
    })

    downstream.end()
  })
}
