'use strict'

const { channel } = require('node:diagnostics_channel')

async function main () {
  const { wire, fetchOptions, contexts, options } = JSON.parse(process.argv[2])
  let httpRequests = 0
  let trackingEvents = 0
  const observeHttp = () => { httpRequests++ }
  const observeTracking = () => { trackingEvents++ }
  const subscriptions = [
    ['undici:request:create', observeHttp],
    ['http.client.request.start', observeHttp],
    ['dd-trace:openfeature:exposure', observeTracking],
    ['dd-trace:openfeature:evaluation', observeTracking]
  ]
  for (const [name, listener] of subscriptions) channel(name).subscribe(listener)

  try {
    const {
      ConfigurationFetchError,
      ConfigurationPrecomputeError,
      configurationFromString,
      configurationToString,
      fetchRulesConfiguration,
      precomputeConfiguration
    } = require('dd-trace/openfeature/rules-based')
    try {
      const configuration = fetchOptions
        ? await fetchRulesConfiguration({
          ...fetchOptions,
          fetch: (url, init) => {
            const { pathname, search } = new URL(url)
            return fetch(`${process.env.SYSTEM_TESTS_FFE_RULES_BASE_URL}${pathname}${search}`, init)
          }
        })
        : configurationFromString(wire)
      const results = contexts.map(context => {
        const errors = []
        const precomputed = precomputeConfiguration(configuration, context, {
          ...options,
          onEvaluationError: error => errors.push(error)
        })
        return { wire: configurationToString(precomputed), errors }
      })
      process.stdout.write(JSON.stringify({ results, httpRequests, trackingEvents }))
    } catch (error) {
      if (!(error instanceof ConfigurationPrecomputeError) && !(error instanceof ConfigurationFetchError)) throw error
      process.stdout.write(JSON.stringify({
        error: { name: error.name, code: error.code, message: error.message },
        httpRequests,
        trackingEvents
      }))
    }
  } finally {
    for (const [name, listener] of subscriptions) channel(name).unsubscribe(listener)
  }
}

main().catch(error => {
  console.error(error)
  process.exitCode = 1
})
