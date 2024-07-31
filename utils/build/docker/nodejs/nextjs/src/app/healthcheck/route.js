/* eslint-disable no-undef */

import { NextResponse } from 'next/server'

export async function GET (request) {
  const { version } = __non_webpack_require__('dd-trace/package.json')
  const pkg = __non_webpack_require__('dd-trace/node_modules/@datadog/native-appsec/package.json')
  const { wafManager } = __non_webpack_require__('dd-trace/packages/dd-trace/src/appsec/waf')

  return NextResponse.json({
    status: 'ok',
    library: {
      language: 'nodejs',
      version,
      libddwaf_version: pkg.libddwaf_version,
      appsec_event_rules_version: wafManager?.rulesVersion
    }
  }, {
    status: 200
  })
}
