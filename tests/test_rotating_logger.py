import glob
import logging
import time

from tree_craftsman.logger import configure_size_rotating_logger, close_logger


def test_rotating_by_size(tmp_path):
    log_file = tmp_path / "app.log"
    # small threshold to trigger rotation
    max_bytes = 1024  # 1KB
    backup_count = 3

    logger = configure_size_rotating_logger(
        str(log_file),
        max_bytes=max_bytes,
        backup_count=backup_count,
        level=logging.INFO,
    )

    try:
        # each line ~200 bytes to trigger rotations
        line = "X" * 200
        for i in range(30):
            logger.info("%d %s", i, line)
            for h in logger.handlers:
                try:
                    h.flush()
                except OSError:
                    pass
        # give filesystem a moment
        time.sleep(0.1)

        files = sorted(glob.glob(str(tmp_path / "app.log*")))
        assert 1 <= len(files) <= (1 + backup_count)
    finally:
        close_logger(logger)
