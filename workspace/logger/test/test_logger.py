import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from Coding.logger import JSONFileLogger, LoggerConfig, create_json_logger


FIXED_TIME = datetime(2026, 8, 14, 12, 30, 45, 123456, tzinfo=timezone(timedelta(hours=5, minutes=30)))


def read_records(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_structured_record_level_filter_and_timestamp(tmp_path):
    path = tmp_path / "nested" / "app.jsonl"
    logger = JSONFileLogger(LoggerConfig(path, level="warning"), clock=lambda: FIXED_TIME)
    assert logger.info("filtered") is False
    assert logger.error("failed", request_id="abc", count=2) is True
    logger.close()

    assert read_records(path) == [{
        "timestamp": "2026-08-14T07:00:45.123Z",
        "level": "ERROR",
        "message": "failed",
        "request_id": "abc",
        "count": 2,
    }]


def test_factory_and_convenience_levels(tmp_path):
    path = tmp_path / "events.log"
    with create_json_logger({"path": path, "level": "debug"}, clock=lambda: FIXED_TIME) as logger:
        assert logger.debug("d") and logger.info("i") and logger.warning("w")
        assert logger.error("e") and logger.critical("c")
    assert [item["level"] for item in read_records(path)] == ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    assert {item["timestamp"] for item in read_records(path)} == {"2026-08-14T07:00:45.123Z"}
    with pytest.raises(ValueError, match="closed"):
        logger.info("late")


@pytest.mark.parametrize(
    "kwargs,error",
    [
        ({"path": ""}, ValueError),
        ({"path": "x", "level": "trace"}, ValueError),
        ({"path": "x", "max_bytes": -1}, ValueError),
        ({"path": "x", "max_bytes": True}, TypeError),
        ({"path": "x", "backup_count": -1}, ValueError),
        ({"path": "x", "backup_count": 1.5}, TypeError),
        ({"path": "x", "encoding": ""}, ValueError),
    ],
)
def test_config_validation(kwargs, error):
    with pytest.raises(error):
        LoggerConfig(**kwargs)


def test_record_validation_happens_before_write(tmp_path):
    path = tmp_path / "safe.log"
    logger = create_json_logger(path=path)
    with pytest.raises(TypeError, match="message"):
        logger.info(3)
    with pytest.raises(ValueError, match="reserved"):
        logger.info("x", timestamp="fake")
    with pytest.raises(TypeError, match="JSON serializable"):
        logger.info("x", bad=object())
    with pytest.raises(ValueError, match="timezone-aware"):
        JSONFileLogger(LoggerConfig(tmp_path / "naive"), clock=lambda: datetime(2020, 1, 1)).info("x")
    logger.close()
    assert path.read_text() == ""


def test_size_rotation_keeps_configured_backups(tmp_path):
    path = tmp_path / "rotate.log"
    logger = create_json_logger(path=path, max_bytes=100, backup_count=2)
    for number in range(5):
        logger.info(f"record-{number}")
    logger.close()

    assert path.exists() and Path(f"{path}.1").exists() and Path(f"{path}.2").exists()
    assert not Path(f"{path}.3").exists()
    records = []
    for candidate in (Path(f"{path}.2"), Path(f"{path}.1"), path):
        records.extend(read_records(candidate))
    assert [record["message"] for record in records] == ["record-2", "record-3", "record-4"]


def test_concurrent_writes_are_complete_json_lines(tmp_path):
    path = tmp_path / "threads.log"
    logger = create_json_logger(path=path, level="debug")
    with ThreadPoolExecutor(max_workers=12) as pool:
        list(pool.map(lambda number: logger.info("concurrent", sequence=number), range(200)))
    logger.close()
    records = read_records(path)
    assert len(records) == 200
    assert {record["sequence"] for record in records} == set(range(200))


def test_factory_rejects_ambiguous_or_invalid_config(tmp_path):
    config = LoggerConfig(tmp_path / "file.log")
    with pytest.raises(ValueError, match="overrides"):
        create_json_logger(config, level="DEBUG")
    with pytest.raises(TypeError, match="config"):
        create_json_logger("bad")
    with pytest.raises(TypeError, match="LoggerConfig"):
        JSONFileLogger({"path": tmp_path / "x"})
