'use strict'

// List the logged-in account's game records as JSON (one summary per game).
//
//   node records.js [--count N] [--start OFFSET] [--type T]
//
// `type` selects a record category. Observed on a Yostar (EN) account:
// 0 and 2 return the ranked list, 1 the friendly-room list, 4 an older
// casual category; the server keeps about 30 records per category, so
// `--start` beyond that just repeats them. Each record carries the game
// uuid (feed it to `node . UUID` or fetch_many.js), start/end time, the
// lobby config, every seat's account and nickname, and the final result.

const process = require('process')
const config = require('./config.js')
const Client = require('./client.js')

function arg(name, dflt) {
  const i = process.argv.indexOf(name)
  return i >= 0 && i + 1 < process.argv.length ? process.argv[i + 1] : dflt
}

;(async () => {
  const count = parseInt(arg('--count', '20'), 10)
  const start = parseInt(arg('--start', '0'), 10)
  const type = parseInt(arg('--type', '0'), 10)

  const client = new Client(config)
  await client.init()
  await client.waitForLogin()

  const res = await client._mjsoul.sendAsync('fetchGameRecordList', { start, count, type })
  const out = {
    account_id: client.account_id,
    total_count: res.total_count,
    records: (res.record_list || []).map((r) => ({
      uuid: r.uuid,
      start_time: r.start_time,
      end_time: r.end_time,
      category: r.config && r.config.category,
      mode: r.config && r.config.mode && r.config.mode.mode,
      mode_id: r.config && r.config.meta && r.config.meta.mode_id,
      room_id: r.config && r.config.meta && r.config.meta.room_id,
      accounts: (r.accounts || []).map((a) => ({ account_id: a.account_id, seat: a.seat, nickname: a.nickname })),
      result: r.result && r.result.players
        ? r.result.players.map((p) => ({ seat: p.seat, part_point_1: p.part_point_1, total_point: p.total_point, grading_score: p.grading_score }))
        : null,
    })),
  }
  console.log(JSON.stringify(out))
  process.exit(0)
})().catch((err) => {
  console.error(err.stack || err.message || err)
  process.exit(1)
})
