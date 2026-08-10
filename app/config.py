"""CP1 — Cấu hình theo 12-Factor.

Nguyên tắc: **không có giá trị cấu hình nào nằm trong code**. Tất cả đến từ
biến môi trường, để cùng một image chạy được ở laptop, staging và production
mà không phải sửa một dòng code nào.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Giá trị mẫu trong .env.example. Ai copy file mẫu mà quên đổi thì token của
# họ chính là chuỗi này — và nó nằm công khai trong repo, tức là ai cũng gọi
# được /chat. Chặn ngay lúc khởi động thay vì để phát hiện qua hóa đơn.
PLACEHOLDER_TOKENS = frozenset(
    {
        "doi-thanh-token-cua-rieng-ban",
        "change-me",
        "changeme",
        "your-token-here",
        "todo",
        "xxx",
    }
)

MIN_TOKEN_LENGTH = 8


class Settings(BaseSettings):
    """Toàn bộ cấu hình của service.

    pydantic-settings tự đọc biến môi trường theo tên trường (không phân biệt
    hoa thường), nên trường ``api_token`` sẽ lấy giá trị từ biến ``API_TOKEN``.

    | Trường            | Kiểu  | Mặc định                   |
    |-------------------|-------|----------------------------|
    | port              | int   | 8000                       |
    | api_token         | str   | KHÔNG có mặc định (bắt buộc)|
    | redis_url         | str   | "redis://localhost:6379/0" |
    | bucket_capacity   | int   | 10                         |
    | refill_per_minute | int   | 10                         |
    | daily_budget_usd  | float | 1.0                        |
    | log_level         | str   | "INFO"                     |

    Vì sao ``api_token`` không được có giá trị mặc định? Vì mặc định nghĩa là
    app vẫn khởi động khi bạn quên set secret trên cloud — và bạn chỉ phát
    hiện ra khi ai đó đã gọi API miễn phí bằng token mặc định đó. Không mặc
    định = fail fast ngay lúc khởi động.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # api_token không có mặc định → thiếu biến môi trường là app chết ngay
    port: int = 8000
    api_token: str
    redis_url: str = "redis://localhost:6379/0"
    bucket_capacity: int = 10
    refill_per_minute: int = 10
    daily_budget_usd: float = 1.0
    log_level: str = "INFO"

    @field_validator("api_token")
    @classmethod
    def _token_phai_dung_that(cls, value: str) -> str:
        """Chặn cả ba kiểu "có set nhưng vô nghĩa": rỗng, quá ngắn, placeholder.

        Trường bắt buộc mới chỉ chặn được trường hợp *quên* set. ``API_TOKEN=``
        (rỗng) hay ``API_TOKEN=changeme`` vẫn qua được — mà về mặt bảo mật thì
        chúng không khác gì không có token.
        """
        token = value.strip()
        if not token:
            raise ValueError(
                "API_TOKEN rỗng. Sinh token mới: "
                'python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )
        if token.lower() in PLACEHOLDER_TOKENS:
            raise ValueError(
                f"API_TOKEN vẫn đang là giá trị mẫu ({token!r}) — giá trị này nằm "
                "công khai trong repo, ai cũng gọi được /chat. Đổi thành token "
                "của riêng bạn."
            )
        if len(token) < MIN_TOKEN_LENGTH:
            # Cảnh báo chứ không chặn: token ngắn vẫn là token thật (test và
            # môi trường dev dùng chuỗi ngắn), nhưng người vận hành nên thấy
            # dòng này trong log lúc khởi động.
            from .logging_utils import emit

            emit(
                "weak_api_token",
                severity="WARNING",
                token_length=len(token),
                minimum=MIN_TOKEN_LENGTH,
                hint="sinh token mạnh: python -c \"import secrets; "
                'print(secrets.token_urlsafe(32))"',
            )
        return token

    @field_validator("log_level")
    @classmethod
    def _log_level_hop_le(cls, value: str) -> str:
        """LOG_LEVEL sai chính tả sẽ âm thầm tắt hết log — bắt lỗi ngay tại đây."""
        from .logging_utils import SEVERITY_LEVELS

        level = value.strip().upper()
        if level not in SEVERITY_LEVELS:
            raise ValueError(
                f"LOG_LEVEL={value!r} không hợp lệ. "
                f"Chọn một trong: {', '.join(sorted(SEVERITY_LEVELS))}"
            )
        return level


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Đọc cấu hình một lần rồi cache lại (đọc env mỗi request là lãng phí)."""
    return Settings()
