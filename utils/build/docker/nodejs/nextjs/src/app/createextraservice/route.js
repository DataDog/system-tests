import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

export async function GET (request) {
  const serviceName = request.nextUrl.searchParams.get('serviceName')
  const span = global._ddtrace?.scope().active()
  span?.setTag('service.name', serviceName)

  return NextResponse.json({ message: 'OK' })
}
