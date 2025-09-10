import os
from typing import List, Optional

import orjson
import pendulum
import structlog

# Repository root (two levels up from this file: src/tree_craftsman -> src/.. -> repo root)
PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)


def build_tree(root: str, show_hidden: bool = False) -> str:
    """Return an ASCII tree string for the given directory path.

    Hidden files (starting with '.') are skipped by default.
    """
    if not os.path.exists(root):
        raise FileNotFoundError(root)

    lines: List[str] = []

    root_name = os.path.abspath(root)
    lines.append(root_name)

    def _inner(dir_path: str, prefix: str = ""):
        try:
            entries = sorted(os.listdir(dir_path))
        except PermissionError:
            lines.append(prefix + "└── [permission denied]")
            return
        if not show_hidden:
            entries = [e for e in entries if not e.startswith('.')]
        for i, entry in enumerate(entries):
            path = os.path.join(dir_path, entry)
            last = i == len(entries) - 1
            connector = "└── " if last else "├── "
            lines.append(prefix + connector + entry)
            if os.path.isdir(path):
                extension = "    " if last else "│   "
                _inner(path, prefix + extension)

    if os.path.isdir(root):
        _inner(root, "")

    return "\n".join(lines)


def save_txt(text: str, out_path: str) -> None:
    os.makedirs(os.path.dirname(out_path) or os.getcwd(), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)


def save_json_machine(obj: dict, out_path: str) -> None:
    # orjson.dumps -> bytes (UTF-8); write as binary to preserve encoding
    os.makedirs(os.path.dirname(out_path) or os.getcwd(), exist_ok=True)
    b = orjson.dumps(obj)
    with open(out_path, "wb") as f:
        f.write(b)


def _add_pendulum_timestamp(logger, method_name, event_dict: dict) -> dict:
    # structlog processors receive (logger, method_name, event_dict)
    # Asia/Tokyo (no DST, always +09:00)
    event_dict["timestamp"] = pendulum.now("Asia/Tokyo").isoformat()
    return event_dict


def configure_structlog(logfile_path: str):
    """Configure structlog to write JSONL lines (encoded by orjson)

    The final rendered string will be a single JSON line (UTF-8) ending with
    a newline.
    """
    import logging as _logging
    from structlog.processors import add_log_level

    # set up stdlib logging to write raw messages to the file
    handler = _logging.FileHandler(logfile_path, encoding="utf-8")
    handler.setFormatter(_logging.Formatter("%(message)s"))

    root = _logging.getLogger()
    # remove other handlers to avoid duplicate output
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(handler)
    root.setLevel(_logging.INFO)

    def orjson_renderer(_, __, event_dict: dict) -> str:
        # orjson.dumps -> bytes; decode to str and append newline
        return orjson.dumps(event_dict).decode("utf-8") + "\n"

    structlog.configure(
        processors=[
            add_log_level,
            _add_pendulum_timestamp,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            orjson_renderer,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    return structlog.get_logger("tree_craftsman"), handler


def generate_for_path(
    path: str,
    out_dir: Optional[str] = None,
    logs_dir: str = "logs",
    txt_name: Optional[str] = None,
    json_name: Optional[str] = None,
    show_hidden: bool = False,
) -> dict:
    """Generate ASCII tree txt and machine json for `path`.

    Returns a dict of created paths.

    - txt file: UTF-8 text
    - json file: UTF-8 binary containing orjson-encoded object
    - logs: append a jsonl event via structlog + orjson
    """
    path = os.path.abspath(path)
    if not out_dir:
        # default to repository-level `out` directory
        out_dir = os.path.join(PROJECT_ROOT, "out")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(logs_dir, exist_ok=True)

    safe_base = os.path.basename(path.rstrip(os.sep)) or "root"
    txt_name = txt_name or f"{safe_base}_tree.txt"
    json_name = json_name or f"{safe_base}_tree.json"

    txt_path = os.path.join(out_dir, txt_name)
    json_path = os.path.join(out_dir, json_name)

    tree_text = build_tree(path, show_hidden=show_hidden)
    save_txt(tree_text, txt_path)

    payload = {
        "path": path,
        "generated_at": pendulum.now("Asia/Tokyo").isoformat(),
        "tree_text": tree_text,
        "text_file": os.path.abspath(txt_path),
    }
    save_json_machine(payload, json_path)

    # configure structlog to write to logs/jsonl
    logs_file = os.path.join(logs_dir, "tree_logs.jsonl")
    logger, handler = configure_structlog(logs_file)

    try:
        # log an event (will be rendered by orjson_renderer and written to file)
        logger.info(
            "tree_generated",
            path=path,
            text_file=os.path.abspath(txt_path),
            json_file=os.path.abspath(json_path),
            size_bytes=os.path.getsize(json_path),
        )
    finally:
        # remove and close the handler so the file is not kept open on Windows
        root = __import__("logging").getLogger()
        try:
            root.removeHandler(handler)
        except Exception:
            pass
        try:
            handler.close()
        except Exception:
            pass

    return {"txt": txt_path, "json": json_path, "log": logs_file}