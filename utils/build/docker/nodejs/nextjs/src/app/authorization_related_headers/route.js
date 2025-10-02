import { NextResponse } from 'next/server'

export async function GET (request) {
  const response = { message: 'OK' }
  return NextResponse.json(response, {
    headers: {
      Authorization: 'value1',
      'Proxy-Authorization': 'value2',
      'WWW-Authenticate': 'value3',
      'Proxy-Authenticate': 'value4',
      'Authentication-Info': 'value5',
      'Proxy-Authentication-Info': 'value6',
      Cookie: 'value7',
      'Set-Cookie': 'value8',
      'content-type': 'text/plain'
    }
  })
}
