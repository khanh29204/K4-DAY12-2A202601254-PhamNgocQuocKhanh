# Thông Tin Deploy — Checkpoint 5

## Thông Tin Học Viên

| Mục | Nội dung |
|-----|----------|
| Họ và tên | Phạm Ngọc Quốc Khánh |
| Mã học viên | 2A202601254 |
| Repo | https://github.com/khanh29204/K4-DAY12-2A202601254-PhamNgocQuocKhanh.git |

## Service

| Mục | Nội dung |
|-----|----------|
| Public URL | https://day12.quockhanh020924.id.vn |
| Platform | vps |
| Ngày deploy | 10/08/2026 |

## Biến Môi Trường Đã Set Trên Cloud

Ghi tên biến và **nguồn giá trị**, không ghi giá trị:

| Biến | Đã set | Ghi chú |
|------|--------|---------|
| `PORT` | ✅ | trong file .env |
| `API_TOKEN` | ✅ | trong file.env |
| `REDIS_URL` | ✅ | trong file .env |
| `BUCKET_CAPACITY` | ✅ | 10 |
| `REFILL_PER_MINUTE` | ✅ | 10 |
| `DAILY_BUDGET_USD` | ✅ | 1.0 |
| `LOG_LEVEL` | ✅ | INFO |

## Lệnh Kiểm Tra

Thay `<URL>` bằng Public URL ở trên:

```bash
# 1. Liveness — mong đợi 200 {"status":"ok"}
curl -i https://day12.quockhanh020924.id.vn/healthz

# 2. Readiness — mong đợi 200 {"status":"ready"} (đã nối được Redis)
curl -i https://day12.quockhanh020924.id.vn/readyz

# 3. Không có token — mong đợi 401 kèm header WWW-Authenticate
curl -i -X POST https://day12.quockhanh020924.id.vn/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello"}'

# 4. Có token — mong đợi 200 kèm câu trả lời
curl -i -X POST https://day12.quockhanh020924.id.vn/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "X-Client-Id: sv-test" \
  -d '{"message":"Deploy là gì?"}'

# 5. Rate limit — gọi 15 lần, những lần cuối phải trả 429
for i in $(seq 1 15); do
  curl -s -o /dev/null -w "%{http_code} " -X POST https://day12.quockhanh020924.id.vn/chat \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $API_TOKEN" \
    -H "X-Client-Id: sv-test" \
    -d '{"message":"test"}'
done; echo
```

## Kết Quả Chạy Thật

Dán output của các lệnh trên vào đây:
1. Liveness
```
curl -i https://day12.quockhanh020924.id.vn/healthz

HTTP/2 200 
server: nginx/1.18.0 (Ubuntu)
date: Mon, 10 Aug 2026 09:02:55 GMT
content-type: application/json
content-length: 64

{"status":"ok","service":"day12-chat-service","version":"1.0.0"}
```
2. Readiness
```
curl -i https://day12.quockhanh020924.id.vn/readyz

HTTP/2 200 
server: nginx/1.18.0 (Ubuntu)
date: Mon, 10 Aug 2026 09:03:35 GMT
content-type: application/json
content-length: 31

{"status":"ready","redis":true}
```
3. Không có token
```
curl -i -X POST https://day12.quockhanh020924.id.vn/chat \
          -H "Content-Type: application/json" \
          -d '{"message":"Hello"}'
HTTP/2 401 
server: nginx/1.18.0 (Ubuntu)
date: Mon, 10 Aug 2026 09:04:06 GMT
content-type: application/json
content-length: 44
www-authenticate: Bearer

{"detail":"invalid or missing bearer token"}
```
4. Có token
```
curl -i -X POST https://day12.quockhanh020924.id.vn/chat \                                                                ↵ 2
          -H "Content-Type: application/json" \
          -H "Authorization: Bearer $API_TOKEN" \
          -H "X-Client-Id: sv-test" \
          -d '{"message":"Deploy là gì?"}'
HTTP/2 200 
server: nginx/1.18.0 (Ubuntu)
date: Mon, 10 Aug 2026 09:05:46 GMT
content-type: application/json
content-length: 288

{"reply":"Câu hỏi hay. Deploy là gì thường được giải quyết bằng cách chuẩn hóa môi trường chạy: cùng một image chạy giống nhau ở laptop và trên cloud.","client_id":"sv-test","turns_before":0,"usd_cost":2.145e-05,"usage":{"prompt":3,"completion":35}}
```
5. Rate limit
```
for i in $(seq 1 15); do
  curl -s -o /dev/null -w "%{http_code} " -X POST https://day12.quockhanh020924.id.vn/chat \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $API_TOKEN" \
    -H "X-Client-Id: sv-test" \
    -d '{"message":"test"}'
done; echo
200 200 200 200 200 200 200 200 200 200 429 429 429 429 429 
```

## Ảnh Chụp Màn Hình

Đặt ảnh trong thư mục `screenshots/`:

- `screenshots/dashboard.png` — trang quản lý service trên platform
- `screenshots/healthz.png` — kết quả gọi `/healthz` từ trình duyệt hoặc curl

---