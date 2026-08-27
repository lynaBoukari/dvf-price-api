"""Tests for the download module.

We do not test the actual download: a test must never depend on the network.
We test the pure logic, here the URL building.
"""

from dvf.data.download import build_url


def test_build_url_returns_a_valid_url() -> None:
    url = build_url(2024, "33")
    assert url.startswith("https://")
    assert url.endswith("/2024/departements/33.csv.gz")


def test_build_url_handles_corsican_departments() -> None:
    assert build_url(2024, "2A").endswith("/2A.csv.gz")


def test_build_url_changes_with_the_year() -> None:
    assert build_url(2022, "33") != build_url(2024, "33")
