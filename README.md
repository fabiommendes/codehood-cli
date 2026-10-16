# Codehood CLI

This is the command line interface for Codehood. It can be used by instructors 
or students to manage their Codehood projects and assignments.

## Installation

The CLI is not on PyPI yet. Install it from a checkout of the
[Codehood repository](https://github.com/fabiommendes/codehood), with
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

It will create the following folder structure in your current working directory:

```
├── .codehood/
├── questions/
│   └── example.mdq
├── exams/
│   ├── draft/
│   │   └── example.md
│   ├── practice/
│   │   └── example.md
│   └── published/
├── resources/
├── codehood.toml
├── calendar.md
├── roster.csv
└── README.md
```

It will also ask for your credentials to connect to the Codehood server and
storing them in the `codehood.toml` file.

We manage the course by editing or adding files in the local repository and then
pushing changes to the Codehood server using a simple command:

```bash
codehood push
```


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


### Linking resources from a lesson

A markdown link in a lesson of `calendar.md` to a file under `resources/`, such
as `[Slides](resources/w03/recursion.pdf)`, attaches that resource to the
lesson's event. On push, the link in the published lesson points to the
resource's page on the server; your local `calendar.md` is not changed. A
resource can belong to at most one lesson, and a link to a file that is not
under `resources/` is an error. Push writes the calendar before the resources.

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


## For students

TBD!


## Contributing

The CLI is developed in the `cli/` directory of the
[Codehood repository](https://github.com/fabiommendes/codehood). Open issues and
pull requests there. See its
[CONTRIBUTING.md](https://github.com/fabiommendes/codehood/blob/main/CONTRIBUTING.md).


## License

[MIT](LICENSE).
