import { NextResponse } from 'next/server'
import { version } from 'dd-trace/package.json'
import { libddwaf_version as libddwafVersion } from 'dd-trace/node_modules/@datadog/native-appsec/package.json'
import { metadata } from 'dd-trace/packages/dd-trace/src/appsec/recommended.json'

export async function GET (request) {
  return NextResponse.json({
    status: 'ok',
    library: {
      language: 'nodejs',
      version,
      libddwaf_version: libddwafVersion,
      appsec_event_rules_version: metadata.rules_version
    }
  }, {
    status: 200
  })
}
