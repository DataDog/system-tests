import { NextResponse } from 'next/server'
import http from 'http'
export const dynamic = 'force-dynamic'

export async function GET (request) {
  let status = 200
  await new Promise((resolve, reject) => {
    const cl = http.get(`http://${request.nextUrl.searchParams.get('domain')}`, () => {
      resolve()
    })
    cl.on('error', (e) => {
      status = 500
      resolve()
    })
  })
  return NextResponse.json({}, {
    status: status || 200
  })
}
