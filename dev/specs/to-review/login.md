# `codehood login` / `codehood logout`

Roadmap 0.1.0 lists both, sitting right after `codehood api`. `cli/init.py`
already carries two explicit hooks for this — `_default_server` and
`_has_credentials` — both stubbed to do nothing until a credentials store
exists. This spec builds that store and the two commands that use it, and
wires the result into `src/codehood_cli/api/generated.py` so every future
authenticated command (`push`, `roster`) gets a bearer token for free.

## Scope

- `codehood login`: prompt for a login (email or username) and a
  hidden-input password, exchange them for a CLI API key via the existing
  `cliLogin` endpoint, and store the key locally.
- `codehood logout`: forget the locally stored key for the current
  repository's server.
- `~/.codehood/credentials.toml`: a global (not per-repo), `chmod 600`
  file holding one token per server URL.
- `api/generate.py`: generated functions for an operation whose effective
  `security` is non-empty now attach `Authorization: Bearer <token>`,
  reading it from the new store via a helper in `api/base.py`.
- `api/base.py`: `save_token`/`load_token`/`delete_token`, `auth_headers`,
  and `NotLoggedInError` — the credentials store and its one failure mode.

Out of scope, and why, in the closing section: revoking the key
server-side, and wiring `--server`/`--login` flags into either command.

## Design decisions

### Credentials are global, not per-repo

`.codehood/` (repo-local, gitignored) already holds machine state, and was
the obvious first guess for where a token should live. But `_default_server`
is called from inside `codehood init`, before the target directory is
necessarily a repository at all — there is no `.codehood/` to put anything
in yet at the point the hook needs an answer. A credential is also not a
property of a course repository; it's a property of the account on a given
server, and one instructor's machine may hold several course repos pointed
at the same server. So the store lives at `~/.codehood/credentials.toml`,
one level up from any single repo, keyed by server URL — a second login to
the same server overwrites the same entry rather than creating a new one,
which is what `_default_server`'s own docstring already assumed
("credentials keyed by server URL").

### A plain file, not the OS keyring

An OS keyring (via the `keyring` package) is the more conventional place
for a secret, but it doesn't work uniformly headless — SSH sessions and CI
runners routinely have no keyring daemon available, and an instructor
running this over SSH to a shared grading box is a realistic case, not an
edge one. A plain TOML file with `chmod 600` is what `gh` and `flyctl` both
fall back to for the same reason, and it costs no new dependency —
`tomlkit` is already used for `codehood.toml`.

### Logout deletes locally; server-side revocation is future work

The roadmap says logout should "revoke the API token," but `codehood-server`
has no REST endpoint for that today — `apiKeyService.revoke()` exists in
its service layer, and there's an unmounted `route("post",
"/api/auth/logout", ...)` in `auth.ts`, but neither is wired under
`src/pages/api/`, and the mounted one only deletes browser `Session` rows,
not API keys. Building that endpoint is `codehood-server` work, not this
repo's. So `codehood logout` does the part it can do — forget the key
locally — and says so: it prints a note that the key remains valid until
revoked from `/profile`, rather than silently implying more than it did.

### The bearer token is attached inside generated code, gated per operation

`api/generate.py` already threads `spec.requires_auth(operation)` through
`codehood api`'s browsing screen to decide whether a call would need a key
it doesn't have. The same fact now drives codegen itself: `render_function`
appends `headers=auth_headers(client)` to the request call only for an
operation whose effective `security` is non-empty. `auth_headers` (in
`api/base.py`, the one file codegen never touches) resolves the token from
`client.base_url` and raises `NotLoggedInError` *before* the request is
sent if there isn't one — the same "fail with a clear message instead of a
server round-trip that was always going to fail" instinct `codehood api`'s
own refusal already follows, just enforced one layer down so it also
covers `push`/`roster` calling generated functions directly, not just the
browser.

Neither endpoint in `ENDPOINTS` today (`getHealth`, `cliLogin`) actually
requires auth, so this path isn't exercised by real traffic yet — it's
proven with a fixture spec carrying a synthetic authenticated operation,
the same technique `test_cli_api.py`'s `SPEC_WITH_CALLS`/`getMe` already
uses for the browser's own gate.

### Login and logout take no flags — the repository's config is the only source

`--server` and `--login` were both considered and dropped. A course
repository already names its one server in `codehood.toml`, and a login
identity is exactly the kind of value that shouldn't be typeable on a
command line at all (shell history, `ps`, shoulder-surfing) — even without
the password sitting next to it, echoing the account name back is
information a flag would leak for no benefit over just asking. Both
commands resolve the server from the current directory's `codehood.toml`
and error clearly if there isn't one; `login` prompts visibly for the
account name and via hidden input for the password, mirroring `init.py`'s
existing prompt style.

## Proving it works

- **`save_token`/`load_token`/`delete_token` round-trip**, keyed by server
  URL, against a `tmp_path`-redirected store.
- **The credentials file is written `chmod 600`.**
- **A second `save_token` for a different server URL doesn't clobber the
  first** — both are readable afterward.
- **`auth_headers` raises `NotLoggedInError` before any request** when
  nothing is stored for the client's `base_url`, and returns the right
  `Authorization` header when something is.
- **Codegen attaches `headers=auth_headers(client)`** for a fixture
  operation with non-empty effective `security`, and omits it for one
  without — both against the same fixture spec so the difference is only
  the `security` field.
- **`codehood login`**: happy path stores the returned token and prints no
  raw key to the terminal; a `cliLogin` `ApiError` (bad credentials) exits
  non-zero with the server's message; running outside a repository (no
  `codehood.toml`) errors clearly instead of prompting for a server.
- **`codehood logout`**: deletes an existing entry and says so; running
  again (nothing stored) says so too, without erroring.
- A terminal capture of a successful `codehood login` followed by
  `codehood logout`, in the PR.

## Out of scope

- **Server-side revocation.** `codehood logout` only removes the local
  copy — see "Logout deletes locally" above. Tracked as a `codehood-server`
  gap, not fixed here.
- **`--server`/`--login` flags on either command.** Both always resolve
  from the current repository's `codehood.toml` — see "Login and logout
  take no flags" above.
- **`codehood api`'s own browsing screen calling an authenticated
  endpoint.** Its refusal message ("...which `codehood login` doesn't
  support yet") is now slightly stale now that `codehood login` exists,
  but no endpoint in `ENDPOINTS` requires auth yet, so nothing observable
  changes; revisiting that screen's gate is follow-up work for whichever
  spec first adds an authenticated operationId to `ENDPOINTS`.
- **Multiple accounts per server.** One credential per server URL: the CLI
  acts as one person per server, and a second `codehood login` replaces the
  first. It is no longer silent: `login` records the login name beside the
  token (a `[logins]` table, so `[servers]` keeps plain token strings that
  older CLI versions read), prints `replacing the stored login for <url>
  (was <login>)` when a different login, or one stored before names were
  recorded, is overwritten, and `logout` says which login it forgot. Several
  logins per server would need `codehood.toml`'s instructor to select one,
  which also breaks for a student, so it was not worth it.

## Open questions

- **Should `codehood login` refuse to overwrite an existing token for the
  same server without confirmation?** This spec assumes silent overwrite
  is fine (re-running `login` is the obvious fix for "my key stopped
  working"), but nothing currently warns that the old key still exists
  server-side, unrevoked, until `logout`'s server-side gap is closed.
