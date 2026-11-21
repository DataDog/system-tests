'use strict'

const { channel } = require('node:diagnostics_channel')
const { writeFileSync } = require('node:fs')
const { createRequire } = require('node:module')

async function main () {
  const { options, entryPoint = 'root', abort = false, abortAfterMs, mutateContext = false, evaluate = true, contexts, trackExposures = false } = JSON.parse(process.argv[2])
  let httpRequests = 0
  let exposureEvents = 0
  let requestUrl
  let outcome
  const subscriptions = [
    ['undici:request:create', () => { httpRequests++ }],
    ['http.client.request.start', () => { httpRequests++ }],
    ['ffe:exposure:submit', () => { exposureEvents++ }]
  ]
  for (const [name, listener] of subscriptions) channel(name).subscribe(listener)
  const requireLibrary = createRequire(require.resolve('dd-trace/package.json'))
  // Load the bundles shipped by the tracer, without importing or initializing the tracer.
  const root = requireLibrary('./vendor/dist/@datadog/openfeature-node-server')
  const rules = requireLibrary('./vendor/dist/@datadog/openfeature-node-server/rules-based')
  const sdk = entryPoint === 'root' ? root : rules
  const { OpenFeature } = require('@openfeature/server-sdk')
  OpenFeature.setLogger({ error () {}, warn () {}, info () {}, debug () {} })
  const originalContext = structuredClone(options.context)
  const diagnostics = []
  const controller = new AbortController()
  if (abort) controller.abort(new Error('private-cancellation-reason'))
  const timer = abortAfterMs === undefined ? undefined : setTimeout(() => controller.abort(new Error('private-cancellation-reason')), abortAfterMs)
  try {
    try {
      const configuration = await sdk.fetchPrecomputedConfiguration({
        ...options,
        signal: controller.signal,
        logger: { error: message => diagnostics.push(message) },
        fetch: (url, init) => {
          requestUrl = String(url)
          if (mutateContext) {
            options.context.country = 'changed-after-request'
            options.context.nested.tags.push('changed-after-request')
          }
          const { pathname, search } = new URL(url)
          return fetch(`${process.env.SYSTEM_TESTS_FFE_RULES_BASE_URL}${pathname}${search}`, init)
        }
      })
      const wire = sdk.configurationToString(configuration)
      const restored = sdk.configurationFromString(wire)
      outcome = { wire, restored: sdk.configurationToString(restored), diagnostics, exposuresBeforeTracking: exposureEvents }
      if (evaluate) {
        const provider = new rules.DatadogCoreProvider(restored, {
          experimentationOptOutMode: options.experimentationOptOutMode,
          ...(trackExposures && { exposureChannel: channel('ffe:exposure:submit') })
        })
        OpenFeature.setProvider('precomputed-fetch', provider)
        const client = OpenFeature.getClient('precomputed-fetch')
        outcome.providerStatus = client.providerStatus
        outcome.results = await Promise.all((contexts ?? [originalContext]).map(context => client.getBooleanDetails('test-flag', false, context)))
        outcome.nullable = await client.getObjectDetails('nullable', { fallback: true }, originalContext)
      }
    } catch (error) {
      if (!(error instanceof sdk.ConfigurationFetchError)) throw error
      outcome = { error: { name: error.name, code: error.code, message: error.message, status: error.status }, diagnostics }
    }
  } finally {
    clearTimeout(timer)
    await OpenFeature.clearProviders()
    process.once('exit', () => {
      if (outcome !== undefined) writeFileSync(1, JSON.stringify({ ...outcome, requestUrl, httpRequests, exposureEvents }))
      for (const [name, listener] of subscriptions) channel(name).unsubscribe(listener)
    })
  }
}

main().catch(error => {
  console.error(error)
  process.exitCode = 1
})
