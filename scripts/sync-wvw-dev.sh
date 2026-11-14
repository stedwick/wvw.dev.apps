#!/usr/bin/env bash
# Makes the local wvw.dev checkout match upstream f/wvw.dev, plus one commit that
# limits stores.json to this store. The preview server uses it as the store front end.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
wvw_dir="${WVW_DEV_DIR:-$repo_root/../repos/wvw.dev}"
fork_url="https://github.com/stedwick/wvw.dev"
upstream_url="https://github.com/f/wvw.dev"
store_source="stedwick/wvw.dev.apps"
commit_subject="chore: list only $store_source in stores.json"

if [ ! -d "$wvw_dir/.git" ]; then
  echo "Cloning $fork_url into $wvw_dir"
  mkdir -p "$(dirname "$wvw_dir")"
  git clone --quiet --depth 1 "$fork_url" "$wvw_dir"
fi
cd "$wvw_dir"

if [ -n "$(git status --porcelain)" ]; then
  echo "Skipping wvw.dev sync: $wvw_dir has uncommitted changes."
  exit 0
fi

git remote get-url upstream >/dev/null 2>&1 || git remote add upstream "$upstream_url"
git fetch --quiet --depth 1 upstream master

# Already in sync: HEAD is exactly upstream/master plus the stores.json commit.
if [ "$(git rev-parse -q --verify HEAD~1 || true)" = "$(git rev-parse upstream/master)" ] &&
  [ "$(git log -1 --format=%s)" = "$commit_subject" ]; then
  echo "wvw.dev already matches upstream $(git rev-parse --short upstream/master)"
  exit 0
fi

# Keep the previous state reachable in case it held work worth recovering.
git branch --quiet --force pre-sync-backup HEAD
git checkout --quiet -B master upstream/master
printf '[\n  "%s"\n]\n' "$store_source" > stores.json
git add stores.json
identity=()
git config user.email >/dev/null || identity=(-c user.name="wvw.dev sync" -c user.email="sync@localhost")
git "${identity[@]}" commit --quiet -m "$commit_subject"
echo "wvw.dev synced to upstream $(git rev-parse --short upstream/master) with stores.json = [$store_source]"
