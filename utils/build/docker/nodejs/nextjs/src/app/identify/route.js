import { NextResponse } from 'next/server'

export async function GET (request) {
  global._ddtrace.setUser({
    id: 'usr.id',
    email: 'usr.email',
    name: 'usr.name',
    session_id: 'usr.session_id',
    role: 'usr.role',
    scope: 'usr.scope'
  })

  return NextResponse.json({ message: 'OK' })
}
