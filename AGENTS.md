# cinecode-codex repository guidance

This is an independent community Codex adapter, not the upstream CineCode project.
Read .agents/skills/cinecode/SKILL.md for a CineCode request.

- cinecode/ is an exact pinned vendor snapshot. Never edit it or update from main.
- Adapter implementation belongs in scripts/, tests/, docs/ and the repo skill.
- User projects belong in workspace/ (ignored), or an explicitly selected workspace.
- A development/qualification request is not a request to start a real film.
- No lifecycle hooks, paid calls, installs, models or secrets without explicit scope.
- Preserve actual user decisions, upstream notices and the reduced-protection claim.
- Verify with python -B scripts/cc.py verify and python -B -m unittest discover -s tests -v.
- Native discovery and media qualification are opt-in integration checks; do not
  report them PASS from file presence, mocked tests, or doctor alone.
- No publication or remote configuration unless the owner explicitly asks.
