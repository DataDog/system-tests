import { NextResponse } from 'next/server'

export async function GET (request) {
  return NextResponse.json({
    message: 'OK'
  }, {
    status: request.nextUrl.searchParams.get('code')
  })
}
