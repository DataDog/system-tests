import { NextResponse } from 'next/server'

export async function GET (request) {
  const userId = request.nextUrl.searchParams.get('code')
  global._tracer.appsec.trackUserLoginSuccessEvent({
    id: userId,
    email: 'system_tests_user@system_tests_user.com',
    name: 'system_tests_user'
  }, { metadata0: 'value0', metadata1: 'value1' })

  return NextResponse.json({ message: 'OK' })
}
