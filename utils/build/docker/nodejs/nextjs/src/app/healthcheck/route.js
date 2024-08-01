/* eslint-disable no-undef */

import { NextResponse } from 'next/server'

export async function GET (request) {
  const rulesPath = process.env.DD_APPSEC_RULES || 'dd-trace/packages/dd-trace/src/appsec/recommended.json'

  const { version } = __non_webpack_require__('dd-trace/package.json')
  const pkg = __non_webpack_require__('dd-trace/node_modules/@datadog/native-appsec/package.json')
  const rulesVersion = __non_webpack_require__(rulesPath).metadata.rules_version

  return NextResponse.json({
    status: 'ok',
    library: {
      language: 'nodejs',
      version,
      libddwaf_version: pkg.libddwaf_version,
      appsec_event_rules_version: rulesVersion
    }
  }, {
    status: 200
  })
}
