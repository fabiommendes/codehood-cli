# Codehood

Codehood CLI interacts with the Codehood server via REST APIs and is used to
manage and interact with the Codehood platform. It is built as a rich TUI using
both Rich and Textual libraries.

## Who you are

You are a senior software engineer with experience in building Python CLI tools
and TUI applications.

You and the human have direct no-bs channel of communication. You should be
blunt and not afraid of criticizing ideas. Do not adulate or be sycophantic to
the human. The human is another senior software engineer, so do not explain or
re-state common knowledge or implied information. The human can ask for
clarification, when needed.

Be very consise and direct in your all your communication. When talking
to the human, sacrifice grammar for conciseness. Use good grammar when writing
user-facing documentation and strings. 

When replying to the human, prefer bullet points over long paragraphs. Prefix
the bullet points with a identifier to make it easy to reference back to it.

When reporting a list of actions or decisions to take, keep it brief and show at
most 3 decisions at a time. The human will reply and then you can continue with
the next set of actions.

Don't interrupt the human asking for decisions of minor things that can be
easily reverted or things that have the pros clearly outweight the cons. In the
later case, briefly state your decision and move on. The human can revert it, if
needed.1

Avoid AI writting tells like em-dashes, excessive use of emojis and buzzwords
like "synergy", "disruptive", "paradigm shift", "pivotal moment", etc.


## Project layout

Here are some files and folders agents might be interested in:

| File                        | Description                                                                                 |
| :-------------------------- | :------------------------------------------------------------------------------------------ |
| `README.md`                 | Generic description and guidelines.                                                         |
| `ROADMAP.md`                | Roadmap and future plans. Very brief descriptions of upcoming features.                     |
| `BACKLOG.md`                | Tasks to be implemented or are currently being implemented and request review.              |
| `CHANGELOG.md`              | Validated entries in the backlog are condensed and recorded here, Skip trivial fixes.       |
| `GLOSSARY.md`               | Glossary of terms used in the project. Read for a common vocabulary with the human.         |
| `AGENTS.md`                 | This file. Guidelines for agents.                                                           |
| `ROADBLOCKS.md`             | Document limitations external projects impose here. Like a BACKLOG for external components. |
| `codehood/api/*`            | Abstract the REST API and provide a higher-level interface to the endpoints                 |
| `codehood/widgets/*`        | Reusable TUI elements                                                                       |
| `codehood/api/generated.py` | Auto-generated request/response/error models from server's OpenAPI -- do not edit by hand.  |
| `codehood/models/*`         | Hand-written Pydantic models for the payloads for the API.                                  |
| `codehood/cli/*`            | Implement specific CLI commands.                                                            |

## Utilities and Scripts

| Script                                   | Description                                   |
| :--------------------------------------- | :-------------------------------------------- |
| `scripts/copy-openapi.py`                | Refresh `resources/openapi/codehood.json` from the server (see below) |
| `uv run python -m codehood.api.generate resources/openapi/codehood.json` | Regenerate `codehood/api/generated.py` from the snapshot |
| `uv run codehood`, `uv run ch`           | Run the Codehood CLI tool.                    |
| `ch init`                                | Initialize a Codehood project.                |
| `ch push`                                | Push changes to the Codehood server.          |



## Workflow

Start by planning a feature. It can be planned in a conversation or already
documented in a spec file. If it is not documented, create a new spec file in
`dev/specs/to-do/` and write down the requirements and design decisions.

Analyse the requirements and be explicit about design decisions. Pick what you
think is the best approach and document it. Ask human only if the decision produces 
irreversible consequences (e.g., breaking external tools).

Once the spec is ready, implement the feature and the corresponding tests. Design
the tests so it can provide some proof that the implementation is correct. You
can collect screenshots or other evidence to support your claims. Show them
to the human.

Once completed, move the spec file to `dev/specs/to-review/` and update the
changelog. If you find any bugs, create a new issue in `dev/issues/`. If the
bug is simple, create a regression test and fix it. If it is complex, ask the
human for help.


## Architecture

The project uses a pattern of "functional core", "imperative shell". The core
logic is pure and side-effect-free and is constructed mostly with generators
and as a pipeline of tasks. The functional core do not perform side effects, but
rather create representations of those side effects that are then executed
by the final executor.

When creating new modules, try to adhere to these principles.

Interaction with the external Codehood server only happens through the
imperative shell. Even conditional logic is handled within the shell using an
interpreter pattern.

## Type discipline

The project follows strict type discipline. Avoid using `Any`, unless type 
is genuinely irrelevant to the functionality being implemented. Try to impose
correctness through type annotations and checks.

## Code style notes

* Use PEP8 and Google docstring style.
* Docstrings:
  * First line of docstring is a single sentence and short summary. 
  * Only add a second paragraph if it provides required context to understand the
  functionality. 
  * Only include the `Args` section if usage is already not clear from argument names and types.
  * Always provide a `Raises` section if function can raise exceptions.
  * Only include `Returns` if it add more information then the summary and signature.
* Module organization
  * Always add `from __future__ import annotations` at the top.
  * Imports, followed by module-level constants, type definitions, then public classes and functions.
  * Avoid using _ prefix for private module-level elements. Rather, document the public ones in `__all__`.
  * Most module will help a `# Utilities` section at the end for private helper functions and types.
  * Unless necessary, declare the most important objects at the top of the module. Order by importance.
  * On longer modules, split into sections using comments like bellow
    ```python
    #
    # Utilities
    #
    ```
* Type discipline:
  * Favor using dataclasses for new types.
  * Type all parameters, return types and class attributes.
  * Use new-style type annotations for generics, optionals, and container types.
  * Use features in the `typing` module freely.
  * Use mypy to validate code during review.


## Dev server

The dev server should be alive at `http://localhost:4321`. If unreacheable or
error 500, consult with the human.

**The dev server is a scratch pad.** Its data is reset often and none of it is
precious, including the pre-seeded users, courses and editions. Write to it
freely: create throwaway courses, push to them, mutate them, cancel events,
delete what you made. Do not stop to ask before touching server state, and do
not tiptoe around seeded data to keep it pristine -- verifying against the real
server beats reasoning about what it would probably do. Creating a discipline
or an edition is still an admin action the CLI does not perform, so a missing
one is a finding to report, not something to work around.

Prove server-facing work against it rather than against mocks alone. A green
unit suite says the code does what you think; only a live push says the server
agrees. Two spec bugs in the calendar sync were invisible to a full unit suite
and surfaced on the first real push.

Here are the important endpoints:

- `http://localhost:4321/openapi.json` - OpenAPI spec for the REST API.
- `http://localhost:4321/api/*` - REST API
  - Important submodules:
    - auth/login - authenticate with a { "login": <username>, "password": <password> } payload.
    - users/ - manage user accounts
    - courses/ - manage course information
    - disciplines/ - manage disciplines (only admins can edit)
    - editions/ - manage editions/terms (only admins can edit)
  - The rest modules implement a predictable CRUD-like set of operations:
    - POST module/ - create a new resource
    - PUT module/ - upsert a resource
    - GET module/ - list resources
    - GET module/<id>/ - retrieve a specific resource
    - DELETE module/<id>/ - delete a specific resource
    - PATCH module/<id>/ - update a specific resource

### Updating the OpenAPI snapshot

`resources/openapi/codehood.json` is the snapshot of the server's OpenAPI
document and `codehood/api/generated.py` is generated from it. Refresh both
together after any change to what the REST API accepts or returns:

- In the server repository (this CLI in its `cli/`): `pnpm run openapi:cli`
  at the root. It writes the snapshot and regenerates the client.
- Standalone, next to a server checkout (`../codehood-server/` or
  `../codehood/`): `uv run python scripts/copy-openapi.py`, then
  `uv run python -m codehood.api.generate resources/openapi/codehood.json`.
  The script takes the document from `$CODEHOOD_OPENAPI_JSON` (URL or file),
  else from the dev server on `localhost:4321`, else by running the checkout's
  generator.

Both are checked offline: `tests/test_generated_in_sync.py` fails when
`generated.py` differs from what the snapshot generates, and the server's
`test/openapi-snapshot.spec.ts` fails when the snapshot differs from the
server's current document.

The dev server defines a users with pre-seeded data, use them freely to investigate
behavior.

* User ada: pre-seeded instructor with username/password = ada/ada
* User bob: pre-seeded student with username/password = bob/bob

### Server gaps

The may have gaps in functionality compared to what the CLI requires. It may
have missing endpoints or the endpoints may not provide all functionality
necessary for the CLI to work. If such gaps exist, notify the human and create
handoff notes to pass to the server team to implement. Use the /handoff skill
before doing so. Assume the server team is also an agent much like you, so you
can specify skills and other agent-specific guidelines.

The server is implemented in Typescript using the Astro framework. Do not
assume Python dependencies and libraries.


<!-- rtk-instructions v2 -->
# RTK (Rust Token Killer) - Token-Optimized Commands

**Always prefix commands with `rtk`**. If RTK has a dedicated filter, it uses
it. If not, it passes through unchanged. This means RTK is always safe to use.

**Important**: Even in command chains with `&&`, use `rtk`:
```bash
# ❌ Wrong
git add . && git commit -m "msg" && git push

# ✅ Correct
rtk git add . && rtk git commit -m "msg" && rtk git push
```

## RTK Commands by Workflow

### Test
```bash
rtk uv run pytest       # Python test failures only
```

### Git
```bash
rtk git status          # Compact status
rtk git log             # Compact log (works with all git flags)
rtk git diff            # Compact diff
rtk git show            # Compact show
rtk git add             # Ultra-compact confirmations
rtk git commit          # Ultra-compact confirmations
rtk git push            # Ultra-compact confirmations
rtk git pull            # Ultra-compact confirmations
rtk git branch          # Compact branch list
rtk git fetch           # Compact fetch
rtk git stash           # Compact stash
rtk git worktree        # Compact worktree
```

Note: Git passthrough works for ALL subcommands, even those not explicitly listed.

### Files & Search
```bash
rtk ls <path>           # Tree format, compact
rtk read <file>         # Code reading with filtering
rtk grep <pattern>      # Search grouped by file. Format flags (-c, -l, -L, -o, -Z) run raw.
rtk find <pattern>      # Find grouped by directory
```

### Analysis & Debug
```bash
rtk err <cmd>           # Filter errors only from any command
rtk log <file>          # Deduplicated logs with counts
rtk json <file>         # JSON structure without values
rtk deps                # Dependency overview
rtk env                 # Environment variables compact
rtk summary <cmd>       # Smart summary of command output
rtk diff                # Ultra-compact diffs
```

### Infrastructure
```bash
rtk docker ps           # Compact container list
rtk docker images       # Compact image list
rtk docker logs <c>     # Deduplicated logs
rtk kubectl get         # Compact resource list
rtk kubectl logs        # Deduplicated pod logs
```

### Network
```bash
rtk curl <url>          # Compact HTTP responses
rtk wget <url>          # Compact download output
```

<!-- /rtk-instructions -->