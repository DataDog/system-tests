import { NextResponse } from 'next/server'
import http from 'http'

export const dynamic = 'force-dynamic'

export async function GET (request) {
  const searchParams = request.nextUrl.searchParams
  const headers = {}
  for (const [key, value] of searchParams.entries()) {
    headers[key] = String(value)
  }

  const totalRedirects = searchParams.get('totalRedirects') || '0'

  // Recursive function to follow redirects
  const followRedirect = (path) => {
    return new Promise((resolve) => {
      const options = {
        hostname: 'internal_server',
        port: 8089,
        path,
        method: 'GET',
        headers
      }

      const httpRequest = http.request(options, (response) => {
        if (response.statusCode === 302 && response.headers.location) {
          // Follow the redirect
          resolve(followRedirect(response.headers.location))
        } else {
          // Final response
          response.on('end', () => {
            resolve(NextResponse.json({ status: 'OK' }, { status: 200 }))
          })
          response.resume()
        }
      })

      httpRequest.end()
    })
  }

  // Start the redirect chain
  return followRedirect(`/redirect?totalRedirects=${totalRedirects}`)
}
