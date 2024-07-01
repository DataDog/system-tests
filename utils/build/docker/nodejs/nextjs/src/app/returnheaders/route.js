import { NextResponse } from 'next/server'

export async function GET (request) {
  const response = Object.fromEntries(request.headers.entries())
  return NextResponse.json(response)
}
