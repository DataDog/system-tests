import { NextResponse } from 'next/server'
import http from 'http'

export const dynamic = 'force-dynamic'

async function handleExternalRequest (request) {
  const searchParams = request.nextUrl.searchParams
  const status = searchParams.get('status') || '200'
  const urlExtra = searchParams.get('url_extra') || ''

  const headers = {}
  for (const [key, value] of searchParams.entries()) {
    if (key !== 'status' && key !== 'url_extra') {
      headers[key] = String(value)
    }
  }

  let body = null
  const contentType = request.headers.get('content-type')
  if (contentType && contentType.includes('application/json')) {
    const requestBody = await request.json()
    if (requestBody && Object.keys(requestBody).length > 0) {
      body = JSON.stringify(requestBody)
      headers['Content-Type'] = contentType || 'application/json'
    }
  }

  const options = {
    hostname: 'internal_server',
    port: 8089,
    path: `/mirror/${status}${urlExtra}`,
    method: request.method,
    headers
  }

  return new Promise((resolve) => {
    const httpRequest = http.request(options, (response) => {
      let responseBody = ''
      response.on('data', (chunk) => {
        responseBody += chunk
      })

      response.on('end', () => {
        const payload = JSON.parse(responseBody)
        resolve(NextResponse.json({
          payload,
          status: response.statusCode,
          headers: response.headers
        }))
      })
    })

    // Write body if present
    if (body) {
      httpRequest.write(body)
    }

    httpRequest.end()
  })
}

export async function GET (request) {
  return handleExternalRequest(request)
}

export async function POST (request) {
  return handleExternalRequest(request)
}

export async function PUT (request) {
  return handleExternalRequest(request)
}
