# Contributing

Keep the adapter small, portable and independent of distribution platforms.
Use Python standard-library tools; propose new dependencies before adding them.
Do not edit cinecode/. Report upstream fixes to the upstream author; a future
pin update must be deliberate, reviewed and accompanied by regenerated
lock/manifest and fresh qualification. Do not auto-update from main.

Run:

~~~sh
python -B scripts/cc.py verify
python -B -m unittest discover -s tests -v
~~~

Use python3 instead of python where appropriate. Tests use temporary fixtures;
they do not render, install software or contact media/model services.
Native Codex and media smoke scripts are explicit opt-in checks, not unit tests.
Record exact versions, exits and limitations; a skipped test is not PASS.

Keep personal paths, account/session data, logs and generated media in ignored
evidence/local/ or workspace/. Commit only sanitized qualification summaries.
Never include user film files, credentials, private user configs or models.
Retain both adapter MIT and upstream attribution. macOS/Linux support claims
require actual platform tests. Pull requests must not relax approval gates or
claim hooks/security coverage that has not been implemented.
