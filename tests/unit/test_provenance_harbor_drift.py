# ABOUTME: AC-4 — harbor major-version drift is a hard error before Job.create.

from unittest.mock import patch

import pytest

from razorback.provenance.drift import check_harbor_drift
from razorback.provenance.errors import HarborDriftError


def test_no_drift_when_major_matches():
    check_harbor_drift(frozen="0.6.6", installed="0.6.6")
    check_harbor_drift(frozen="0.6.6", installed="0.7.0")
    check_harbor_drift(frozen="0.6.6", installed="0.6.99")


def test_major_drift_raises():
    with pytest.raises(HarborDriftError) as exc_info:
        check_harbor_drift(frozen="0.6.6", installed="1.0.0")
    assert exc_info.value.frozen == "0.6.6"
    assert exc_info.value.installed == "1.0.0"
    assert "0.6.6" in str(exc_info.value)
    assert "1.0.0" in str(exc_info.value)


def test_major_drift_raises_2_to_1():
    with pytest.raises(HarborDriftError):
        check_harbor_drift(frozen="2.0.0", installed="1.5.0")


def test_check_harbor_drift_reads_installed_version_when_not_passed():
    with patch(
        "razorback.provenance.drift._installed_harbor_version", return_value="1.5.0"
    ):
        with pytest.raises(HarborDriftError):
            check_harbor_drift(frozen="0.6.6", installed=None)
