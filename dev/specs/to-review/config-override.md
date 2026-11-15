# Global `--config` override

Every command that reads `codehood.toml` reads it from the repository root
(the current directory, or the `path` argument of `push`, `grades` and
`attendance`). A global `--config`/`-c` option points the CLI at another
file instead, so one course repository can sync with two servers
(`codehood.toml` and `codehood.prod.toml` side by side).

## Scope

- A global option on the Typer app callback: `ch --config FILE <command>`,
  short form `-c`, environment variable `CODEHOOD_CONFIG`.
- Every reader of `codehood.toml` honours it: `push`, `grades`,
  `attendance`, `login`, `logout`, `api` (through `api.base.get_client`'s
  default base URL).
- `init` writes the config to the override path instead of
  `<path>/codehood.toml`. The rest of the scaffold still goes to `path`.

Out of scope:

- Overriding `~/.codehood/credentials.toml`. Tokens are keyed by server URL,
  so a config pointing at another server already uses another token. A second
  identity on the same server uses `CODEHOOD_TOKEN`.
- Repeating the option on each subcommand (`ch push -c x.toml`). It is only
  accepted before the subcommand.

## Design decisions

### Precedence

1. `--config`/`-c`
2. `CODEHOOD_CONFIG` (empty counts as unset)
3. `<root>/codehood.toml`

Typer's `envvar=` on the option gives 1 and 2 for free.

### The override replaces the file, not the root

The repository root stays what it is today: cwd or the `path` argument.
`--config` only changes which TOML is parsed. `ch -c prod.toml push
../course` reads `./prod.toml` and pushes the files under `../course`.

A relative `--config` resolves against the current directory, at parse time,
like any other CLI path. It is not resolved against `path`.

### One resolver

The resolution lives in one function in `codehood/repo/` (suggested:
`repo.config_path(root: Path) -> Path`), returning the override when set and
`root / CONFIG_FILE` otherwise. The override is process state set by the app
callback (`repo.set_config_override(path | None)` or equivalent). Every
caller that today builds `Path(repo.CONFIG_FILE)` or passes a directory to
`RepoConfig.open` goes through the resolver:

- `cli/push.py`, `cli/grades.py`, `cli/attendance.py`: `RepoConfig.open`.
- `cli/auth.py:_repo_config`.
- `api/base.py:_default_base_url`.
- `cli/init.py` / `repo.write_repo`: where `ensure_config` writes.

Module state is acceptable here: it is set once by the imperative shell
before any command runs. The callback must always assign it, `None`
included, so a second invocation in the same process (tests with
`CliRunner`) does not inherit the previous override.

`models.repo` must not import `repo` (`repo` already imports `models`).
`RepoConfig.open` keeps accepting a file or a directory; callers pass the
resolved file.

### Errors

- Override points to a missing file, for a command that reads it: one line
  `error: could not find Codehood config at <path>`, exit 1. Same path as
  today's missing `codehood.toml`.
- `login`/`logout` without a config: the message names the path it looked
  at, not a hard-coded "no codehood.toml here".
- `init` with an override whose parent directory does not exist: create it,
  as `init` already does for `path`.
- `init` with an override that exists and names another course:
  `IdentityConflictError`, as today.

### The push report ignores files outside the pushed trees

A second config in the root (`alt.toml`) would show up as "not pushed (no
handler)". Rather than special-casing config files, the report now covers
only `questions/`, `resources/` and `exams/`: the CLI looks for content in
predictable paths, and anything else in the course is not its business.
`roster.csv` loses its "not synced yet" hint with it.

## Acceptance criteria

1. `ch -c other.toml push --dry-run` reads `other.toml`, ignoring
   `codehood.toml` in the same directory.
2. `CODEHOOD_CONFIG=other.toml ch push --dry-run` behaves like 1.
3. `--config` beats `CODEHOOD_CONFIG` when both are set.
4. `ch -c ./x.toml push sub/` reads `./x.toml` (cwd), not `sub/x.toml`, and
   pushes `sub/`.
5. A missing override file gives the one-line error and exit 1 on `push`,
   `grades`, `attendance`, `login`, `logout`.
6. `ch -c other.toml login` uses `other.toml`'s `[server].url` and stores the
   token under it. `logout` the same.
7. `api.base.get_client()` with no argument uses the override's server URL.
8. `ch -c other.toml init dir ...` writes `other.toml` and no
   `dir/codehood.toml`. A second identical run reports it as `exists`.
9. Two invocations in one process: the second without `-c` reads
   `codehood.toml` again.
10. `ch --help` lists `--config`/`-c` and mentions `CODEHOOD_CONFIG`.

## Verification against the dev server

With the dev server on `localhost:4321`, in a scratch course repo:

- `codehood.toml` with `url = "http://localhost:4321"`, and `alt.toml`, same
  course, `url = "http://127.0.0.1:4321"` (same server, distinct credentials
  key).
- `CODEHOOD_TOKEN=dev-ada-cli ch -c alt.toml push` succeeds against
  `127.0.0.1`.
- Without `CODEHOOD_TOKEN` and with no token stored for `127.0.0.1`,
  `ch -c alt.toml push` fails with `not logged in to http://127.0.0.1:4321`,
  proving the override drove the server choice.

## Docs

- `README.md`, "For instructors": a short section on `--config` with the
  two-servers example.
- `CHANGELOG.md`, "Unreleased": one entry.
