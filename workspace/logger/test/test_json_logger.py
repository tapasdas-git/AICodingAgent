from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from workspace.logger.Coding.json_logger import JsonFileLogger, LoggerConfig, create_json_logger


def _records(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_structured_record_level_filter_and_custom_timestamp(tmp_path: Path) -> None:
    moment = datetime(2026, 8, 14, 9, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    logger = create_json_logger(
        tmp_path / "nested" / "events.jsonl",
        level="warning",
        timestamp_format="%Y/%m/%d %H:%M:%S %z",
        clock=lambda: moment,
    )

    assert logger.info("filtered") is False
    assert logger.warning("disk nearing capacity", percent=91, labels=["storage"]) is True

    assert _records(tmp_path / "nested" / "events.jsonl") == [{
        "timestamp": "2026/08/14 04:00:00 +0000",
        "level": "WARNING",
        "message": "disk nearing capacity",
        "percent": 91,
        "labels": ["storage"],
    }]


def test_all_convenience_levels_are_written(tmp_path: Path) -> None:
    logger = create_json_logger(tmp_path / "levels.jsonl", level="DEBUG")

    assert logger.debug("d")
    assert logger.info("i")
    assert logger.warning("w")
    assert logger.error("e")
    assert logger.critical("c")

    assert [item["level"] for item in _records(tmp_path / "levels.jsonl")] == [
        "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
    ]


def test_rotation_keeps_configured_number_of_backups(tmp_path: Path) -> None:
    path = tmp_path / "rotate.jsonl"
    logger = create_json_logger(path, max_bytes=1, backup_count=2)

    logger.info("first")
    logger.info("second")
    logger.info("third")
    logger.info("fourth")

    assert _records(path)[0]["message"] == "fourth"
    assert _records(Path(f"{path}.1"))[0]["message"] == "third"
    assert _records(Path(f"{path}.2"))[0]["message"] == "second"


def test_rotation_without_backups_discards_old_file(tmp_path: Path) -> None:
    path = tmp_path / "no-backup.jsonl"
    logger = create_json_logger(path, max_bytes=1, backup_count=0)
    logger.info("old")
    logger.info("new")

    assert [item["message"] for item in _records(path)] == ["new"]
    assert not Path(f"{path}.1").exists()


def test_concurrent_writes_produce_complete_json_records(tmp_path: Path) -> None:
    path = tmp_path / "threads.jsonl"
    logger = create_json_logger(path, max_bytes=1_000_000)

    with ThreadPoolExecutor(max_workers=12) as executor:
        results = list(executor.map(lambda number: logger.info("worker", number=number), range(300)))

    records = _records(path)
    assert all(results)
    assert len(records) == 300
    assert {item["number"] for item in records} == set(range(300))


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"level": "TRACE"}, ValueError),
        ({"level": 10}, TypeError),
        ({"max_bytes": 0}, ValueError),
        ({"max_bytes": True}, ValueError),
        ({"backup_count": -1}, ValueError),
        ({"backup_count": False}, ValueError),
        ({"timestamp_format": ""}, ValueError),
    ],
)
def test_factory_validates_configuration(tmp_path: Path, kwargs: dict[str, object], error: type[Exception]) -> None:
    with pytest.raises(error):
        create_json_logger(tmp_path / "invalid.jsonl", **kwargs)  # type: ignore[arg-type]


def test_logger_validates_inputs_before_writing(tmp_path: Path) -> None:
    path = tmp_path / "invalid-record.jsonl"
    logger = create_json_logger(path)

    with pytest.raises(TypeError, match="message"):
        logger.info(123)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="reserved"):
        logger.info("bad", level="fake")
    with pytest.raises(TypeError, match="JSON serializable"):
        logger.info("bad", value=object())
    with pytest.raises(ValueError, match="unsupported"):
        logger.log("notice", "bad")

    assert not path.exists()


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_floats_are_rejected_before_writing(tmp_path: Path, value: float) -> None:
    path = tmp_path / "non-finite.jsonl"
    logger = create_json_logger(path)

    with pytest.raises(TypeError, match="JSON serializable"):
        logger.info("invalid numeric value", value=value)

    assert not path.exists()


def test_constructor_and_clock_contracts_are_validated(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match="LoggerConfig"):
        JsonFileLogger(object())  # type: ignore[arg-type]
    config = LoggerConfig(tmp_path / "clock.jsonl")
    with pytest.raises(TypeError, match="callable"):
        JsonFileLogger(config, clock=object())  # type: ignore[arg-type]
    logger = JsonFileLogger(config, clock=lambda: "now")  # type: ignore[arg-type,return-value]
    with pytest.raises(TypeError, match="datetime"):
        logger.info("bad clock")


def test_naive_clock_is_interpreted_as_utc_and_unicode_is_preserved(tmp_path: Path) -> None:
    path = tmp_path / "unicode.jsonl"
    logger = create_json_logger(path, clock=lambda: datetime(2026, 1, 2, 3, 4, 5))
    logger.info("नमस्ते")

    record = _records(path)[0]
    assert record["timestamp"] == "2026-01-02T03:04:05.000000Z"
    assert record["message"] == "नमस्ते"
