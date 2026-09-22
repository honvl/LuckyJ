'use strict'

// Local config for the current (Unity WebGL, "v4") Mahjong Soul web client.
// Same shape as config.example.js, plus a sibling .env so the token never has
// to be exported by hand. The login fields mirror what the live client sends
// (captured 2026-09-20): login type 22, client_version_string
// "WebGL_2022-<res>", and a Route.requestConnection handshake before login.
const fs = require('fs')
const path = require('path')
const process = require('process')

const envPath = path.join(__dirname, '.env')
if (fs.existsSync(envPath)) {
  for (const line of fs.readFileSync(envPath, 'utf8').split('\n')) {
    const m = line.match(/^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*?)\s*$/)
    if (m && process.env[m[1]] === undefined) process.env[m[1]] = m[2]
  }
}

const userAgent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
// Resource version of the Unity client. It is not published at a stable URL;
// the client's own telemetry reports it as res_version. When the game updates,
// login fails with error 151 ("game version is outdated") until this is bumped.
const resVersion = process.env.MJS_RES_VERSION || '0.16.259'
// Package version (the "Build/en-WebGL-release-X.Y.Z(N)" filename on the page).
// client.js refreshes this from the page at startup when it can.
const packageVersion = process.env.MJS_PACKAGE_VERSION || '4.0.10'

const config = {
  userAgent,

  mjsoul: {
    // US: https://mahjongsoul.game.yo-star.com
    // JP: https://game.mahjongsoul.com
    base: process.env.MJS_BASE,
    // can be null; then server_config.js picks the first gateway in config.json
    gateway: process.env.MJS_GATEWAY,
    timeout: 10000,
  },

  // Route.requestConnection handshake sent before anything else.
  route: {
    type: 1,
    // "<lang>-<route index>": en-1 is route-main, en-2 is route-bk.
    route_id: process.env.MJS_ROUTE_ID || 'en-2',
    platform: 'Web',
  },
  heartbeatMs: 5000,

  resVersion,
  packageVersion,

  login: {
    type: 22,
    access_token: process.env.ACCESS_TOKEN,
    reconnect: false,
    device: {
      platform: 'pc',
      hardware: 'pc',
      os: 'mac',
      is_browser: true,
      software: 'Chrome',
      sale_platform: 'web',
      screen_width: 1456,
      screen_height: 812,
      user_agent: userAgent,
    },
    random_key: process.env.MJS_RANDOM_KEY || '1a5675c3-fcaf-495e-a147-320050388cd0',
    client_version: { resource: resVersion, package: packageVersion },
    currency_platforms: [1, 4, 5, 9, 12],
    client_version_string: `WebGL_2022-${resVersion}`,
    tag: process.env.MJS_TAG || 'en',
  },

  forceReLoginIntervalMs: 0,

  port: process.env.PORT || 2563,
  addr: '127.0.0.1',
}

if (!config.login.access_token) {
  console.error('missing access token (set ACCESS_TOKEN in .env)')
  process.exit(1)
}
if (!config.mjsoul.base) {
  console.error('missing MJS_BASE in .env')
  process.exit(1)
}

module.exports = config
