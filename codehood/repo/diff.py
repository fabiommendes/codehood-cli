import enum
from dataclasses import dataclass
from pathlib import Path


class FileType(enum.IntEnum):
    """
    File by type.
    """

    WARNING = -1
    UNTRACKED = 0
    CONFIG = 1
    README = 2
    ROSTER = 3
    CALENDAR = 4
    QUESTION = 8
    RESOURCE = 16
    EXAM = 32

    def path(self, rel_path: Path | str, /) -> Path:
        """
        Return the relative path to the repo root for a path of the given type.
        """
        return self.base() / rel_path

    def base(self) -> Path:
        """
        The base path (root directory) for each file type in the repo.
        """
        return BASE_PATHS.get(self, Path(""))


BASE_PATHS = {
    FileType.QUESTION: Path("questions"),
    FileType.RESOURCE: Path("resources"),
    FileType.EXAM: Path("exams"),
}


@dataclass(frozen=True)
class AddFile:
    name: str
    type: FileType

    @property
    def path(self):
        return self.type.path(self.name)


@dataclass(frozen=True)
class DeleteFile:
    name: str
    type: FileType

    @property
    def path(self):
        return self.type.path(self.name)


@dataclass(frozen=True)
class UpdateFile:
    name: str
    type: FileType

    @property
    def path(self):
        return self.type.path(self.name)


Diff = AddFile | DeleteFile | UpdateFile
