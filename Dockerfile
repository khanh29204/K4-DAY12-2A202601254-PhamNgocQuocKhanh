# ═══════════════════════════════════════════════════════════════════
# CP2 — Containerization (bản production-ready)
#
# Kiểm tra:  pytest tests/test_cp2.py -v
# Build thử: docker build -t day12-chat:prod .
#            docker images day12-chat:prod     # xem dung lượng
# ═══════════════════════════════════════════════════════════════════

# ─── Stage 1: builder ───────────────────────────────────────────────
# Cài dependency ở đây. Mọi thứ nặng nề của quá trình build (compiler,
# header file, cache của pip) nằm lại trong stage này, không đi tiếp sang
# image cuối.
FROM python:3.11-alpine AS builder

WORKDIR /app

# COPY requirements.txt TRƯỚC source code: Docker cache theo layer, nên sửa
# một dòng code không làm mất cache của bước cài thư viện.
COPY requirements.txt .

# --user cài vào /root/.local — một thư mục duy nhất, dễ copy sang stage sau.
# --no-cache-dir để pip không giữ lại bản tải về.
RUN pip install --no-cache-dir --user -r requirements.txt

# ─── Stage 2: runtime ───────────────────────────────────────────────
# Image thật sự chạy: Python alpine + thư viện đã cài, không có toolchain build.
FROM python:3.11-alpine AS runtime

# curl cho HEALTHCHECK. `--no-cache` để apk không giữ lại index gói trong image.
RUN apk add --no-cache curl

# Chạy bằng user thường: ai thoát được khỏi app cũng chỉ là `appuser`, không
# phải root trên host.
RUN adduser -D -h /home/appuser -u 10001 appuser

WORKDIR /app

# Không ghi .pyc; log ra stdout ngay không đệm — quan trọng khi log JSON được
# orchestrator thu thập theo dòng.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/home/appuser/.local/bin:$PATH \
    PORT=8000

# Chỉ mang sang kết quả của bước cài, không mang theo pip cache hay compiler
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local

# COPY source SAU pip install để giữ nguyên cache layer dependency
COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser utils ./utils

USER appuser

EXPOSE 8000

# Docker tự gọi /healthz; container không còn phục vụ được sẽ bị đánh dấu
# unhealthy để orchestrator thay thế.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT}/healthz" || exit 1

# Đọc cổng từ biến môi trường PORT — cloud (Cloud Run, Railway, Render) tự gán
# cổng lúc chạy, không cố định 8000. Cần shell để nội suy ${PORT}, nhưng phải
# có `exec`: không có nó thì /bin/sh là PID 1 và SIGTERM dừng ở sh, uvicorn
# không bao giờ nhận được tín hiệu → graceful shutdown ở CP4 vô hiệu.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
