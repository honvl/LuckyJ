// A player's games reach a thread as archives mounted in its sandbox: the one made at sign-up, then
// one more for each top-up (service/thread.py games). The names match thread.py's archive_mount()
// and what service/sandbox/setup.sh unpacks.

/** Where a player's k-th games archive is mounted (k from 1). */
export function archiveMount(k) {
  return k === 1 ? "/player/games.tar.gz" : `/player/games-${k}.tar.gz`;
}

/** The player's games archives, oldest first (file ids): the recorded deliveries, or for a player
 * from before deliveries were recorded, the newest thread's single upload. */
export function gamesFiles(player) {
  const files = (player?.games?.archives || []).map((a) => a.file_id).filter(Boolean);
  if (files.length) return files;
  const last = [...(player?.threads || [])].reverse().find((t) => t.games_file_id)?.games_file_id;
  return last ? [last] : [];
}

/** The file resources that mount every archive in a new thread. */
export function gamesResources(player) {
  return gamesFiles(player).map((file_id, i) => ({ type: "file", file_id, mount_path: archiveMount(i + 1) }));
}
