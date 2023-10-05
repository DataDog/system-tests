import { NextResponse } from 'next/server'

export async function GET (request) {
  return NextResponse.json({ mesage: 'OK' })
}

export async function POST (request) {
  const contentType = request.headers.get('Content-Type')
  let body
  try {
    switch (contentType) {
      case 'application/json':
        body = await request.json()
        break
      case 'application/x-www-form-urlencoded':
        body = await request.formData()
        break
      default:
        body = await request.text()
    }
  } catch (e) {
    // eslint-disable-next-line no-console
    console.error('Error parsing body', e)
  }

  return NextResponse.json({ mesage: 'OK', body })
}
