import { NextResponse } from 'next/server'
import { version } from 'dd-trace/package.json'
import { libddwaf_version as libddwafVersion } from 'dd-trace/node_modules/@datadog/native-appsec/package.json'

export async function GET (request) {
  const { wafManager } = await import('dd-trace/packages/dd-trace/src/appsec/waf')
  const tracer = import('dd-trace')

  console.log('wafManager', wafManager)
  console.log('tracer', tracer.tracer)

  return NextResponse.json({
    status: 'ok',
    library: {
      language: 'nodejs',
      version,
      libddwaf_version: libddwafVersion,
      appsec_event_rules_version: wafManager?.rulesVersion
    }
  }, {
    status: 200
  })
}
