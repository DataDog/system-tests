import { forwardToInternalServer } from './forwardToInternalServer'

export const dynamic = 'force-dynamic'

export async function GET (request) {
  return forwardToInternalServer(request, null)
}

export async function POST (request) {
  return forwardToInternalServer(request, null)
}

export async function PUT (request) {
  return forwardToInternalServer(request, null)
}
