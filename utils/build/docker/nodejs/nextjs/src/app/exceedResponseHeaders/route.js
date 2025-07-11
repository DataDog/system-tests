import { NextResponse } from 'next/server'

export async function GET (request) {
  const response = { message: 'OK' }
  return NextResponse.json(response, {
    headers: {
      'content-type': 'text/plain',
      ...Object.fromEntries(
        Array.from({ length: 50 }, (_, i) => [`x-test-header-${i}`, `value${i}`])
      ),
      'content-language': 'en-US',
    }
  })
}
