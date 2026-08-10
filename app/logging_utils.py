"""CP1 — Structured logging.

`print("client abc hỏi gì đó")` là log cho người đọc. Cloud (Railway, Render,
Cloud Run, Datadog...) đọc log bằng máy: một dòng = một JSON object thì mới
lọc/đếm/cảnh báo được. Đây là khác biệt lớn giữa localhost và production.

Module này lo hai nguồn log, và cả hai phải ra cùng một định dạng:

    emit()              → log của app  ("chat_completed", "service_started"...)
    JsonFormatter       → log của thư viện (uvicorn, FastAPI), gồm cả access log

Chỉ làm nửa đầu thì công cụ thu thập log parse được log của bạn nhưng vỡ ở
access log của uvicorn — mà đó lại chính là chỗ ghi status code và latency.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone

# Khóa `severity` (không phải `level`) là tên mà Google Cloud Logging hiểu.
# Map sang mức của `logging` chuẩn để emit() và logger của uvicorn dùng chung
# một thang đo — LOG_LEVEL=WARNING thì cả hai cùng im.
SEVERITY_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "NOTICE": logging.INFO,
    "WARNING": logging.WARNING,
    "WARN": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
    "FATAL": logging.CRITICAL,
}

DEFAULT_LEVEL = "INFO"

# Logger của uvicorn: không tắt, chỉ đổi định dạng đầu ra sang JSON.
UVICORN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi")

# Ngưỡng lọc của emit(). Cố tình KHÔNG đọc qua get_settings(): log phải chạy
# được cả khi cấu hình lỗi — đó đúng là lúc ta cần log nhất.
_min_level = logging.INFO


def utc_now_iso() -> str:
    """CHO SẴN — thời điểm hiện tại theo ISO-8601, múi giờ UTC."""
    return datetime.now(timezone.utc).isoformat()


def level_of(severity: str) -> int:
    """Đổi tên mức log thành số của ``logging``; tên lạ thì coi như INFO."""
    return SEVERITY_LEVELS.get(str(severity).upper(), logging.INFO)


class JsonFormatter(logging.Formatter):
    """Định dạng log của thư viện thành JSON một dòng, cùng khóa với emit().

    Access log của uvicorn đi kèm ``record.args`` là tuple 5 phần tử
    (client, method, path, http_version, status). Tách nó thành các trường
    riêng thì mới lọc được kiểu "đếm request 5xx trong 10 phút qua" — chuỗi
    ``'GET /chat HTTP/1.1" 200'`` thì phải regex lại mới dùng được.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "event": record.name,
            "severity": logging.getLevelName(record.levelno).upper(),
            "ts": utc_now_iso(),
            "message": record.getMessage(),
            "logger": record.name,
        }

        if record.name == "uvicorn.access" and isinstance(record.args, tuple):
            if len(record.args) == 5:
                client_addr, method, full_path, http_version, status_code = record.args
                payload.update(
                    {
                        "event": "http_request",
                        "client_addr": client_addr,
                        "method": method,
                        "path": full_path,
                        "http_version": http_version,
                        "status": status_code,
                    }
                )

        if record.exc_info:
            payload["traceback"] = self.formatException(record.exc_info)

        # default=str để một object lạ trong log không làm hỏng cả dòng log
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str | None = None) -> str:
    """Bắt mọi log trong process đi ra stdout dưới dạng JSON một dòng.

    Gọi hai lần là bình thường và cố ý: lần đầu lúc import (để bắt cả log
    khởi động của uvicorn, vốn phát ra trước lifespan), lần sau trong lifespan
    khi đã đọc được ``LOG_LEVEL`` từ Settings.

    ``level=None`` thì đọc thẳng biến môi trường ``LOG_LEVEL`` — không đi qua
    Settings, vì Settings bắt buộc có API_TOKEN và ta cần log hoạt động được
    kể cả khi thiếu nó.
    """
    global _min_level

    level_name = (level or os.getenv("LOG_LEVEL") or DEFAULT_LEVEL).strip().upper()
    numeric = level_of(level_name)
    _min_level = numeric

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    # Gán đè thay vì thêm vào: nối thêm handler nghĩa là mỗi dòng log ra hai
    # lần (một text của uvicorn, một JSON của ta).
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(numeric)

    for name in UVICORN_LOGGERS:
        logger = logging.getLogger(name)
        logger.handlers = []  # bỏ handler text mặc định của uvicorn
        logger.propagate = True  # để log đi lên handler JSON ở root
        logger.setLevel(numeric)

    return level_name


def emit(event: str, severity: str = "INFO", **fields) -> str:
    """Ghi một dòng log JSON ra stdout.

    Ba khóa luôn có: ``event``, ``severity`` (VIẾT HOA — đúng tên khóa mà
    Google Cloud Logging hiểu để tô màu và lọc) và ``ts``. Mọi cặp key/value
    trong ``**fields`` được gộp thêm vào.

    Dòng log dưới ngưỡng ``LOG_LEVEL`` thì không in, nhưng hàm **vẫn trả về**
    chuỗi JSON: nơi gọi có thể dùng nó cho việc khác (test, gửi đi nơi khác)
    mà không phụ thuộc vào mức log đang bật.

    Ví dụ:
        >>> emit("chat_completed", client_id="sv01", usd_cost=0.0001)
        '{"event": "chat_completed", "severity": "INFO", "ts": "...", ...}'
    """
    severity = severity.upper()
    record = {
        "event": event,
        "severity": severity,
        "ts": utc_now_iso(),
        **fields,
    }
    line = json.dumps(record, ensure_ascii=False, default=str)
    if level_of(severity) >= _min_level:
        print(line, file=sys.stdout, flush=True)
    return line
