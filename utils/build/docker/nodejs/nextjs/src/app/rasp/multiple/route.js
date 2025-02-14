import { NextResponse } from 'next/server'
import { statSync } from 'fs'

export const dynamic = 'force-dynamic'

export function GET (request) {
  try {
    statSync(request.nextUrl.searchParams.get('file1'))
  } catch (e) {}

  try {
    statSync(request.nextUrl.searchParams.get('file2'))
  } catch (e) {}

  try {
    statSync('../etc/passwd')
  } catch (e) {}

  return NextResponse.json({}, {
    status: 200
  })
}
