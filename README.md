# Codehood CLI

This is the command line interface for Codehood. It can be used by instructors 
or students to manage their Codehood projects and assignments.

## Installation

```bash
uv tool install codehood-cli    # or: pipx install codehood-cli
```

It installs two commands, `codehood` and its short alias `ch`. Python 3.13 or
later is required.

To work on the CLI itself, clone the
[Codehood repository](https://github.com/fabiommendes/codehood) with
[mdq](https://github.com/fabiommendes/mdq-spec) checked out next to it:

```bash
git clone https://github.com/fabiommendes/codehood.git
git clone https://github.com/fabiommendes/mdq-spec.git mdq
uv tool install --editable codehood/cli
```


##  For instructors

In Codehood, you manage your course in a local repository, possibly under
version control, and then push changes to the Codehood server. Your local files
are the source of truth, and so you must init the course repository before
anything.

```bash
codehood init
```

It asks for the discipline, your username, the edition and the server, and
creates the following folder structure in your current working directory:

```
├── .local/codehood/
├── questions/
│   └── example.md
├── exams/
│   └── example.md
├── resources/
├── repositories/
├── .gitignore
├── codehood.toml
├── calendar.md
└── README.md
```

Then log in from inside the repository. `codehood login` asks for your
password and stores a CLI key for the server in
`~/.codehood/credentials.toml`, never in `codehood.toml`:

```bash
codehood login
```

For CI and scripts, set `CODEHOOD_TOKEN` to a CLI key instead. When it is set
(and not empty) it is used for every server, and `credentials.toml` is not
read. `codehood login` and `codehood logout` still edit the file, and say that
the variable overrides it.

We manage the course by editing or adding files in the local repository and then
pushing changes to the Codehood server using a simple command:

```bash
codehood push
```

### Two servers, one repository

`--config` (`-c`) reads another file in place of `codehood.toml`, so one
repository can sync with two servers. Keep `codehood.toml` for one and, say,
`codehood.prod.toml` (same `[course]`, another `[server] url`) for the other:

```bash
codehood -c codehood.prod.toml login
codehood -c codehood.prod.toml push
```

The option goes before the command. `CODEHOOD_CONFIG=codehood.prod.toml` does
the same, and `--config` wins when both are set. Only the config file changes:
the repository root is still the current directory (or the `push` path), and
a relative `--config` is relative to the current directory. Tokens are stored
per server URL, so each config uses its own. `codehood -c file init` writes
the config to `file`. To use a second identity on the same server, set
`CODEHOOD_TOKEN`.

### When the server changed

`codehood push` sends only what you changed locally. It compares your files, a
record of the last sync and the server, and never overwrites something that
changed on the server since. It lists those entities and leaves them alone:

- `pull`: something was written on the server by anything but a CLI, such as
  an edit or a creation on the web or through the REST API. Nothing is
  written in your files yet, and the server's version stays.
- `conflict`: you and the server both changed it. The push exits with code 1.
  `codehood push --ours resource/intro` sends your version (`<kind>/<key>`,
  globs allowed, repeatable).
- `other cli`: another checkout pushed it. Run `git pull` first. If the file
  no longer exists anywhere, `--ours <kind>/<key>` deletes it from the server
  (or sends your copy, if you still have it).

The record of the last sync lives in `.local/codehood/`. Push creates it, with
its own `.gitignore`, when it is missing, so Git never lists it, even in a
fresh clone. It is safe to delete: the next push rebuilds it without writing
anything for what matches the server (or carries the hash it last sent). What
differs and has no record is a `conflict`, or a `pull` when only the server
changed it. An entity that exists only on the server and carries a `rev`
shows as `other cli`; `--ours <kind>/<key>` deletes it.


### Keeping files out of a push

Files you do not want on the server (drafts, questions of a type the server
does not support yet) can be excluded in `codehood.toml`:

```toml
[push]
exclude = [
    "questions/wip",            # a directory: everything under it
    "questions/**/draft-*.md",  # ** crosses directories
    "resources/private.md",
]
```

Patterns are relative to the repository root and gitignore-like: `*` and `?`
stay inside one path segment, `**` matches any number of directories, and
there is no `!` negation. They apply to files under `questions/` and
`resources/`. An excluded file is not read, so it may even be invalid. What
the server already holds for it is neither updated nor deleted. `codehood
push` lists excluded files and does not fail because of them.

`.codehoodignore` at the root takes gitignore syntax (with `!`). A match under
`questions/`, `resources/` or `exams/` is treated like an `exclude` pattern:
not pushed, and the server copy is kept. `codehood init` does not create the
file.

`codehood push` reports "not pushed (no handler)" only for files under
`questions/`, `resources/` and `exams/` that it did not read. Anything else
(extra files at the root, folders such as `solutions/`, another tool's config)
is never read and never reported. The report follows git's rules in a git
repository (`.gitignore` at any level, `.git/info/exclude`,
`core.excludesFile`), and the root `.gitignore` only otherwise.


### Linking resources from a lesson

A markdown link in a lesson of `calendar.md` to a file under `resources/`, such
as `[Slides](resources/w03/recursion.pdf)`, attaches that resource to the
lesson's event. On push, the link in the published lesson points to the
resource's page on the server; your local `calendar.md` is not changed. A
resource can belong to at most one lesson, and a link to a file that is not
under `resources/` is an error. Push writes the calendar before the resources.

### Repositories

Each folder directly under `repositories/` is a git repository of the course,
and the folder name is its slug (lowercase letters, digits, `.`, `_` and `-`).
`codehood push` uploads the files and makes one commit per change, and
students clone it from the course page:

```bash
codehood push -m "Fix the lab 1 test"   # -m sets the commit message
```

- `.gitignore` files inside a repository folder apply at every level, `!`
  included, and are published with the repository. The `.gitignore` at the
  course root does not apply. `.git` directories are never published.
- Symlinks, files loose in `repositories/`, files over 16 MB and folders with
  no file to publish are errors. The executable bit is kept (`100755`); on
  Windows every file is `100644`.
- `[push] exclude` patterns also work under `repositories/<slug>/`.
- A repository whose folder is gone stays on the server, because deleting it
  breaks its clone URL and history. `codehood push --drop-repositories`
  deletes it.
- A link in a lesson of `calendar.md` to `repositories/<slug>` or
  `repositories/<slug>/<path>` ties the repository to that lesson. The link
  in the published lesson points to the repository page on the server. A link
  to a repository or path that does not exist is an error.

A student who commits in their clone should update with `git pull
--no-rebase`: recent git versions refuse a plain `git pull` when the local
and the server's branches diverge.


### Final grades

Codehood does not compute a course's final grade. You compute it on your
machine and push the result as grade columns, which the Grades tab shows
beside the exams. Declare the columns in `codehood.toml`, in the order they
should appear:

```toml
[[grades.column]]
slug = "assignments"
title = "Assignments"

[[grades.column]]
slug = "final"
title = "Final grade"
kind = "label"        # "number" is the default
```

Scores you keep outside Codehood go in `grades.csv`, one row per student.
The header of the first column says how students are identified:
`school_id`, `username`, `github` or `email`.

```csv
school_id,assignments
190012345,82.5
190054321,60
```

A column whose slug is a header of `grades.csv` needs nothing else. To
compute one, write a `grade` function in `grades.py`. It is called once per
enrolled student and returns that student's value for each column it
computes:

```python
from codehood.grades import Student

def grade(student: Student) -> dict[str, float | str | None]:
    midterm = student.exams["midterm"].score or 0.0   # 0 to 100, or None
    total = 0.6 * midterm + 0.4 * (student.scores["assignments"] or 0.0)
    return {"final": "pass" if total >= 50 else "fail"}
```

`codehood grades` prints the resulting table without sending anything, and
`codehood push` sends it. A pushed column stays hidden from students until
you release it on the Grades tab.

`grades.py` runs inside the CLI, so it can import the standard library and
whatever is installed beside the CLI. To use another package, install the
CLI with it: `uv tool install --editable codehood/cli --with pandas`.

### Releasing exam grades

Students see the grades of an exam only after you release them:

```bash
codehood exam release midterm
```

The server refuses while the exam is still open, while answers wait for a
grade, or while a student exception keeps a personal window open, and the
command says which and how many. Releasing an exam twice changes nothing.


## For students

TBD!


## Contributing

The CLI is developed in the `cli/` directory of the
[Codehood repository](https://github.com/fabiommendes/codehood). Open issues and
pull requests there. See its
[CONTRIBUTING.md](https://github.com/fabiommendes/codehood/blob/main/CONTRIBUTING.md).


## License

[MIT](LICENSE).
