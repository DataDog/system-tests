import { NextResponse } from 'next/server'
import http from 'http'
import { getParam } from '../getParam'

export const dynamic = 'force-dynamic'

async function handler (request) {
  const domain = await getParam(request, 'domain')

  let status = 200
  await new Promise((resolve, reject) => {
    const clientRequest = http.get(`http://${domain}`, (response) => {
      response.resume()
      resolve()
    })
    clientRequest.on('error', (e) => {
      if (e.name === 'DatadogRaspAbortError') {
        reject(e)
        return
      }
      status = 500
      resolve()
    })
  })

  return NextResponse.json({}, {
    status
  })
}

export { handler as GET, handler as POST }
