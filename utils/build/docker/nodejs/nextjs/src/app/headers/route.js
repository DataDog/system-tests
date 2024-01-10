import { NextResponse } from 'next/server'

export async function GET (request) {
  const response = { message: 'OK' }
  return NextResponse.json(response, {
    headers: {
      'content-type': 'text/plain',
      'content-length': JSON.stringify(response).length,
      'content-language': 'en-US'
    }
  })
}
