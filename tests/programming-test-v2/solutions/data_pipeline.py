"""
DataPipeline: Configurable data processing pipeline with filter/map/aggregate steps.
"""

import csv
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

logger = logging.getLogger(__name__)

# Type aliases
Record = dict[str, Any]
Transform = Callable[[Record], Record | None]
FilterFn = Callable[[Record], bool]
AggregateFn = Callable[[list[Record]], Record]


# ------------------------------------------------------------------
# Pipeline step definitions
# ------------------------------------------------------------------

@dataclass
class StepResult:
    """Metrics captured after a pipeline step runs."""
    name: str
    input_count: int
    output_count: int
    errors: list[tuple[int, str]] = field(default_factory=list)  # (record_index, error_msg)


class PipelineStep:
    """Base class for a single pipeline step."""

    def __init__(self, name: str) -> None:
        self.name = name

    def run(self, records: list[Record]) -> tuple[list[Record], StepResult]:
        raise NotImplementedError


class FilterStep(PipelineStep):
    """Keep only records that satisfy a predicate."""

    def __init__(self, name: str, predicate: FilterFn) -> None:
        super().__init__(name)
        self.predicate = predicate

    def run(self, records: list[Record]) -> tuple[list[Record], StepResult]:
        errors: list[tuple[int, str]] = []
        kept: list[Record] = []
        for idx, rec in enumerate(records):
            try:
                if self.predicate(rec):
                    kept.append(rec)
            except Exception as exc:  # noqa: BLE001
                errors.append((idx, str(exc)))
                logger.warning("Filter '%s' error on record %d: %s", self.name, idx, exc)
        result = StepResult(self.name, len(records), len(kept), errors)
        return kept, result


class MapStep(PipelineStep):
    """Transform every record through a function.

    If the transform returns ``None``, the record is dropped (filtering map).
    """

    def __init__(self, name: str, transform: Transform) -> None:
        super().__init__(name)
        self.transform = transform

    def run(self, records: list[Record]) -> tuple[list[Record], StepResult]:
        errors: list[tuple[int, str]] = []
        out: list[Record] = []
        for idx, rec in enumerate(records):
            try:
                mapped = self.transform(rec)
                if mapped is not None:
                    out.append(mapped)
            except Exception as exc:  # noqa: BLE001
                errors.append((idx, str(exc)))
                logger.warning("Map '%s' error on record %d: %s", self.name, idx, exc)
        result = StepResult(self.name, len(records), len(out), errors)
        return out, result


class AggregateStep(PipelineStep):
    """Collapse all records into a single aggregated record."""

    def __init__(self, name: str, aggregate_fn: AggregateFn) -> None:
        super().__init__(name)
        self.aggregate_fn = aggregate_fn

    def run(self, records: list[Record]) -> tuple[list[Record], StepResult]:
        errors: list[tuple[int, str]] = []
        try:
            agg = self.aggregate_fn(records)
            out = [agg]
        except Exception as exc:  # noqa: BLE001
            errors.append((-1, str(exc)))
            logger.warning("Aggregate '%s' failed: %s", self.name, exc)
            out = []
        result = StepResult(self.name, len(records), len(out), errors)
        return out, result


# ------------------------------------------------------------------
# Built-in transforms (convenience helpers)
# ------------------------------------------------------------------

def rename_fields(mapping: dict[str, str]) -> Transform:
    """Return a transform that renames keys according to *mapping*."""
    def _transform(rec: Record) -> Record:
        out = dict(rec)
        for old, new in mapping.items():
            if old in out:
                out[new] = out.pop(old)
        return out
    return _transform


def cast_fields(casts: dict[str, type]) -> Transform:
    """Return a transform that casts specified fields to given types."""
    def _transform(rec: Record) -> Record:
        out = dict(rec)
        for key, typ in casts.items():
            if key in out:
                try:
                    out[key] = typ(out[key])
                except (ValueError, TypeError):
                    out[key] = None
        return out
    return _transform


def add_computed_field(name: str, fn: Callable[[Record], Any]) -> Transform:
    """Return a transform that adds a computed field."""
    def _transform(rec: Record) -> Record:
        out = dict(rec)
        out[name] = fn(rec)
        return out
    return _transform


def group_aggregate(group_key: str, agg_field: str, op: str = "sum") -> AggregateFn:
    """Aggregate records by summing/counting/averaging *agg_field* grouped by *group_key*.

    Returns a single record mapping group_key values to the aggregated value.
    """
    def _aggregate(records: list[Record]) -> Record:
        groups: dict[Any, list[float]] = {}
        for rec in records:
            key = rec.get(group_key)
            val = rec.get(agg_field, 0)
            groups.setdefault(key, []).append(float(val) if val is not None else 0.0)

        out: Record = {}
        for key, values in groups.items():
            if op == "sum":
                out[key] = sum(values)
            elif op == "mean":
                out[key] = sum(values) / len(values) if values else 0.0
            elif op == "count":
                out[key] = len(values)
            elif op == "min":
                out[key] = min(values)
            elif op == "max":
                out[key] = max(values)
            else:
                raise ValueError(f"Unknown aggregate op: {op}")
        return out
    return _aggregate


# ------------------------------------------------------------------
# DataPipeline
# ------------------------------------------------------------------

@dataclass
class PipelineReport:
    """Summary report after a pipeline run."""
    total_input: int
    total_output: int
    step_results: list[StepResult]
    elapsed: float

    def summary(self) -> str:
        lines = [
            f"Pipeline Report: {len(self.step_results)} steps",
            f"  Input records:  {self.total_input}",
            f"  Output records: {self.total_output}",
            f"  Elapsed:        {self.elapsed:.3f}s",
            f"  Steps:",
        ]
        for sr in self.step_results:
            errs = f"  ({len(sr.errors)} errors)" if sr.errors else ""
            lines.append(f"    {sr.name}: {sr.input_count} -> {sr.output_count}{errs}")
        return "\n".join(lines)


class DataPipeline:
    """Configurable data processing pipeline.

    Usage::

        pipeline = DataPipeline()
        pipeline.add_step(FilterStep("non_empty", lambda r: bool(r.get("name"))))
        pipeline.add_step(MapStep("normalize", cast_fields({"age": int})))
        pipeline.add_step(AggregateStep("total", group_aggregate("dept", "salary", "sum")))

        report = pipeline.run(records)
        print(report.summary())
        results = pipeline.output
    """

    def __init__(self) -> None:
        self.steps: list[PipelineStep] = []
        self.output: list[Record] = []
        self.report: PipelineReport | None = None

    # ------------------------------------------------------------------
    # Step management
    # ------------------------------------------------------------------

    def add_step(self, step: PipelineStep) -> "DataPipeline":
        """Add a step to the pipeline. Returns *self* for chaining."""
        self.steps.append(step)
        return self

    def filter(self, name: str, predicate: FilterFn) -> "DataPipeline":
        """Convenience: add a filter step."""
        return self.add_step(FilterStep(name, predicate))

    def map(self, name: str, transform: Transform) -> "DataPipeline":
        """Convenience: add a map step."""
        return self.add_step(MapStep(name, transform))

    def aggregate(self, name: str, aggregate_fn: AggregateFn) -> "DataPipeline":
        """Convenience: add an aggregate step."""
        return self.add_step(AggregateStep(name, aggregate_fn))

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run(self, records: list[Record]) -> PipelineReport:
        """Execute all steps sequentially on *records*."""
        import time
        start = time.monotonic()

        current = list(records)
        step_results: list[StepResult] = []

        for step in self.steps:
            current, sr = step.run(current)
            step_results.append(sr)
            logger.info("Step '%s': %d -> %d", sr.name, sr.input_count, sr.output_count)

        elapsed = time.monotonic() - start
        self.output = current
        self.report = PipelineReport(
            total_input=len(records),
            total_output=len(current),
            step_results=step_results,
            elapsed=elapsed,
        )
        return self.report

    # ------------------------------------------------------------------
    # I/O helpers
    # ------------------------------------------------------------------

    @staticmethod
    def load_csv(path: str | Path, encoding: str = "utf-8") -> list[Record]:
        """Load records from a CSV file."""
        with open(path, newline="", encoding=encoding) as f:
            return list(csv.DictReader(f))

    @staticmethod
    def load_json(path: str | Path, encoding: str = "utf-8") -> list[Record]:
        """Load records from a JSON file (expects a list of objects)."""
        with open(path, encoding=encoding) as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        raise ValueError("JSON root must be a list of objects")

    @staticmethod
    def load_ndjson(path: str | Path, encoding: str = "utf-8") -> list[Record]:
        """Load records from a newline-delimited JSON file."""
        records: list[Record] = []
        with open(path, encoding=encoding) as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    @staticmethod
    def save_csv(records: list[Record], path: str | Path, encoding: str = "utf-8") -> None:
        """Write records to a CSV file."""
        if not records:
            logger.warning("No records to write")
            return
        fieldnames = list(records[0].keys())
        with open(path, "w", newline="", encoding=encoding) as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)

    @staticmethod
    def save_json(records: list[Record], path: str | Path, encoding: str = "utf-8", indent: int = 2) -> None:
        """Write records to a JSON file."""
        with open(path, "w", encoding=encoding) as f:
            json.dump(records, f, indent=indent, ensure_ascii=False)


# ------------------------------------------------------------------
# Demo
# ------------------------------------------------------------------

def _demo() -> None:
    """Demonstrate the pipeline with synthetic sales data."""
    import random

    random.seed(42)

    # Generate sample data
    departments = ["Engineering", "Sales", "Marketing", "Support"]
    records: list[Record] = []
    for i in range(200):
        records.append({
            "id": i,
            "name": f"Employee_{i}",
            "department": random.choice(departments),
            "salary": random.randint(40000, 120000),
            "active": random.random() > 0.1,
        })

    print(f"Generated {len(records)} sample records\n")

    # Build and run pipeline
    pipeline = DataPipeline()
    pipeline.filter("active_only", lambda r: r.get("active", False))
    pipeline.map("with_bonus", add_computed_field("bonus", lambda r: r.get("salary", 0) * 0.1))
    pipeline.map("rename", rename_fields({"department": "dept"}))
    pipeline.aggregate("dept_salary", group_aggregate("dept", "salary", "sum"))

    report = pipeline.run(records)
    print(report.summary())
    print(f"\nAggregated output:")
    for rec in pipeline.output:
        print(f"  {rec}")


if __name__ == "__main__":
    _demo()
