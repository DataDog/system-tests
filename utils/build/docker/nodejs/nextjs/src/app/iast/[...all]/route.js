import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

export async function GET () {
  return NextResponse.json({ message: 'Not implemented' }, { status: 404 })
}

export async function POST () {
  return NextResponse.json({ message: 'Not implemented' }, { status: 404 })
}
