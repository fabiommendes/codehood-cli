"""
Tests for `codehood.push.resource`: the pure core that turns `resources/`
into `ResourceFile`s. See `dev/specs/to-do/push.md`, "A resource's slug is
its flattened path under `resources/`" and "Type is inferred from the
extension", and `dev/specs/to-do/push.handoff.md`'s `push/resource.py`
section.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from codehood.push.errors import ResourceFileError, SlugCollisionError
from codehood.push.resource import (
    REF_PREFIX,
    CodeData,
    FileData,
    LinkData,
    MdData,
    content_ref,
    scan_resources,
    slugify,
    slugify_text,
    title_from_filename,
)

#
# slugify
#
SLUGIFY_CASES = [
    # The spec's own worked example.
    ("week1/Slides (final).pdf", "week1-slides-final"),
    # Each half of the spec's two collision examples, on its own.
    ("week1/slides.pdf", "week1-slides"),
    ("week1/slides.md", "week1-slides"),
    ("week1-slides.md", "week1-slides"),
    # Path separators and punctuation both collapse to a single '-', and
    # the result is trimmed, not left with a trailing dash.
    ("Week 1/My File!!.md", "week-1-my-file"),
    # Accents drop the way the server's `src/utils/slugify.ts` drops them.
    ("laços/passos-do-range.md", "lacos-passos-do-range"),
    ("classes/herança.md", "classes-heranca"),
    ("condicionais/condição-dupla.md", "condicionais-condicao-dupla"),
    ("Érico Veríssimo.pdf", "erico-verissimo"),
    # NFKD does not decompose these, and the server does not transliterate.
    ("straße.md", "stra-e"),
    ("smørrebrød.md", "sm-rrebr-d"),
]


@pytest.mark.parametrize("rel_path, expected", SLUGIFY_CASES)
def test_slugify(rel_path: str, expected: str) -> None:
    assert slugify(Path(rel_path)) == expected


def test_slugify_two_different_source_paths_collide_on_the_same_slug():
    """
    The spec's first collision example: `week1/slides.md` and
    `week1-slides.md` are different files that flatten to the same slug.
    """
    assert slugify(Path("week1/slides.md")) == slugify(Path("week1-slides.md"))


def test_slugify_extension_alone_does_not_disambiguate():
    """
    The spec's second collision example: `week1/slides.pdf` and
    `week1/slides.md` differ only in extension, which slugify drops.
    """
    assert slugify(Path("week1/slides.pdf")) == slugify(Path("week1/slides.md"))


#
# content_ref
#
# `ref` is a free-form string the server stores and returns untouched, so
# this recipe is the CLI's alone: sha256 hex of the JSON serialisation of
# {v, title, description, data}, keys sorted, no whitespace, prefixed by
# the recipe version. A `FILE`'s bytes enter as their own sha256.
def _vector(title, description, data) -> str:
    payload = json.dumps(
        {"v": REF_PREFIX, "title": title, "description": description, "data": data},
        separators=(",", ":"),
        sort_keys=True,
        ensure_ascii=False,
    )
    return f"{REF_PREFIX}:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


CONTENT_REF_CASES = [
    (
        "Hello",
        None,
        MdData(content="# Hello\n\nBody text.\n"),
        {"type": "MD", "content": "# Hello\n\nBody text.\n"},
    ),
    (
        "main.py",
        "A script",
        CodeData(content="print(1)\n", language="python"),
        {"type": "CODE", "content": "print(1)\n", "language": "python"},
    ),
    (
        "slides.pdf",
        None,
        FileData(filename="slides.pdf", blob=b"%PDF\n"),
        {
            "type": "FILE",
            "filename": "slides.pdf",
            "blob": hashlib.sha256(b"%PDF\n").hexdigest(),
        },
    ),
]


@pytest.mark.parametrize("title, description, data, payload", CONTENT_REF_CASES)
def test_content_ref_matches_hand_computed_vector(title, description, data, payload):
    assert content_ref(title, description, data) == _vector(title, description, payload)


def test_content_ref_distinguishes_absent_from_empty_string():
    """
    `null` (absent) and `""` (present-but-empty) serialise differently, so
    they must not hash the same -- a resource with no description is not
    the same content as one with an empty one.
    """
    data = MdData(content="d")
    assert content_ref("t", None, data) != content_ref("t", "", data)


def test_content_ref_distinguishes_types_holding_the_same_text():
    """
    The tag is part of the payload, so the same text pushed as Markdown
    and as code are two different resources.
    """
    md = content_ref("t", None, MdData(content="x"))
    code = content_ref("t", None, CodeData(content="x", language="python"))
    assert md != code


def test_content_ref_tracks_a_file_s_bytes_not_just_its_name():
    same_name = FileData(filename="a.pdf", blob=b"one")
    changed = FileData(filename="a.pdf", blob=b"two")
    assert content_ref("t", None, same_name) != content_ref("t", None, changed)


#
# scan_resources
#
def _write(root: Path, rel: str, text: str) -> Path:
    path = root / "resources" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_scan_resources_recurses_and_skips_directories(tmp_path):
    """
    `scan_resources` walks subdirectories -- the bug in the current
    `file_tracker` glob (yielding subdirectories as resources) does not
    reappear here.
    """
    _write(tmp_path, "week1/slides.md", "# Slides\n\nBody.\n")
    (tmp_path / "resources" / "week2").mkdir(parents=True)

    resources = list(scan_resources(tmp_path))
    slugs = {r.slug for r in resources}
    assert slugs == {"week1-slides"}


def test_scan_resources_md_title_from_front_matter(tmp_path):
    _write(
        tmp_path,
        "week1/slides.md",
        "---\ntitle: Real Title\ndescription: A real description\n---\n\nBody text.\n",
    )
    [resource] = list(scan_resources(tmp_path))
    assert isinstance(resource.data, MdData)
    assert resource.title == "Real Title"
    assert resource.description == "A real description"
    assert "---" not in resource.data.content
    assert "Body text." in resource.data.content


def test_scan_resources_md_title_falls_back_to_first_h1(tmp_path):
    _write(tmp_path, "week1/slides.md", "# The Real Title\n\nBody text.\n")
    [resource] = list(scan_resources(tmp_path))
    assert resource.title == "The Real Title"
    assert resource.description is None


def test_scan_resources_md_title_falls_back_to_the_title_cased_filename(tmp_path):
    _write(tmp_path, "week1/slides.md", "Just a paragraph, no heading.\n")
    [resource] = list(scan_resources(tmp_path))
    assert resource.title == "Slides"


@pytest.mark.parametrize(
    "stem, expected",
    [
        ("janela-minima", "Janela Minima"),
        ("bola_jogavel", "Bola Jogavel"),
        ("bigONotation", "Big O Notation"),
        ("slides-PDF", "Slides PDF"),
        ("HTTPServer", "HTTP Server"),
        ("aula 01", "Aula 01"),
    ],
)
def test_title_from_filename(stem: str, expected: str) -> None:
    assert title_from_filename(stem) == expected


def test_scan_resources_code_and_file_titles_fall_back_to_the_title_cased_filename(
    tmp_path,
):
    _write(tmp_path, "w1/janela-minima.py", "print(1)\n")
    _write(tmp_path, "w1/paleta_oficial.png", "png")
    titles = {r.slug: r.title for r in scan_resources(tmp_path)}
    assert titles == {
        "w1-janela-minima.py": "Janela Minima",
        "w1-paleta_oficial.png": "Paleta Oficial",
    }


def test_slugify_text_matches_the_server_on_free_text():
    assert slugify_text("Herança Múltipla") == "heranca-multipla"


def test_scan_resources_infers_code_type_and_language(tmp_path):
    _write(tmp_path, "week1/solution.py", "print('hi')\n")
    [resource] = list(scan_resources(tmp_path))
    assert resource.data == CodeData(content="print('hi')\n", language="python")


def test_scan_resources_infers_file_type_for_unknown_extension(tmp_path):
    _write(tmp_path, "week1/slides.pdf", "%PDF-not-really-a-pdf\n")
    [resource] = list(scan_resources(tmp_path))
    assert resource.data == FileData(
        filename="slides.pdf", blob=b"%PDF-not-really-a-pdf\n"
    )


def test_scan_resources_ref_is_deterministic(tmp_path):
    """
    Two scans of an untouched repository must agree, or `plan_push` reads
    every resource as changed and pushes the whole course every time.
    """
    _write(tmp_path, "week1/slides.md", "# Slides\n\nBody.\n")
    first = list(scan_resources(tmp_path))
    second = list(scan_resources(tmp_path))
    assert first[0].ref == second[0].ref


#
# SlugCollisionError
#
def test_collision_week1_slides_md_vs_flattened_sibling(tmp_path):
    """The spec's first collision example."""
    _write(tmp_path, "week1/slides.md", "# A\n")
    _write(tmp_path, "week1-slides.md", "# B\n")

    with pytest.raises(SlugCollisionError) as excinfo:
        list(scan_resources(tmp_path))

    collisions = excinfo.value.collisions
    assert set(collisions) == {"week1-slides"}
    # Paths relative to `resources/` -- what `scan_resources` walked, not
    # an absolute filesystem path a temp directory would make brittle.
    assert set(collisions["week1-slides"]) == {
        Path("week1/slides.md"),
        Path("week1-slides.md"),
    }


def test_week1_slides_pdf_and_week1_slides_md_are_two_resources(tmp_path):
    """Only Markdown drops its extension, so a page and its PDF coexist."""
    _write(tmp_path, "week1/slides.pdf", "%PDF\n")
    _write(tmp_path, "week1/slides.md", "# B\n")
    slugs = sorted(r.slug for r in scan_resources(tmp_path))
    assert slugs == ["week1-slides", "week1-slides.pdf"]


def test_collision_of_names_that_differ_only_in_punctuation(tmp_path):
    _write(tmp_path, "week1/Slides (final).pdf", "%PDF\n")
    _write(tmp_path, "week1/slides-final.PDF", "%PDF\n")

    with pytest.raises(SlugCollisionError) as excinfo:
        list(scan_resources(tmp_path))
    assert set(excinfo.value.collisions) == {"week1-slides-final.pdf"}


def test_collision_is_raised_eagerly_before_any_valid_resource_is_used(tmp_path):
    """
    A collision refuses the *whole* push, not a partial one -- scanning
    must not yield any resource for a slug outside the collision either,
    since the generator is expected to raise rather than silently skip.
    """
    _write(tmp_path, "week1/slides.md", "# A\n")
    _write(tmp_path, "week1-slides.md", "# B\n")
    _write(tmp_path, "week2/notes.md", "# Notes\n")

    with pytest.raises(SlugCollisionError):
        list(scan_resources(tmp_path))


#
# .url files: LINK
#
def test_scan_resources_reads_a_url_file_as_a_link_titled_by_its_comments(tmp_path):
    _write(
        tmp_path,
        "w1/docs.url",
        "# Pyxel docs\n#  The official README.  \n#\n# With examples.\n"
        "https://github.com/kitao/pyxel\nhttps://ignored.example\n",
    )
    [resource] = list(scan_resources(tmp_path))
    assert resource.data == LinkData(url="https://github.com/kitao/pyxel")
    assert resource.title == "Pyxel docs"
    assert resource.description == "The official README.\nWith examples."
    assert resource.ref == content_ref(
        "Pyxel docs", "The official README.\nWith examples.", resource.data
    )


def test_scan_resources_url_file_without_comments_uses_the_filename(tmp_path):
    _write(tmp_path, "w1/formato-json.url", "https://docs.python.org/3/\n")
    [resource] = list(scan_resources(tmp_path))
    assert (resource.title, resource.description) == ("Formato Json", None)


@pytest.mark.parametrize(
    "text, reason",
    [
        ("# Only a title\n", "no URI"),
        ("javascript:alert(1)\n", r"not an http\(s\) URL"),
    ],
)
def test_scan_resources_refuses_a_url_file_with_no_http_uri(tmp_path, text, reason):
    _write(tmp_path, "w1/bad.url", text)
    with pytest.raises(ResourceFileError, match=reason):
        list(scan_resources(tmp_path))


#
# info.yaml
#
def test_info_yaml_is_metadata_and_overrides_titles_and_descriptions(tmp_path):
    _write(tmp_path, "w1/notes.md", "---\ntitle: From front matter\n---\nBody\n")
    _write(tmp_path, "w1/janela.png", "png")
    _write(tmp_path, "w2/other.png", "png")
    _write(
        tmp_path,
        "w1/info.yaml",
        "notes.md:\n  title: From info\n"
        "janela.png:\n  title: Janela do Pyxel\n  description: Primeira janela.\n",
    )
    resources = {r.slug: r for r in scan_resources(tmp_path)}
    assert set(resources) == {"w1-notes", "w1-janela.png", "w2-other.png"}
    assert resources["w1-notes"].title == "From info"
    assert resources["w1-janela.png"].title == "Janela do Pyxel"
    assert resources["w1-janela.png"].description == "Primeira janela."
    # Another folder's info.yaml does not reach here.
    assert resources["w2-other.png"].title == "Other"


def test_info_yaml_language_forces_code_and_mime_forces_file(tmp_path):
    _write(tmp_path, "w1/rules.txt", "fact(1).\n")
    _write(tmp_path, "w1/game.html", "<canvas></canvas>\n")
    _write(
        tmp_path,
        "w1/info.yaml",
        "rules.txt:\n  language: prolog\ngame.html:\n  mime: text/html\n",
    )
    resources = {r.slug: r for r in scan_resources(tmp_path)}
    assert resources["w1-rules.txt"].data == CodeData(
        content="fact(1).\n", language="prolog"
    )
    assert resources["w1-game.html"].data == FileData(
        filename="game.html", blob=b"<canvas></canvas>\n"
    )


@pytest.mark.parametrize(
    "text, reason",
    [
        ("- a\n- b\n", "expected a mapping of file names"),
        ("notes.md: just a string\n", "expected a mapping"),
        ("notes.md:\n  titel: typo\n", "unknown keys titel"),
        ("notes.md:\n  title: [a, b]\n", "values must be strings"),
        ("ghost.md:\n  title: Gone\n", "no such file"),
        ("notes.md: [unclosed\n", "not valid YAML"),
    ],
)
def test_info_yaml_malformed_stops_the_scan(tmp_path, text, reason):
    _write(tmp_path, "w1/notes.md", "Body\n")
    _write(tmp_path, "w1/info.yaml", text)
    with pytest.raises(ResourceFileError, match=reason):
        list(scan_resources(tmp_path))
