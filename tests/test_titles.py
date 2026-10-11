"""Module 3: friendly titles for manifest-doctor's codes (drafts, for Georgi's review)."""

import sys
from pathlib import Path

import pytest

from delivery_desk_app import titles

DOCTOR = Path(__file__).resolve().parents[2] / "delivery-verify"


def doctor_codes():
    sys.path.insert(0, str(DOCTOR))
    from manifest_doctor.findings import DEFAULT_SEVERITY
    return set(DEFAULT_SEVERITY)


@pytest.mark.skipif(not (DOCTOR / "manifest_doctor").is_dir(), reason="manifest-doctor not next to the app")
def test_every_finding_code_manifest_doctor_has_gets_a_title_and_one_category():
    for code in doctor_codes():
        assert titles.title(code) != code, code
        assert sum(code in c["codes"] for c in titles.CATEGORIES) == 1, code


def test_every_probable_cause_gets_a_title():
    for code in ("CAUSE_WRAPPER_FOLDER", "CAUSE_UNICODE_FORM", "CAUSE_CASE_ONLY", "CAUSE_DUPLICATE_LISTING",
                 "CAUSE_HIDDEN_NOISE"):
        assert titles.title(code) != code


def test_a_code_the_app_doesnt_know_yet_is_shown_as_the_code_itself():
    assert titles.title("SOMETHING_NEW") == "SOMETHING_NEW"


def test_the_all_clear_list_counts_findings_per_category():
    counted = titles.count_by_category([{"code": "MISSING"}, {"code": "MISSING"}, {"code": "HIDDEN_FILE"}])
    as_dict = {c["label"]: c["count"] for c in counted}
    assert as_dict["Files missing from the folder"] == 2
    assert as_dict["Hidden system files"] == 1
    assert as_dict["Empty (zero-byte) files"] == 0
