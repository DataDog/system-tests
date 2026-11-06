import { NextResponse } from 'next/server'
import { forwardToInternalServer } from '../../forwardToInternalServer'

export const dynamic = 'force-dynamic'

const DOWNSTREAM_RESPONSE_BODY_LIMIT_PROFILES = new Set([
  'invalid_content_type',
  'content_length_missing',
  'content_length_too_big'
])

async function handleBodyLimit (request, { params }) {
  const { failureReason } = params
  if (!DOWNSTREAM_RESPONSE_BODY_LIMIT_PROFILES.has(failureReason)) {
    return NextResponse.json({ error: 'unknown failure reason' }, { status: 404 })
  }
  return forwardToInternalServer(request, `/downstream_response/${failureReason}`)
}

export async function GET (request, ctx) {
  return handleBodyLimit(request, ctx)
}

export async function POST (request, ctx) {
  return handleBodyLimit(request, ctx)
}

export async function PUT (request, ctx) {
  return handleBodyLimit(request, ctx)
}
