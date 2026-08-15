from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from queue import Queue
import sys
import threading

import pytest


sys.path.insert(0, str(Path(__file__).parents[1]))

from Coding import LoggerConfig, create_json_logger


FIXED_TIME = datetime(2026, 8, 15, 9, 30, 5, tzinfo=timezone.utc)


def read_records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_writes_structured_json_with_iso_timestamp(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "app.log"
    logger = create_json_logger(path, clock=lambda: FIXED_TIME)

    assert logger.info("signed in", user_id=42, labels=["web"]) is True

    assert read_records(path) == [{
        "timestamp": "2026-08-15T09:30:05Z",
        "level": "INFO",
        "message": "signed in",
        "user_id": 42,
        "labels": ["web"],
    }]


def test_level_filtering_and_custom_timestamp_format(tmp_path: Path) -> None:
    path = tmp_path / "app.log"
    logger = create_json_logger(
        path, level="warning", timestamp_format="%Y/%m/%d %H:%M", clock=lambda: FIXED_TIME
    )

    assert logger.info("ignored") is False
    assert logger.warning("kept") is True

    assert read_records(path)[0] == {
        "timestamp": "2026/08/15 09:30", "level": "WARNING", "message": "kept"
    }


@pytest.mark.parametrize(
    "kwargs,exception",
    [
        ({"path": ""}, ValueError),
        ({"level": "verbose"}, ValueError),
        ({"timestamp_format": ""}, ValueError),
        ({"max_bytes": 0}, ValueError),
        ({"backup_count": 0}, ValueError),
    ],
)
def test_configuration_is_validated(tmp_path: Path, kwargs: dict, exception: type[Exception]) -> None:
    path = kwargs.pop("path", tmp_path / "app.log")
    with pytest.raises(exception):
        create_json_logger(path, **kwargs)


def test_record_inputs_are_validated(tmp_path: Path) -> None:
    logger = create_json_logger(tmp_path / "app.log", clock=lambda: FIXED_TIME)

    with pytest.raises(ValueError, match="reserved"):
        logger.info("event", timestamp="spoofed")
    with pytest.raises(TypeError, match="JSON-serializable"):
        logger.info("event", value=object())
    with pytest.raises(TypeError, match="message"):
        logger.info(123)  # type: ignore[arg-type]


def test_rotates_by_size_and_retains_configured_backups(tmp_path: Path) -> None:
    path = tmp_path / "app.log"
    logger = create_json_logger(path, max_bytes=110, backup_count=2, clock=lambda: FIXED_TIME)

    logger.info("first", sequence=1)
    logger.info("second", sequence=2)
    logger.info("third", sequence=3)

    assert read_records(path)[0]["message"] == "third"
    assert read_records(Path(f"{path}.1"))[0]["message"] == "second"
    assert read_records(Path(f"{path}.2"))[0]["message"] == "first"


def test_concurrent_writes_are_complete_json_records(tmp_path: Path) -> None:
    path = tmp_path / "app.log"
    logger = create_json_logger(path, level="DEBUG", clock=lambda: FIXED_TIME)
    count = 100
    threads = [threading.Thread(target=logger.debug, args=("worker",), kwargs={"index": i}) for i in range(count)]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    records = read_records(path)
    assert len(records) == count
    assert {record["index"] for record in records} == set(range(count))
    assert all(record["level"] == "DEBUG" for record in records)


def test_multiple_loggers_coordinate_concurrent_rotation(tmp_path: Path) -> None:
    log_directory = tmp_path / "logs"
    (log_directory / "child").mkdir(parents=True)
    path = log_directory / "app.log"
    equivalent_path = log_directory / "child" / ".." / "app.log"
    worker_count = 8
    writes_per_worker = 25
    barrier = threading.Barrier(worker_count)
    errors: Queue[BaseException] = Queue()

    def write_from_instance(worker: int) -> None:
        worker_path = path if worker % 2 == 0 else equivalent_path
        logger = create_json_logger(
            worker_path, max_bytes=180, backup_count=3, clock=lambda: FIXED_TIME
        )
        try:
            barrier.wait()
            for sequence in range(writes_per_worker):
                logger.info("worker", worker=worker, sequence=sequence)
        except BaseException as exc:
            errors.put(exc)

    threads = [
        threading.Thread(target=write_from_instance, args=(worker,))
        for worker in range(worker_count)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors.empty(), list(errors.queue)
    candidates = [path, *(Path(f"{path}.{i}") for i in range(1, 4))]
    log_files = [candidate for candidate in candidates if candidate.exists()]
    assert len(log_files) == 4
    records = [record for log_file in log_files for record in read_records(log_file)]
    assert records
    assert all(record["message"] == "worker" for record in records)


def test_logger_config_is_immutable(tmp_path: Path) -> None:
    config = LoggerConfig(tmp_path / "app.log")
    with pytest.raises(AttributeError):
        config.level = "DEBUG"  # type: ignore[misc]
