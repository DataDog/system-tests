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
      // TODO when blocking is supported, throw e when is aborted
      //  to check that we are blocking as expected
      status = 500
      resolve()
    })
  })
  return NextResponse.json({}, {
    status: status || 200
  })
}
