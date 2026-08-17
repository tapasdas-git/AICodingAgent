import json
import logging
import re
import sys
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).parents[1]))

from Coding import JSONFileLogger, create_json_logger


class JSONFileLoggerTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.path = Path(self.temporary_directory.name) / "nested" / "events.log"
        self.loggers = []

    def tearDown(self):
        for logger in self.loggers:
            for handler in tuple(logger.handlers):
                handler.close()
                logger.removeHandler(handler)

    def make_logger(self, **kwargs):
        logger = create_json_logger(self.path, **kwargs)
        self.loggers.append(logger)
        return logger

    def records(self, path=None):
        target = path or self.path
        return [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()]

    def all_records(self):
        records = []
        for path in self.path.parent.glob(f"{self.path.name}*"):
            records.extend(self.records(path))
        return records

    def test_writes_structured_json_context_and_exception(self):
        logger = self.make_logger(level="DEBUG")
        logger.info("hello %s", "world", extra={"request_id": "abc", "payload": {"x": 1}})
        try:
            raise RuntimeError("broken")
        except RuntimeError:
            logger.exception("operation failed")

        first, second = self.records()
        self.assertEqual(first["message"], "hello world")
        self.assertEqual(first["level"], "INFO")
        self.assertEqual(first["request_id"], "abc")
        self.assertEqual(first["payload"], {"x": 1})
        self.assertRegex(first["timestamp"], r"^\d{4}-\d\d-\d\dT.*Z$")
        self.assertIn("RuntimeError: broken", second["exception"])

    def test_reserved_extra_fields_cannot_replace_canonical_fields(self):
        logger = self.make_logger()
        logger.info(
            "authentic message",
            extra={
                "timestamp": "FORGED",
                "level": "FORGED",
                "exception": "FORGED",
                "request_id": "kept",
            },
        )

        [record] = self.records()
        self.assertNotEqual(record["timestamp"], "FORGED")
        self.assertRegex(record["timestamp"], r"^\d{4}-\d\d-\d\dT.*Z$")
        self.assertEqual(record["level"], "INFO")
        self.assertEqual(record["message"], "authentic message")
        self.assertNotIn("exception", record)
        self.assertEqual(record["request_id"], "kept")

    def test_filters_levels_and_supports_custom_timestamp_format(self):
        logger = self.make_logger(level="WARNING", timestamp_format="%Y/%m/%d %H:%M:%S")
        logger.info("ignored")
        logger.warning("kept")

        [record] = self.records()
        self.assertEqual(record["message"], "kept")
        self.assertTrue(re.fullmatch(r"\d{4}/\d\d/\d\d \d\d:\d\d:\d\d", record["timestamp"]))

    def test_rotates_file_and_respects_backup_count(self):
        logger = self.make_logger(max_bytes=180, backup_count=2)
        for index in range(20):
            logger.info("event-%02d-%s", index, "x" * 40)
        for handler in logger.handlers:
            handler.flush()

        files = sorted(self.path.parent.glob("events.log*"))
        self.assertEqual({file.name for file in files}, {"events.log", "events.log.1", "events.log.2"})
        for file in files:
            self.records(file)

    def test_concurrent_writes_are_complete_and_valid(self):
        logger = self.make_logger(max_bytes=0)
        threads = [
            threading.Thread(
                target=lambda worker=worker: [logger.info("entry", extra={"id": f"{worker}-{i}"}) for i in range(100)]
            )
            for worker in range(8)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        records = self.records()
        self.assertEqual(len(records), 800)
        self.assertEqual(len({record["id"] for record in records}), 800)

    def test_multiple_instances_serialize_shared_file_rotation(self):
        loggers = [self.make_logger(max_bytes=350, backup_count=100) for _ in range(4)]
        errors = []

        def write_events(worker):
            try:
                for index in range(50):
                    loggers[worker].info(
                        "rotating-entry-%s",
                        "x" * 30,
                        extra={"id": f"{worker}-{index}"},
                    )
            except BaseException as error:
                errors.append(error)

        threads = [threading.Thread(target=write_events, args=(worker,)) for worker in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        for logger in loggers:
            for handler in logger.handlers:
                handler.flush()

        records = self.all_records()
        self.assertEqual(errors, [])
        self.assertEqual(len(records), 200)
        self.assertEqual(len({record["id"] for record in records}), 200)

    def test_validates_configuration_and_facade_closes(self):
        with self.assertRaises(ValueError):
            create_json_logger(self.path, level="LOUD")
        with self.assertRaises(ValueError):
            create_json_logger(self.path, max_bytes=-1)
        with self.assertRaises(ValueError):
            create_json_logger(self.path, backup_count=-1)
        with JSONFileLogger(self.path) as facade:
            facade.info("closed safely")
        self.assertEqual(self.records()[0]["message"], "closed safely")


if __name__ == "__main__":
    unittest.main()
