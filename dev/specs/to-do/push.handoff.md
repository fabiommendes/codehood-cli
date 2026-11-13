# Handoff: `codehood push` (slice 1 — course + resources)

Spec: `dev/specs/to-do/push.md`. Read it first; this is the API contract and
task split, not a restatement.

## Goal

`codehood push` PUTs the course row and syncs `resources/` (MD/CODE only —
FILE is planned, not executed; LINK is out of scope). No local state.

## Public API

New package `codehood/push/`.

### `codehood/push/plan.py` — pure core

```python
@dataclass(frozen=True)
class UpsertCourse:
    discipline: str
    course: str            # "{instructor}_{edition}"
    description: str
    start_at: str
    end_at: str

@dataclass(frozen=True)
class UpsertResource:
    slug: str
    type: Literal["MD", "CODE", "FILE"]
    title: str
    description: str | None
    data: str | None       # MD/CODE body; None for FILE
    extra: str | None      # CODE language; None otherwise
    blob: bytes | None     # FILE bytes; None for MD/CODE
    content_hash: str
    path: Path              # source file, for reporting/upload

@dataclass(frozen=True)
class DeleteResource:
    slug: str

PushOp = UpsertCourse | UpsertResource | DeleteResource

def plan_push(
    discipline: str,
    course: str,                            # "{instructor}_{edition}"
    readme_text: str,
    edition_dates: tuple[str, str],       # (start_at, end_at)
    resources: Iterable[ResourceFile],     # from push/resource.py
    server_course_exists: bool,
    server_resources: Mapping[str, str],   # slug -> contentHash
) -> Iterator[PushOp]: ...
```

Correction: `discipline`/`course` are required leading params — they're the
only source for `UpsertCourse.discipline`/`.course`, missing from the first
draft.

No client, no ids, no `run()` — matches the spec's `PushOp` union exactly.
`plan_push` doesn't reach the network itself; the shell fetches
`server_course_exists` (`read_course` catching a 404) and `server_resources`
(`list_resource`, projected to `{slug: contentHash}`) and passes them in.

### `codehood/push/resource.py` — pure core

```python
@dataclass(frozen=True)
class ResourceFile:
    slug: str
    type: Literal["MD", "CODE", "FILE"]
    title: str
    description: str | None
    data: str | None
    extra: str | None
    blob: bytes | None
    content_hash: str
    path: Path

def slugify(rel_path: Path) -> str: ...

def content_hash(
    type: Literal["MD", "CODE", "FILE"],
    title: str,
    description: str | None,
    data: str | None,
    extra: str | None,
    file_hash: str | None,
) -> str: ...

def scan_resources(root: Path) -> Iterator[ResourceFile]: ...
```

`scan_resources` walks `resources/` recursively (reuses the fixed
`repo/file_tracker.scan_files` for the walk), infers type from extension,
extracts title/description from MD front matter, and raises
`SlugCollisionError` if two files flatten to the same slug — eagerly, before
any network call.

### `codehood/push/errors.py`

```python
class SlugCollisionError(Exception):
    def __init__(self, collisions: Mapping[str, list[Path]]): ...
```

Correction: the committed OpenAPI spec only documents a 200 response for
`PUT /api/course/{discipline}/{course}`, so `generated.upsert_course` hits
`response.raise_for_status()` on a 404 and raises `httpx.HTTPStatusError`,
not a `CodehoodAPIError` subclass. `run_plan` must catch broadly
(`httpx.HTTPStatusError` and `CodehoodAPIError`) per op and yield a failed
`OpResult` instead of letting it propagate — this is required
because a sync is not atomic ("remaining operations still run" after a
failure), not optional polish.

### `codehood/push/run.py` — imperative shell

```python
@dataclass(frozen=True)
class OpResult:
    op: PushOp
    ok: bool
    message: str

def fetch_server_state(
    discipline: str, course: str, client: httpx.Client
) -> tuple[bool, Mapping[str, str]]: ...   # (course exists, slug -> contentHash)

def run_plan(
    ops: Iterable[PushOp], *, discipline: str, course: str, client: httpx.Client
) -> Iterator[OpResult]: ...
```

`run_plan` is the only thing in the package touching HTTP. A `FILE`
`UpsertResource` yields `OpResult(ok=False, message="blocked: ...")` without
calling anything (ROADBLOCKS.md item 1).

## Other changes

- `repo/_layout.py`: fix `render_readme` docstring — description is local
  only, never sent as the course name.
- `repo/file_tracker.py`: `scan_files`' resource glob recurses and skips
  directories (currently yields subdirs as resources — bug).
- Delete `repo/history.py`; drop the `history` param from `find_diffs`
  (unused outside its own module — verified, no other caller).
- `cli/push.py`: rewrite per the CLI surface below.
- `pyproject.toml`: move `pyyaml` from the `dev` group to `dependencies`
  (needed at runtime for front-matter parsing, currently test-only).

## CLI surface

Per spec: `codehood push [PATH] [--dry-run] [--no-prune]`, one output line
per op, exit 0 iff every executed op succeeded, failures don't stop the run.

## Testing strategy

- **Property**: convergence — `plan_push` → apply against a fake in-memory
  server state → `plan_push` again → second plan is empty. Hypothesis
  generates resource trees (paths, extensions, content) and a fake prior
  server state.
- **Table-driven**: `slugify` (including the two collision examples from the
  spec) and `content_hash` (a hand-computed vector, cross-checked once
  against the dev server's returned `contentHash` in the e2e test).
- **Named errors**: collision, missing discipline, missing edition each get
  one unit test asserting the specific exception, not a traceback.
- **CLI**: `CliRunner`, mirroring `test_cli_init.py` — `--dry-run` makes no
  writes, `--no-prune` reports deletions without executing them, exit codes.
- **E2E** (`pytest.mark.integration`, skipped if `localhost:4321` is down,
  mirroring `test_api_integration.py`): `init` → push → resource visible →
  delete local file → push → resource gone. MD/CODE only.

## Acceptance criteria

- Pushing a fresh course creates it; pushing again updates it, never fails
  on "already exists".
- `resources/` converges: added/changed/removed files map 1:1 to
  upsert/delete ops, nothing else.
- Colliding slugs refuse the whole push and name every contending file.
- Missing discipline/edition fails with a clear message, no traceback.
- `--dry-run` performs zero writes; `--no-prune` performs zero deletes.
- Re-running push against unchanged state plans nothing.

Handoff document: `dev/specs/to-do/push.handoff.md`
