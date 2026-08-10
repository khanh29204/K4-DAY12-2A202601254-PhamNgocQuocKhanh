"""CP3 — Xác thực bằng Bearer token.

Public URL = ai cũng gọi được. Không có lớp này, hóa đơn LLM của bạn do
người lạ quyết định.

Chuẩn dùng ở đây là **RFC 6750** — token đi trong header ``Authorization``:

    Authorization: Bearer <token>

Đây là cách mọi API lớn (GitHub, Stripe, OpenAI) nhận token, nên client viết
bằng ngôn ngữ nào cũng có sẵn thư viện hiểu nó.
"""

from __future__ import annotations

import secrets

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBearer

from .config import get_settings

ANONYMOUS_CLIENT = "anonymous"
SCHEME = "Bearer"

security_scheme = HTTPBearer(auto_error=False)


def verify_bearer_token(
    authorization: str | None = Header(default=None),
    x_client_id: str | None = Header(default=None),
    _credentials: object | None = Depends(security_scheme),
) -> str:
    """Kiểm tra header ``Authorization``; trả về client_id nếu hợp lệ.

    Mọi trường hợp thất bại dùng **cùng một** thông báo: nói rõ "sai scheme"
    hay "token không đúng" là tặng thông tin cho người đang dò. Header
    ``WWW-Authenticate`` là bắt buộc theo chuẩn HTTP cho response 401.

    client_id trả về là đơn vị để rate limit và tính chi phí.
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="invalid or missing bearer token",
        headers={"WWW-Authenticate": SCHEME},
    )

    if not authorization:
        raise unauthorized

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != SCHEME.lower() or not token:
        raise unauthorized

    # compare_digest luôn chạy hết chuỗi; `==` dừng ở ký tự đầu khác nhau nên
    # thời gian trả lời rò rỉ thông tin về token (timing attack).
    if not secrets.compare_digest(token, get_settings().api_token):
        raise unauthorized

    return x_client_id or ANONYMOUS_CLIENT
