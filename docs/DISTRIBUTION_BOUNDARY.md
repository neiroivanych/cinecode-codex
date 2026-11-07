# Distribution boundary

A future installer or registry can distribute the same standalone adapter.

- Read adapter.json, then VERSION for the adapter version and upstream.lock.json
  for the exact upstream revision and manifest digest.
- Resolve installation resources relative to scripts/cc.py and the skill file.
  Keep package resources at their package-relative paths.
- Default film storage is installation-root/workspace/, ignored by Git.
  A read-only installer may pass an explicit writable --workspace directory.
- The distributor may expose these existing commands and choose a workspace.
  It must preserve notices and run verification; it need not rewrite the adapter.
- Adapter setup, verification and local commands require no distributor APIs,
  external accounts or global configuration. Running a Codex session may require
  the host's own sign-in.
