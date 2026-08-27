"""Tests for the quality gate."""

import pytest

from dvf.data.quality import CleaningReport, DataQualityError, check_quality


def test_survival_rate_is_a_ratio() -> None:
    report = CleaningReport(raw_rows=1000, kept_sales=250)
    assert report.survival_rate == 0.25


def test_survival_rate_does_not_divide_by_zero() -> None:
    report = CleaningReport(raw_rows=0, kept_sales=0)
    assert report.survival_rate == 0.0


def test_summary_is_readable() -> None:
    report = CleaningReport(raw_rows=1000, kept_sales=250)
    assert report.summary() == "1000 raw rows -> 250 sales (25.0% kept)"


def test_check_quality_accepts_a_normal_rate() -> None:
    check_quality(CleaningReport(raw_rows=1000, kept_sales=207))


def test_check_quality_rejects_a_low_rate() -> None:
    report = CleaningReport(raw_rows=1000, kept_sales=50)
    with pytest.raises(DataQualityError, match="5.0%"):
        check_quality(report)


def test_check_quality_rejects_an_empty_dataset() -> None:
    report = CleaningReport(raw_rows=0, kept_sales=0)
    with pytest.raises(DataQualityError, match="empty or missing"):
        check_quality(report)


def test_the_threshold_is_configurable() -> None:
    report = CleaningReport(raw_rows=1000, kept_sales=150)
    check_quality(report, min_rate=0.10)
    with pytest.raises(DataQualityError):
        check_quality(report, min_rate=0.20)


def test_the_report_is_immutable() -> None:
    """frozen=True prevents any change after construction."""
    report = CleaningReport(raw_rows=1000, kept_sales=250)
    with pytest.raises(AttributeError):
        report.kept_sales = 999  # type: ignore[misc]
