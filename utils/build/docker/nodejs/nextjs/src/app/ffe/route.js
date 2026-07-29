import { OpenFeature } from '@openfeature/server-sdk'
import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

let openFeatureClient = null
let openFeatureClientPromise = null

async function getOpenFeatureClient () {
  if (openFeatureClient) {
    return openFeatureClient
  }

  const tracer = global._ddtrace
  if (!tracer?.openfeature || process.env.DD_EXPERIMENTAL_FLAGGING_PROVIDER_ENABLED !== 'true') {
    return null
  }

  if (!openFeatureClientPromise) {
    openFeatureClientPromise = OpenFeature.setProviderAndWait(tracer.openfeature)
      .then(() => {
        openFeatureClient = OpenFeature.getClient()
        return openFeatureClient
      })
      .catch(error => {
        openFeatureClientPromise = null
        throw error
      })
  }

  return openFeatureClientPromise
}

export async function POST (request) {
  try {
    const client = await getOpenFeatureClient()
    if (!client) {
      return NextResponse.json({ error: 'FFE provider not initialized' }, { status: 500 })
    }

    const { flag, variationType, defaultValue, targetingKey, targetingKeys, attributes } = await request.json()
    const keys = Array.isArray(targetingKeys) && targetingKeys.length > 0 ? targetingKeys : [targetingKey]
    let value

    for (const key of keys) {
      const context = { targetingKey: key, ...attributes }

      switch (variationType) {
        case 'BOOLEAN':
          value = await client.getBooleanValue(flag, defaultValue, context)
          break
        case 'STRING':
          value = await client.getStringValue(flag, defaultValue, context)
          break
        case 'INTEGER':
        case 'NUMERIC':
          value = await client.getNumberValue(flag, defaultValue, context)
          break
        case 'JSON':
          value = await client.getObjectValue(flag, defaultValue, context)
          break
        default:
          return NextResponse.json({ error: `Unknown variation type: ${variationType}` }, { status: 400 })
      }
    }

    return NextResponse.json({ value, count: keys.length })
  } catch (error) {
    console.error('[FFE] Error:', error)
    return NextResponse.json({ error: error.message }, { status: 500 })
  }
}
