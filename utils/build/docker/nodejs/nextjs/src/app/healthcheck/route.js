/* eslint-disable no-undef */

import { NextResponse } from 'next/server'

export async function GET (request) {
  const maybeRequire = name => { try { return __non_webpack_require__(name) } catch (e) {} }

  const { version } = maybeRequire('dd-trace/package.json')

  return NextResponse.json({
    status: 'ok',
    library: {
      name: 'nodejs',
      version,
    }
  }, {
    status: 200
  })
}
