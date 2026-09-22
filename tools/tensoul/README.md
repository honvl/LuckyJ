# tensoul, patched for the current Mahjong Soul web client

[tensoul](https://github.com/Equim-chan/tensoul) converts Mahjong Soul records to
tenhou.net/6 JSON. Its last commit predates the move of the web client to a Unity
WebGL build, so stock tensoul now fails to log in: every request comes back with
error 151 ("your game version is outdated"). `v4-client.patch` brings it up to
date, based on a capture of the live client's websocket traffic on 2026-09-20:

- `config.json` no longer lists service-discovery URLs; it lists gateway hosts
  under `gateways`, and the websocket is `wss://<host>/gateway`.
- Every connection opens with `.lq.Route.requestConnection` (type 1, route id
  `en-2`, unix timestamp, platform `Web`) and keeps a `.lq.Route.heartbeat`
  going. Without the handshake the server treats the client as outdated.
- Login is `oauth2Login` type 22 with `client_version {resource, package}`,
  `client_version_string "WebGL_2022-<resource>"` and `tag "en"`. The published
  liqi.json already declares the Route service; the patch only adds the
  handshake's undeclared sixth field.

Added scripts:

- `records.js` lists the logged-in account's record history as JSON (the server
  keeps the last 30 games).
- `fetch_many.js` converts many ids with one login, writing `<uuid>.json` files.
  The record server throttles bursts (error 540); the script backs off and
  retries.

`sh tools/tensoul/install.sh` clones, patches and installs into `tmp/tensoul`.
