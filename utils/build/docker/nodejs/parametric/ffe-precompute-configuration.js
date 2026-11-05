'use strict'

const { channel } = require('node:diagnostics_channel')
const { writeFileSync } = require('node:fs')

async function main () {
  const { wire, fetchOptions, contexts, options } = JSON.parse(process.argv[2])
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
      outcome = { results }
    } catch (error) {
      if (!(error instanceof ConfigurationPrecomputeError) && !(error instanceof ConfigurationFetchError)) throw error
      outcome = { error: { name: error.name, code: error.code, message: error.message } }
    }
  } finally {
    // Include deferred activity until the child exits; persistent work hits the parent timeout.
    process.once('exit', () => {
      if (outcome !== undefined) writeFileSync(1, JSON.stringify({ ...outcome, httpRequests, exposureEvents }))
      for (const [name, listener] of subscriptions) channel(name).unsubscribe(listener)
    })
  }
}

main().catch(error => {
  console.error(error)
  process.exitCode = 1
})
