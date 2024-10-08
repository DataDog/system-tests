/* eslint-disable no-undef */

import { NextResponse } from 'next/server'

export async function GET (request) {
  const rulesPath = process.env.DD_APPSEC_RULES || 'dd-trace/packages/dd-trace/src/appsec/recommended.json'
  const maybeRequire = name => { try { return __non_webpack_require__(name) } catch (e) {} }

  const { version } = maybeRequire('dd-trace/package.json')
  const pkg = maybeRequire('dd-trace/node_modules/@datadog/native-appsec/package.json')
  const rulesVersion = maybeRequire(rulesPath)?.metadata.rules_version

  return NextResponse.json({
    status: 'ok',
    library: {
      language: 'nodejs',
      version,
    }
  }, {
    status: 200
  })
}
