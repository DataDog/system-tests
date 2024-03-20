import { promisify } from 'util'
import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

export async function GET (request) {
  await flush()

  return NextResponse.json({ message: 'OK' })
}

// try to flush as much stuff as possible from the library
function flush () {
  const tracer = global._ddtrace
  if (!tracer) return

  // doesn't have a callback :(
  // tracer._tracer?._dataStreamsProcessor?.writer?.flush?.()
  tracer.dogstatsd?.flush?.()
  tracer._pluginManager?._pluginsByName?.openai?.metrics?.flush?.()

  // does have a callback :)
  const promises = []

  /* profiling crashes in nextjs ?
  const { profiler } = require('dd-trace/packages/dd-trace/src/profiling/')
  if (profiler?._collect) {
    promises.push(profiler._collect('on_shutdown'))
  }
  */

  if (tracer._tracer?._exporter?._writer?.flush) {
    promises.push(promisify((err) => tracer._tracer._exporter._writer.flush(err)))
  }

  if (tracer._pluginManager?._pluginsByName?.openai?.logger?.flush) {
    promises.push(promisify((err) => tracer._pluginManager._pluginsByName.openai.logger.flush(err)))
  }

  return Promise.all(promises)
}
