import { NextResponse } from 'next/server'
import http from 'http'

export async function GET (request) {
  const url = request.nextUrl.searchParams.get('url')
  const parsedUrl = new URL(url)
  const method = request.nextUrl.searchParams.get('method') || 'GET'

  return new Promise((resolve) => {
    // Keep query strings and credentials intact so the tracer sees the full outbound URL.
    const request = http.request(parsedUrl, { method }, (response) => {
      let responseBody = ''
      response.on('data', (chunk) => {
        responseBody += chunk
      })

      response.on('end', () => {
        resolve(NextResponse.json({
          url,
          status_code: response.statusCode,
          request_headers: response.req.getHeaders(),
          response_headers: response.headers,
          response_body: responseBody
        }))
      })
    })

    request.on('error', (error) => {
      console.log(error)
      resolve(NextResponse.json({
        url,
        status_code: 500,
        request_headers: null,
        response_headers: null
      }))
    })

    request.end()
  })
}
