'use strict'

const {
  ConfigurationFetchError,
  configurationToString,
  fetchRulesConfiguration
} = require('dd-trace/openfeature/rules-based')

async function main () {
  const { abort = false, abortAfterMs, ...options } = JSON.parse(process.argv[2])
  const controller = new AbortController()
  if (abort) controller.abort()
  const abortTimer = abortAfterMs === undefined
    ? undefined
    : setTimeout(() => controller.abort(new Error('private-cancellation-reason')), abortAfterMs)

  try {
    const configuration = await fetchRulesConfiguration({
      ...options,
      signal: controller.signal,
      // Exercise real HTTP while keeping generated paths, headers, and fetch options intact.
      fetch: (url, init) => {
        const { pathname, search } = new URL(url)
        return fetch(`${process.env.SYSTEM_TESTS_FFE_RULES_BASE_URL}${pathname}${search}`, init)
      }
    })
    process.stdout.write(JSON.stringify({ wire: configurationToString(configuration) }))
  } catch (error) {
    if (!(error instanceof ConfigurationFetchError)) throw error
    process.stdout.write(JSON.stringify({
      error: { name: error.name, code: error.code, message: error.message, status: error.status }
    }))
  } finally {
    clearTimeout(abortTimer)
  }
}

main().catch(error => {
  console.error(error)
  process.exitCode = 1
})
