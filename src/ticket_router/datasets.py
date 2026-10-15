"""Versioned inputs, selected one at a time without starting a model campaign."""

from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from .models import Contract, DatasetSelection, Ticket

MAX_INPUT_BYTES = 128 * 1024
_packaged = Path(__file__).with_name("sample_data") / "manifest.json"
DEFAULT_MANIFEST = _packaged if _packaged.exists() else Path(__file__).resolve().parents[2] / "data/manifest.json"


def read_input(path: Path) -> bytes:
    with path.open("rb") as source:
        content = source.read(MAX_INPUT_BYTES + 1)
    if len(content) > MAX_INPUT_BYTES:
        raise ValueError("JSON input exceeds 128 KiB")
    return content


class Case(Contract):
    case_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Profile(Contract):
    name: Literal["starter", "busy", "ambiguous", "boundary"]
    cases: list[Case] = Field(min_length=1)


class Manifest(Contract):
    dataset_id: str = Field(min_length=1)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    profiles: list[Profile]

    @model_validator(mode="after")
    def unique_population(self):
        if sorted(profile.name for profile in self.profiles) != ["ambiguous", "boundary", "busy", "starter"]:
            raise ValueError("Manifest needs each of the four profiles exactly once")
        ids = [case.case_id for profile in self.profiles for case in profile.cases]
        paths = [case.path for profile in self.profiles for case in profile.cases]
        if len(ids) != len(set(ids)) or len(paths) != len(set(paths)):
            raise ValueError("Case IDs and source paths must be unique across profiles")
        return self


def _ticket(root: Path, case: Case) -> Ticket:
    path = (root / case.path).resolve()
    if not path.is_relative_to(root) or path.suffix != ".json":
        raise ValueError("Dataset input must be a JSON file inside its manifest directory")
    content = read_input(path)
    if sha256(content).hexdigest() != case.sha256:
        raise ValueError(f"Dataset digest mismatch for {case.case_id}; qualify a new dataset version")
    return Ticket.model_validate_json(content)


def load_manifest(path: Path = DEFAULT_MANIFEST) -> Manifest:
    return Manifest.model_validate_json(read_input(path))


def select_case(case_id: str, path: Path = DEFAULT_MANIFEST) -> tuple[Ticket, DatasetSelection]:
    manifest = load_manifest(path)
    for profile in manifest.profiles:
        for case in profile.cases:
            if case.case_id == case_id:
                ticket = _ticket(path.parent.resolve(), case)
                return ticket, DatasetSelection(dataset_id=manifest.dataset_id, version=manifest.version,
                    profile=profile.name, case_id=case.case_id, source_sha256=case.sha256)
    raise ValueError(f"Dataset case not found: {case_id}")


def describe_cases(path: Path = DEFAULT_MANIFEST) -> dict:
    manifest = load_manifest(path)
    for profile in manifest.profiles:
        for case in profile.cases:
            _ticket(path.parent.resolve(), case)
    return {"dataset_id": manifest.dataset_id, "version": manifest.version,
            "case_count": sum(len(profile.cases) for profile in manifest.profiles),
            "profiles": [{"name": profile.name, "case_ids": [case.case_id for case in profile.cases]}
                         for profile in manifest.profiles]}
