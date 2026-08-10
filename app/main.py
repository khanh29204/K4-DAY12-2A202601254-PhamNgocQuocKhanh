"""Chat service — điểm ráp nối của cả lab (CP1, CP3, CP4).

Luồng một request tới /chat:

    client ──► verify_bearer_token ──► token bucket ──► cost guard
                                                            │
                                    store.history ◄─────────┘
                                          │
                                   generate_reply
                                          │
                              store.add_turn × 2 ──► guard.record ──► emit
"""

from __future__ import annotations

import sys
import time
from contextlib import asynccontextmanager
from functools import lru_cache

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError

from utils.mock_llm import generate_reply

from .auth import verify_bearer_token
from .config import get_settings
from .cost_guard import CostGuard
from .lifecycle import shutdown_guard
from .logging_utils import configure_logging, emit
from .rate_limiter import TokenBucket
from .store import ChatStore, get_redis_client

SERVICE_NAME = "day12-chat-service"
SERVICE_VERSION = "1.0.0"

# Thời điểm process bắt đầu — dùng cho `uptime_s` ở /health. Đây là con số
# phân biệt "app vẫn đang sống" với "app vừa bị restart âm thầm": uptime tụt
# về 0 sau mỗi lần bạn nhìn nghĩa là container đang crash-loop.
STARTED_AT = time.monotonic()

# Log ra JSON ngay từ lúc import, trước cả khi uvicorn kịp gắn handler text
# mặc định của nó. Đọc LOG_LEVEL thẳng từ biến môi trường, chưa đụng tới
# Settings — Settings có thể ném lỗi, và lỗi đó cũng cần được log ra JSON.
configure_logging()


# ─────────────────────────────────────────────────────────────
# Providers — CHO SẴN
# Tách ra thành hàm để test có thể thay bằng Redis giả qua
# app.dependency_overrides, và để kết nối Redis chỉ tạo khi thật sự cần.
# ─────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def get_store() -> ChatStore:
    return ChatStore(get_redis_client())


@lru_cache(maxsize=1)
def get_bucket() -> TokenBucket:
    settings = get_settings()
    return TokenBucket(
        get_redis_client(),
        capacity=settings.bucket_capacity,
        refill_per_minute=settings.refill_per_minute,
    )


@lru_cache(maxsize=1)
def get_cost_guard() -> CostGuard:
    return CostGuard(get_redis_client(), get_settings().daily_budget_usd)


def load_settings_or_exit():
    """Đọc cấu hình; thiếu hoặc sai thì DỪNG HẲN process, không chạy tiếp.

    Đây là phần "thiếu API_TOKEN thì không run". Chỉ khai báo ``api_token``
    là trường bắt buộc thôi chưa đủ: ``get_settings()`` được gọi lười, mãi
    tới request /chat đầu tiên mới chạm tới. App vì thế vẫn khởi động ngon
    lành, /healthz vẫn xanh, orchestrator vẫn báo "deploy thành công" — rồi
    mọi request thật đều 500. Deploy hỏng mà mọi đèn đều xanh là kiểu hỏng
    tệ nhất.

    ``sys.exit(1)`` để orchestrator thấy container chết ngay và giữ lại bản
    cũ đang chạy, thay vì thay nó bằng một bản không phục vụ được.
    """
    try:
        return get_settings()
    except ValidationError as err:
        missing = [
            ".".join(str(part) for part in error["loc"]) for error in err.errors()
        ]
        emit(
            "config_invalid",
            severity="CRITICAL",
            service=SERVICE_NAME,
            invalid_fields=missing,
            detail=str(err),
            hint="Đặt biến môi trường còn thiếu (xem .env.example) rồi chạy lại.",
        )
        sys.exit(1)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """CHO SẴN — chạy lúc app khởi động và lúc tắt."""
    settings = load_settings_or_exit()
    # Cấu hình lại log lần hai: lần này bằng LOG_LEVEL đã qua kiểm tra của
    # Settings, thay cho giá trị thô đọc từ env lúc import.
    level = configure_logging(settings.log_level)

    shutdown_guard.arm()
    emit(
        "service_started",
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
        port=settings.port,
        log_level=level,
    )
    yield
    emit("service_stopped", service=SERVICE_NAME)


app = FastAPI(title="Day 12 Chat Service", version=SERVICE_VERSION, lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


# ─────────────────────────────────────────────────────────────
# Health & readiness
#
# Hai câu hỏi khác nhau, đừng gộp làm một:
#
#   /healthz — "process này còn sống không?"      → sai thì RESTART container
#   /readyz  — "nó phục vụ được request chưa?"    → sai thì NGỪNG GỬI traffic
#
# Gộp lại thì Redis chớp tắt một nhịp sẽ khiến toàn bộ cụm container bị giết
# và khởi động lại cùng lúc — trong khi việc đúng cần làm chỉ là tạm ngừng
# đẩy traffic vào cho tới khi Redis trả lời lại.
# ─────────────────────────────────────────────────────────────
@app.get("/healthz")
def healthz():
    """Liveness probe — process còn sống không?

    Endpoint này phải **nhẹ**: không gọi Redis, không query DB. Nó chỉ trả
    lời câu hỏi "có cần restart container này không?". Nếu nó phụ thuộc
    Redis, Redis chết một nhịp là cả cụm container bị restart theo.
    """
    if shutdown_guard.draining:
        return JSONResponse(status_code=503, content={"status": "draining"})
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "uptime_s": round(time.monotonic() - STARTED_AT, 3),
    }


@app.get("/readyz")
def readyz(store: ChatStore = Depends(get_store)):
    """Readiness probe — đã sẵn sàng nhận traffic chưa?

    Khác /healthz ở chỗ: endpoint này ĐƯỢC PHÉP kiểm tra dependency. Load
    balancer dùng nó để quyết định có đẩy request vào instance này không.
    """
    if shutdown_guard.draining:
        return JSONResponse(status_code=503, content={"status": "draining"})
    if not store.ping():
        # Log ở mức ERROR: /readyz đỏ nghĩa là instance này đang bị rút khỏi
        # vòng xoay của load balancer — đáng để cảnh báo, không phải chuyện
        # thường ngày.
        emit("readiness_failed", severity="ERROR", service=SERVICE_NAME, redis=False)
        return JSONResponse(
            status_code=503, content={"status": "not ready", "redis": False}
        )
    return {"status": "ready", "redis": True}


# ─────────────────────────────────────────────────────────────
# Endpoint chính
# ─────────────────────────────────────────────────────────────
@app.post("/chat")
def chat(
    payload: ChatRequest,
    client_id: str = Depends(verify_bearer_token),
    store: ChatStore = Depends(get_store),
    bucket: TokenBucket = Depends(get_bucket),
    guard: CostGuard = Depends(get_cost_guard),
):
    """Gửi một tin nhắn tới service.

    Thứ tự các bước là cố ý: chặn (rate limit → ngân sách) trước, gọi LLM sau.
    Vì tiền mất ở bước gọi LLM — chặn sau khi đã gọi thì bạn vừa trả tiền vừa
    trả lỗi.

    ``client_id`` do ``verify_bearer_token`` trả về, nên request không có
    token hợp lệ sẽ dừng ở 401 trước khi chạm vào bất cứ dòng nào ở đây.
    """
    bucket.consume(client_id)  # 429 nếu gọi quá nhanh
    guard.check(client_id)  # 402 nếu hết ngân sách ngày

    history = store.history(client_id)
    result = generate_reply(payload.message, history)

    store.add_turn(client_id, "user", payload.message)
    store.add_turn(client_id, "assistant", result["text"])
    guard.record(client_id, result["usd_cost"])

    emit(
        "chat_completed",
        client_id=client_id,
        prompt_tokens=result["prompt_tokens"],
        completion_tokens=result["completion_tokens"],
        usd_cost=result["usd_cost"],
    )

    return {
        "reply": result["text"],
        "client_id": client_id,
        "turns_before": len(history),
        "usd_cost": result["usd_cost"],
        "usage": {
            "prompt": result["prompt_tokens"],
            "completion": result["completion_tokens"],
        },
    }


if __name__ == "__main__":
    import uvicorn

    # Kiểm tra cấu hình TRƯỚC khi uvicorn mở cổng: sai config thì thoát ngay
    # với exit code 1, không bao giờ có một cổng mở dẫn tới app hỏng.
    settings = load_settings_or_exit()

    # log_config=None để uvicorn không cài đè cấu hình log của ta bằng bản
    # text mặc định — nếu không, access log sẽ quay lại dạng chữ.
    uvicorn.run(app, host="0.0.0.0", port=settings.port, log_config=None)
