'use strict'

// Convert many Mahjong Soul logs with a single login.
//
//   node fetch_many.js --out DIR UUID [UUID ...]
//
// Writes DIR/<uuid>.json (tenhou.net/6 format, as `node . UUID` prints) for
// each id that does not already exist there, and prints one JSON line per id:
// {"uuid":..., "file":..., "status": "written"|"exists"|"error", "error"?: ...}

const fs = require('fs')
const path = require('path')
const process = require('process')
const config = require('./config.js')
const Client = require('./client.js')

;(async () => {
  const argv = process.argv.slice(2)
  const oi = argv.indexOf('--out')
  if (oi < 0 || oi + 1 >= argv.length) {
    console.error('usage: node fetch_many.js --out DIR UUID [UUID ...]')
    process.exit(2)
  }
  const outDir = argv[oi + 1]
  const ids = argv.filter((a, i) => i !== oi && i !== oi + 1)
  fs.mkdirSync(outDir, { recursive: true })

  const client = new Client(config)
  await client.init()
  await client.waitForLogin()

  for (const id of ids) {
    const file = path.join(outDir, id.split('_')[0] + '.json')
    if (fs.existsSync(file)) {
      console.log(JSON.stringify({ uuid: id, file, status: 'exists' }))
      continue
    }
    let lastErr = null
    for (let attempt = 0; attempt < 5; attempt++) {
      try {
        const log = await client.tenhouLogFromMjsoulID(id)
        fs.writeFileSync(file, JSON.stringify(log))
        console.log(JSON.stringify({ uuid: id, file, status: 'written', attempts: attempt + 1 }))
        lastErr = null
        break
      } catch (err) {
        lastErr = err
        const code = err && err.error && err.error.code
        // 540: the record server throttles bursts of fetchGameRecord calls.
        if (code !== 540) break
        await new Promise((resolve) => setTimeout(resolve, 5000 * (attempt + 1)))
      }
    }
    if (lastErr) {
      console.log(JSON.stringify({ uuid: id, file, status: 'error', error: String(lastErr && (lastErr.message || lastErr.error && JSON.stringify(lastErr.error)) || lastErr) }))
    }
    // be polite to the record server
    await new Promise((resolve) => setTimeout(resolve, 1500))
  }
  process.exit(0)
})().catch((err) => {
  console.error(err.stack || err.message || err)
  process.exit(1)
})
