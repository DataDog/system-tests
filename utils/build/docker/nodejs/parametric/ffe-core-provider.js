'use strict'

const { channel } = require('node:diagnostics_channel')
const { writeFileSync } = require('node:fs')
const { createRequire } = require('node:module')

async function main () {
  const { operation, wire, replacementWire, contexts, fetchOptions } = JSON.parse(process.argv[2])
  let httpRequests = 0
  let exposureEvents = 0
  let outcome
  const observeHttp = () => { httpRequests++ }
  const observeExposure = () => { exposureEvents++ }
  const subscriptions = [
    ['undici:request:create', observeHttp],
    ['http.client.request.start', observeHttp],
    ['ffe:exposure:submit', observeExposure]
  ]
  for (const [name, listener] of subscriptions) channel(name).subscribe(listener)

  // Resolve the tracer's packaged dependency without loading or initializing the tracer.
  const requireLibrary = createRequire(require.resolve('dd-trace/package.json'))
  const {
    ConfigurationFetchError,
    configurationFromString,
    configurationToString,
    createExposureTracking,
    DatadogCoreProvider,
    fetchRulesConfiguration
  } = requireLibrary('@datadog/openfeature-node-server/rules-based')
  const { OpenFeature, ProviderEvents } = require('@openfeature/server-sdk')
  OpenFeature.setLogger({ error () {}, warn () {}, info () {}, debug () {} })
  const tracking = ['tracking', 'overlap'].includes(operation)
    ? createExposureTracking({ collectDependencyEvaluations: true })
    : undefined
  const exposures = []
  const sink = channel('ffe:exposure:submit')
  const captureExposure = event => exposures.push(event)
  sink.subscribe(captureExposure)
  const provider = new DatadogCoreProvider(configurationFromString(wire), { ...tracking?.providerOptions })
  if (operation === 'overlap') provider.hooks.push(tracking.createHook(sink))
  let readyEvents = 0
  OpenFeature.addHandler(ProviderEvents.Ready, () => { readyEvents++ })
  OpenFeature.setProvider('offline-provider', provider)
  let client = OpenFeature.getClient('offline-provider')
  const startup = { status: client.providerStatus, readyEvents, hooks: provider.hooks.length, httpRequests }
  const evaluate = (context, options) => client.getBooleanDetails('test-flag', false, context, options)

  try {
    if (operation === 'bootstrap') {
      outcome = { startup, results: await Promise.all(contexts.map(context => evaluate(context))) }
    } else if (operation === 'overlap') {
      const observations = []
      let arrivals = 0
      let release
      const barrier = new Promise(resolve => { release = resolve })
      client.addHooks({
        after: async (hookContext, details) => {
          if (++arrivals === contexts.length) release()
          await barrier
          const sidecar = tracking.providerOptions.dependencyTelemetrySidecar
          const dependencies = sidecar.takeDependencyEvaluations(undefined, undefined, hookContext.context)
          observations.push({
            subject: hookContext.context.targetingKey,
            value: details.value,
            dependencies: dependencies.map(item => ({ flag: item.flagKey, value: item.details.value })),
            consumed: sidecar.takeDependencyEvaluations(details.flagMetadata, undefined, hookContext.context)
          })
        }
      })
      outcome = { startup, results: await Promise.all(contexts.map(context => evaluate(context))), observations, exposures }
    } else if (operation === 'refresh') {
      const initial = await evaluate(contexts[0])
      const notifications = []
      client.addHandler(ProviderEvents.ConfigurationChanged, () => {
        notifications.push({ status: client.providerStatus, result: evaluate(contexts[0]) })
      })
      let allowFetch
      let fetchEntered
      const entered = new Promise(resolve => { fetchEntered = resolve })
      const proceed = new Promise(resolve => { allowFetch = resolve })
      const refresh = fetchRulesConfiguration({
        ...fetchOptions,
        fetch: async (url, init) => {
          fetchEntered()
          await proceed
          const { pathname, search } = new URL(url)
          return fetch(`${process.env.SYSTEM_TESTS_FFE_RULES_BASE_URL}${pathname}${search}`, init)
        }
      })
      await entered
      const duringRefresh = await evaluate(contexts[0])
      allowFetch()
      let fetchError
      try {
        provider.setConfiguration(await refresh)
      } catch (error) {
        if (!(error instanceof ConfigurationFetchError)) throw error
        fetchError = { name: error.name, code: error.code, status: error.status }
      }
      const afterFetch = await evaluate(contexts[0])
      const snapshot = configurationToString(provider.getConfiguration())
      let invalidUpdateError
      try {
        provider.setConfiguration(configurationFromString('invalid wire'))
      } catch (error) {
        if (!(error instanceof TypeError)) throw error
        invalidUpdateError = error.name
      }
      const unchanged = configurationToString(provider.getConfiguration()) === snapshot
      const afterInvalid = await evaluate(contexts[0])
      provider.setConfiguration(configurationFromString(replacementWire))
      outcome = {
        startup,
        initial,
        duringRefresh,
        fetchError,
        afterFetch,
        invalidUpdateError,
        unchanged,
        afterInvalid,
        afterReplacement: await evaluate(contexts[0]),
        notifications: await Promise.all(notifications.map(async event => ({ ...event, result: await event.result })))
      }
    } else if (operation === 'tracking') {
      await evaluate(contexts[0])
      const beforeHook = exposures.length
      provider.hooks.push(tracking.createHook(sink))
      await Promise.all([evaluate(contexts[0]), evaluate(contexts[0])])
      const deduplicated = exposures.length
      const failed = await evaluate(contexts[1], { hooks: [{ after () { throw new Error('rejected by application') } }] })
      const afterFailure = exposures.length
      await evaluate(contexts[1])
      const afterRetry = exposures.length
      await OpenFeature.clearProviders()
      const restarted = new DatadogCoreProvider(configurationFromString(wire), { ...tracking.providerOptions })
      restarted.hooks.push(tracking.createHook(sink))
      OpenFeature.setProvider('offline-provider', restarted)
      client = OpenFeature.getClient('offline-provider')
      await evaluate(contexts[0])
      const afterClose = exposures.length
      tracking.clear()
      await evaluate(contexts[0])
      outcome = { startup, beforeHook, deduplicated, failed, afterFailure, afterRetry, afterClose, exposures }
    } else {
      throw new Error(`Unknown provider operation: ${operation}`)
    }
    outcome.status = client.providerStatus
    outcome.versions = {
      node: process.version,
      provider: requireLibrary('@datadog/openfeature-node-server/package.json').version
    }
  } finally {
    await OpenFeature.clearProviders()
    tracking?.clear()
    // Observe deferred activity until exit; a leaked worker hits the endpoint's process deadline.
    process.once('exit', () => {
      if (outcome !== undefined) writeFileSync(1, JSON.stringify({ ...outcome, httpRequests, exposureEvents }))
      sink.unsubscribe(captureExposure)
      for (const [name, listener] of subscriptions) channel(name).unsubscribe(listener)
    })
  }
}

main().catch(error => {
  console.error(error)
  process.exitCode = 1
})
