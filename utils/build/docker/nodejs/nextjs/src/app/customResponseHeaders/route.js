import { NextResponse } from 'next/server'

export async function GET (request) {
  const response = { message: 'OK' }
  return NextResponse.json(response, {
    headers: {
      'content-type': 'text/plain',
      'content-language': 'en-US',
      'x-test-header-1': 'value1',
      'x-test-header-2': 'value2',
      'x-test-header-3': 'value3',
      'x-test-header-4': 'value4',
      'x-test-header-5': 'value5',
    }
  })
}
