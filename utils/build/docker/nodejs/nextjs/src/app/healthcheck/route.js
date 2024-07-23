import { NextResponse } from 'next/server'
import { version } from 'dd-trace/package.json'
import { libddwaf_version } from '@datadog/native-appsec/package.json'

export async function GET (request) {
  return NextResponse.json({
    status: 'ok',
    library: {
      language: 'nodejs',
      version: version,
      libddwaf_version: libddwaf_version
    }
  }, {
    status: 200
  })
}
