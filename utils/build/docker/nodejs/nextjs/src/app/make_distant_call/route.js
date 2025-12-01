import { NextResponse } from 'next/server'
import http from 'http'

export async function GET (request) {
  const url = request.nextUrl.searchParams.get('url')

  const parsedUrl = new URL(url)

  const options = {
    hostname: parsedUrl.hostname,
    port: parsedUrl.port || 80,
    path: parsedUrl.pathname,
    method: 'GET'
  }

  return new Promise((resolve) => {
    const request = http.request(options, (response) => {
      let responseBody = ''
      response.on('data', (chunk) => {
        responseBody += chunk
      })

      response.on('end', () => {
        resolve(NextResponse.json({
          url,
          status_code: response.statusCode,
          request_headers: response.req._headers,
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
