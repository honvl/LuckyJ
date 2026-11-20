import assert from "node:assert/strict";
import { test } from "node:test";
import { archiveMount, gamesFiles, gamesResources } from "./games-rules.mjs";

test("the first archive keeps the name setup.sh has always read", () => {
  assert.equal(archiveMount(1), "/player/games.tar.gz");
  assert.equal(archiveMount(2), "/player/games-2.tar.gz");
  assert.equal(archiveMount(11), "/player/games-11.tar.gz");
});

test("a new thread mounts every archive, oldest first", () => {
  const player = { threads: [{ session_id: "s1", games_file_id: "file_a" }], games: { uuids: [], archives: [{ file_id: "file_a" }, { file_id: "file_b" }, { file_id: "file_c" }] } };
  assert.deepEqual(gamesResources(player), [
    { type: "file", file_id: "file_a", mount_path: "/player/games.tar.gz" },
    { type: "file", file_id: "file_b", mount_path: "/player/games-2.tar.gz" },
    { type: "file", file_id: "file_c", mount_path: "/player/games-3.tar.gz" },
  ]);
});

test("a player from before deliveries were recorded mounts the newest thread's upload", () => {
  const player = { threads: [{ session_id: "s1", games_file_id: "old" }, { session_id: "s2", games_file_id: "new" }, { session_id: "s3" }] };
  assert.deepEqual(gamesFiles(player), ["new"]);
  assert.deepEqual(gamesFiles({ threads: [] }), []);
});
