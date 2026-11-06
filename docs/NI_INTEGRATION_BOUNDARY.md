# Future packaging boundary

NI AI Creator Tools is not a dependency and is not integrated in this release.
A future installer or registry may distribute the same repository contents.

- Read adapter.json, then VERSION for the adapter version and upstream.lock.json
  for the exact upstream revision and manifest digest.
- Resolve installation resources relative to scripts/cc.py and the skill file.
  Never infer resources from an installer parent or a research checkout.
- Default film storage is installation-root/workspace/, ignored by Git.
  A read-only installer may pass an explicit writable --workspace directory.
- The distributor may expose these existing commands and choose a workspace.
  It must preserve notices and run verification; it need not rewrite the adapter.
- No NI APIs, authentication, global Codex config or NI-specific paths are needed.

This note defines package inputs and ownership only. It does not design an NI
platform, registry protocol, account model or installation system.
