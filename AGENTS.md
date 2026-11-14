# Phil's Apps store

This repository is Philip's store for [wvw.dev](https://wvw.dev/stores/stedwick/wvw.dev.apps): `apps.json` (schema: https://wvw.dev/apps.schema.json) and the images in `screenshots/`. wvw.dev fetches the pushed `apps.json` from `main` on its scheduled rebuild (every 6 hours), so pushing here is how changes go live.

## Preview locally

- `../repos/wvw.dev` is a checkout of the fork `stedwick/wvw.dev`: upstream `f/wvw.dev` plus one commit that limits `stores.json` to this store. `scripts/sync-wvw-dev.sh` (run by `.agents/setup`) resets it to the latest upstream and reapplies that commit. Do not edit it; changes belong in this repository.
- `amp orb services ensure` starts the `store` service (`scripts/preview.py`) and prints the portal URLs. It builds the catalog with wvw.dev's own `build.sh` from the local, unpushed `apps.json`, and rebuilds when `apps.json` changes, so reload the page after an edit. `amp orb service logs store` shows the build output and any `apps.json` errors.
- Screenshot URLs of the form `https://raw.githubusercontent.com/stedwick/wvw.dev.apps/main/screenshots/<file>` are served from the local `screenshots/` folder in the preview, so new images show before they are pushed. Use that URL form for images stored in this repository.
- Only apps with at least one category that wvw.dev knows (`../repos/wvw.dev/categories.json`) are listed; the build drops the rest.
