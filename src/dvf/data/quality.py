"""Quality gate on the cleaning pipeline.

A measurement taken once in a notebook is a curiosity. The same measurement
checked on every run is a guardrail: if the source ever changes format, the
pipeline stops instead of silently producing wrong data.
"""

from dataclasses import dataclass

# Below this rate, something has changed upstream.
MIN_SURVIVAL_RATE = 0.10


class DataQualityError(Exception):
    """Cleaning dropped far more data than expected."""


@dataclass(frozen=True)
class CleaningReport:
    """Numeric summary of one cleaning run."""

    raw_rows: int
    kept_sales: int

    @property
    def survival_rate(self) -> float:
        """Share of raw rows that become usable sales."""
        if self.raw_rows == 0:
            return 0.0
        return self.kept_sales / self.raw_rows

    def summary(self) -> str:
        """One readable line, meant for the logs."""
        return (
            f"{self.raw_rows} raw rows -> {self.kept_sales} sales "
            f"({self.survival_rate:.1%} kept)"
        )


def check_quality(report: CleaningReport, min_rate: float = MIN_SURVIVAL_RATE) -> None:
    """Raise if cleaning dropped too much data.

    We fail loudly rather than let a suspicious dataset through: a visible
    error is far cheaper than a model trained on truncated data.
    """
    if report.raw_rows == 0:
        message = "No raw rows: the source files are empty or missing."
        raise DataQualityError(message)

    if report.survival_rate < min_rate:
        message = (
            f"Survival rate of {report.survival_rate:.1%}, "
            f"below the {min_rate:.0%} threshold. "
            f"The source format may have changed."
        )
        raise DataQualityError(message)
