import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

export async function GET (request) {
  if (process.env.DD_API_SECURITY_PARSE_RESPONSE_BODY != null) {
    return NextResponse.json('{"error": "DD_API_SECURITY_PARSE_RESPONSE_BODY not implemented"}', { status: 501 })
  }

  const query = Object.fromEntries(new URL(request.url).searchParams)

  return NextResponse.json('OK', {
    status: 200,
    headers: new Headers(query)
  })
}
