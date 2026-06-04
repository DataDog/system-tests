#!/usr/bin/env node
// Prune node_modules using @vercel/nft static analysis. Keeps only files that
// are statically reachable from the given entry points; deletes everything
// else, including the nft package itself (which is not reachable from the app).
import { nodeFileTrace } from '@vercel/nft'
import { readdir, rm } from 'fs/promises'
import { join, relative } from 'path'

const cwd = process.cwd()
const args = process.argv.slice(2)
const keepTypes = args.includes('--keep-types')
const entries = args.filter(a => !a.startsWith('--'))

if (entries.length === 0) {
  process.stderr.write('Usage: nft-prune.mjs [--keep-types] <entry1.js> [entry2.js ...]\n')
  process.exit(1)
}

const { fileList } = await nodeFileTrace(entries, { base: cwd })
const keep = new Set([...fileList].filter(f => f.startsWith('node_modules/')))

async function* walk (dir) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name)
    if (entry.isDirectory()) yield * walk(full)
    else yield full
  }
}

if (keepTypes) {
  for await (const fullPath of walk(join(cwd, 'node_modules/@types'))) {
    keep.add(relative(cwd, fullPath))
  }
}

let removed = 0
for await (const fullPath of walk(join(cwd, 'node_modules'))) {
  const rel = relative(cwd, fullPath)
  if (!keep.has(rel)) {
    await rm(fullPath)
    removed++
  }
}

process.stdout.write(`nft-prune: kept ${keep.size}, removed ${removed} files\n`)
