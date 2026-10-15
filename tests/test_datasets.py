from hashlib import sha256
import json
from pathlib import Path
import shutil

import pytest

from ticket_router.datasets import DEFAULT_MANIFEST, describe_cases, load_manifest, select_case

ROOT = Path(__file__).resolve().parents[1]


def test_four_profiles_cover_sixteen_distinct_inputs_with_matching_digests():
    manifest = load_manifest()
    assert manifest.dataset_id == "northstar-support-tickets"
    assert manifest.version == "1.0.0"
    assert {profile.name: len(profile.cases) for profile in manifest.profiles} == {"starter": 2, "busy": 8, "ambiguous": 3, "boundary": 3}
    ids = []
    paths = []
    for profile in manifest.profiles:
        for case in profile.cases:
            ticket, selection = select_case(case.case_id)
            ids.append(ticket.ticket_id)
            paths.append(case.path)
            assert selection.profile == profile.name
            assert selection.source_sha256 == sha256((DEFAULT_MANIFEST.parent / case.path).read_bytes()).hexdigest()
    assert len(set(ids)) == 16
    assert set(paths) == {f"tickets/{path.name}" for path in (ROOT / "data/tickets").glob("*.json")}
    assert describe_cases()["case_count"] == 16


def copied_manifest(tmp_path):
    shutil.copytree(ROOT / "data", tmp_path / "data")
    return tmp_path / "data/manifest.json"


def test_changed_input_cannot_keep_a_qualified_dataset_identity(tmp_path):
    path = copied_manifest(tmp_path)
    source = path.parent / "tickets/ordinary-billing.json"
    source.write_text(source.read_text().replace("$48", "$480"))
    with pytest.raises(ValueError, match="digest mismatch"):
        select_case("starter-receipt", path)


def test_manifest_paths_cannot_escape_the_declared_dataset(tmp_path):
    path = copied_manifest(tmp_path)
    raw = json.loads(path.read_text())
    raw["profiles"][0]["cases"][0]["path"] = "../outside.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="inside its manifest directory"):
        select_case("starter-receipt", path)


def test_duplicate_case_identity_and_missing_profile_are_rejected(tmp_path):
    path = copied_manifest(tmp_path)
    raw = json.loads(path.read_text())
    raw["profiles"][1]["cases"][0]["case_id"] = "starter-receipt"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="unique"):
        load_manifest(path)
    raw["profiles"][1]["name"] = "starter"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="four profiles"):
        load_manifest(path)


def test_unknown_case_is_not_replaced_with_a_default_ticket():
    with pytest.raises(ValueError, match="not found"):
        select_case("missing-case")
