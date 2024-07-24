import { NextResponse } from 'next/server'
import { version } from 'dd-trace/package.json'
import { libddwaf_version as libddwafVersion } from '@datadog/native-appsec/package.json'

export async function GET (request) {
  return NextResponse.json({
    status: 'ok',
    library: {
      language: 'nodejs',
      version,
      libddwaf_version: libddwafVersion
    }
  }, {
    status: 200
  })
}
