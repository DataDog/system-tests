import { NextResponse } from 'next/server'
import http from 'http'

/**
 * Proxies the incoming request to the internal_server test fixture.
 * @param {Request} request
 * @param {string | null} resolvedPath - When null, path is `/mirror/${status}${urlExtra}` from query params.
 */
export async function forwardToInternalServer (request, resolvedPath) {
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

  const path = resolvedPath ?? `/mirror/${status}${urlExtra}`

  const options = {
    hostname: 'internal_server',
    port: 8089,
    path,
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

    if (body) {
      httpRequest.write(body)
    }

    httpRequest.end()
  })
}
