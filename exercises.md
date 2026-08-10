# Phiếu Phản Ánh — K4 Ngày 12

> **Bài làm cá nhân.** Trả lời bằng lời của chính bạn, dựa trên những gì bạn
> quan sát được khi chạy code — không sao chép đáp án của người khác.
>
> Cách trả lời: thay dòng `> *Câu trả lời của bạn*` bằng câu trả lời.
> `grade.py` đếm số câu đã trả lời (15 điểm cho 10 câu).
>
> Họ và tên: Phạm Ngọc Quốc Khánh  Mã học viên: 2A202601254

---

### Câu 1 — Fail fast (CP1)

Trong `Settings`, `api_token` không có giá trị mặc định nên app chết ngay khi
khởi động nếu thiếu biến môi trường. Hãy mô tả một tình huống cụ thể mà việc
"chết sớm" này cứu bạn, so với việc để mặc định `"changeme"`.

> *Nếu đặt api_token mặc định và production thiếu api_token sẽ khiến app hoạt động với giá trị mặc định này, các hacker hoặc bot có thể truy cập api_token này và thực hiện các hành động không mong muốn.*

---

### Câu 2 — Log cho máy đọc (CP1)

Chạy service và gọi `/chat` vài lần. Dán một dòng log JSON bạn thu được, rồi
nêu **hai** việc bạn làm được với dòng log đó mà `print("đã trả lời xong")`
không làm được.

> *Hai dòng lấy từ log thật của service (`docker logs`):*
>
> ```json
> {"event": "chat_completed", "severity": "INFO", "ts": "2026-08-10T09:28:53.892486+00:00", "client_id": "sv-reflect", "prompt_tokens": 48, "completion_tokens": 49, "usd_cost": 3.66e-05}
> {"event": "http_request", "severity": "INFO", "ts": "2026-08-10T09:30:55.165838+00:00", "message": "172.24.0.1:59332 - \"GET /ads.txt HTTP/1.0\" 404", "logger": "uvicorn.access", "client_addr": "172.24.0.1:59332", "method": "GET", "path": "/ads.txt", "http_version": "1.0", "status": 404}
> ```
>
> *Hai việc tôi làm được mà `print("đã trả lời xong")` không làm được:*
>
> *1. **Cộng/lọc theo trường để ra một con số.** `usd_cost` là một field riêng
> nên tôi cộng dồn được theo `client_id`: `... | jq 'select(.event=="chat_completed")
> | .usd_cost' | paste -sd+ | bc` ra đúng số tiền hôm nay, và
> `group by .client_id` cho biết client nào đốt nhiều nhất. Câu
> "đã trả lời xong" không có số nào để cộng — muốn biết tiền thì phải chờ hóa đơn.*
>
> *2. **Đặt cảnh báo tự động và phân biệt được traffic lạ.** `status` là số nên
> viết được luật "đếm status >= 500 trong 5 phút, quá 10 thì báo" mà không cần
> regex. Thực tế trên VPS của tôi, lọc theo `path` thấy `/ads.txt`,
> `/app-ads.txt`, `/sellers.json`, `/favicon.ico` cùng trả 404 từ một
> `client_addr` duy nhất trong vòng 10 giây — đó là bot đang quét, khác hẳn
> `/healthz` 200 đều đặn 30 giây một lần của healthcheck. Nhìn một đống dòng
> chữ giống nhau thì không tách được hai loại traffic này.*

---

### Câu 3 — Kích thước image (CP2)

Build cả hai phiên bản và ghi lại số đo thật:

```bash
docker build -f Dockerfile-1-state -t chat:single .
docker build -t chat:multi .
docker images | grep chat
```

| Bản | Dung lượng |
|-----|-----------|
| 1 stage (bản đầu) | 171 MB |
| Multi-stage | 171 MB |

Giải thích: phần dung lượng chênh lệch đó là những gì?

> *cả 2 không chênh lệch nhau vì các thư viện trong requirements.txt đều là thư viện Python thuần hoặc đã có sẵn wheel tương thích với Alpine, Quá trình build không cần cài đặt thêm các công cụ biên dịch C/C++ nặng nề (như gcc, musl-dev, make)*

---

### Câu 4 — Thứ tự lệnh trong Dockerfile (CP2)

Sửa một ký tự trong `app/main.py` rồi build lại. Với Dockerfile của bạn, những
layer nào được dùng lại từ cache, layer nào phải chạy lại? Nếu bạn đặt
`COPY . .` lên trước `RUN pip install` thì kết quả khác thế nào?

> *Tôi chạy thật: thêm một dòng comment vào `app/main.py` rồi
> `docker build -t chat:multi .`, log build cho thấy:*
>
> ```
> #7 [builder 2/4] WORKDIR /app                      CACHED
> #8 [builder 3/4] COPY requirements.txt .           CACHED
> #10 [builder 4/4] RUN pip install -r requirements  CACHED
> #14 [runtime 6/7] COPY app ./app                   DONE 0.2s   ← chạy lại
> #15 [runtime 7/7] COPY utils ./utils               DONE 0.2s   ← chạy lại
> ```
>
> *Layer `pip install` được dùng lại từ cache; chỉ layer `COPY app` (chứa
> `main.py` vừa sửa) và layer `COPY utils` phải chạy lại. Lý do: Docker cache
> theo layer, mỗi layer là khác biệt của layer trước với thư mục build đã chỉ
> định. `COPY app ./app` kiểm tra checksum thư mục `app` — thay đổi rồi thì
> layer đó và mọi layer sau nó được dựng lại, còn các layer trước nó giữ
> nguyên.*
>
> *Nếu đặt `COPY . .` lên trước `RUN pip install` thì mọi thay đổi trong
> `app/` (thậm chí cả `README.md`) đều phá cache của layer `COPY . .`, và vì
> `RUN pip install` nằm sau, nó cũng phải chạy lại — mỗi lần sửa code lại tải
> và cài lại toàn bộ thư viện (~30–60 giây thêm cho mỗi build, lặp lại ở mọi
> máy CI). Trình tự hiện tại "copy requirements trước, cài sau, copy code
> cuối" khiến việc sửa code chỉ tốn 0.2 giây.*

---

### Câu 5 — Vì sao không chạy bằng root (CP2)

Container mặc định chạy bằng root. Mô tả chuỗi sự kiện dẫn từ "một lỗ hổng
trong code Python của bạn" tới "kẻ tấn công có quyền cao trên máy host", và
lệnh `USER` cắt đứt chuỗi đó ở chỗ nào.

> *Chuỗi sự kiện:*
>
> *1. Code Python của tôi có lỗ hổng cho phép chạy lệnh tùy ý — ví dụ một
> endpoint truyền input người dùng vào `subprocess`, hoặc một thư viện trong
> `requirements.txt` dính CVE deserialize. Kẻ tấn công gửi request và chạy
> được lệnh trong container.*
>
> *2. Lệnh đó chạy với UID của process. Mặc định là 0 (root), nên kẻ tấn công
> đọc được mọi file trong container: biến môi trường chứa `API_TOKEN`,
> `REDIS_URL` có mật khẩu. Chúng còn `apk add` thêm công cụ để dò tiếp.*
>
> *3. Đây là bước quan trọng: UID trong container và UID trên host là **cùng
> một con số** — Docker không bật user namespace mặc định. Root trong
> container chính là UID 0 của kernel host, chỉ bị giới hạn bởi namespace và
> capability.*
>
> *4. Từ UID 0, kẻ tấn công tìm đường ra: nếu có bind mount thì ghi file vào
> host với quyền root (ví dụ thêm SSH key vào `/root/.ssh`); nếu
> `/var/run/docker.sock` bị mount thì tạo container mới mount `/` của host —
> xong, root trên host. Không có đường nào thì vẫn còn các CVE escape của
> runc/kernel, mà hầu hết đều cần capability chỉ root mới có.*
>
> *`USER appuser` (uid 10001) trong Dockerfile cắt chuỗi ở **bước 2 sang bước
> 3***. *Lệnh của kẻ tấn công chạy với uid 10001: không `apk add` được, không
> ghi được file thuộc root, không có `CAP_SYS_ADMIN` nên các exploit ở bước 4
> hết đường. Quan trọng nhất, nếu có bind mount thì file ghi ra host mang uid
> 10001 — một user không tồn tại, không đặc quyền gì — chứ không phải root.
> Lỗ hổng vẫn là lỗ hổng, nhưng thiệt hại dừng trong phạm vi container.*

---

### Câu 6 — Bearer token (CP3)

Vì sao 401 phải kèm header `WWW-Authenticate: Bearer`? Và vì sao ta trả **cùng
một** thông báo lỗi cho cả ba trường hợp (thiếu header, sai scheme, sai token)
thay vì nói rõ sai ở đâu cho người dùng dễ sửa?

> *Về `WWW-Authenticate: Bearer` — RFC 7235 quy định response 401 **bắt buộc**
> phải có header này, nó cho client biết "cần xác thực bằng cách nào". Không
> có nó thì 401 chỉ là một lời từ chối cụt lủn: client (và thư viện HTTP) phải
> đoán xem nên gửi Basic, Bearer hay API key. Có nó thì thư viện tự biết đường
> gắn `Authorization: Bearer <token>` và thử lại. Trong `app/auth.py` tôi đặt
> header này ngay trong object `unauthorized` để cả ba nhánh lỗi đều trả về
> đúng chuẩn.*
>
> *Về việc dùng chung một thông báo — vì thông báo lỗi chi tiết là món quà cho
> người đang dò, không phải cho người dùng thật. Nếu phân biệt "thiếu header"
> / "sai scheme" / "sai token" thì kẻ tấn công có một oracle: gửi thử một token
> bất kỳ, thấy trả về "sai token" (thay vì "sai scheme") tức là định dạng đã
> đúng, chỉ còn dò giá trị — và chúng biết mình đang đi đúng hướng. Với một
> thông báo duy nhất, chúng không phân biệt được "gần đúng" và "sai hoàn
> toàn".*
>
> *Điều này cũng đồng bộ với lý do dùng `secrets.compare_digest` thay cho `==`:
> `==` dừng ở ký tự đầu tiên khác nhau nên thời gian trả lời rò rỉ thông tin
> về token. Chặn rò rỉ qua nội dung thông báo mà vẫn để rò rỉ qua thời gian thì
> chỉ là làm nửa vời.*
>
> *Còn người dùng hợp lệ thì không thiệt gì: họ có token đúng, đọc tài liệu là
> biết cần gửi header nào. Người thật sự cần thông tin chi tiết là người vận
> hành — và chi tiết đó nằm trong log phía server, nơi kẻ tấn công không đọc
> được.*

---

### Câu 7 — Token bucket (CP3)

Với `capacity=10`, `refill_per_minute=10`: một client im lặng 10 phút rồi gửi
liên tiếp. Nó gửi được bao nhiêu request trước khi bị 429? Nếu bỏ đoạn
`min(capacity, ...)` trong `available()` thì con số đó thành bao nhiêu, và tại sao?

> *Tôi kiểm chứng bằng script chạy thật (fakeredis, tiêm thời gian giả để khỏi
> phải chờ 10 phút): tiêu hết xô, nhảy thời gian tới `t0 + 600`, rồi gọi liên
> tiếp tới khi 429.*
>
> *Kết quả: **10 request** rồi 429. Xô đầy nhất chỉ là `capacity = 10`, dù im
> lặng bao lâu đi nữa. 10 phút im lặng nạp được 10 × 10 = 100 token, nhưng
> `min(capacity, tokens)` cắt xuống 10.*
>
> *Bỏ `min(capacity, ...)`: **100 request** rồi mới 429 — tôi chạy lại script
> với bản `available()` không chặn trần và ra đúng con số này. Vì công thức
> `tokens += (now - last) * refill_per_second` cộng tuyến tính không giới hạn:
> 600 giây × (10/60) token mỗi giây = 100 token.*
>
> *Đây chính là điểm phân biệt token bucket với "cộng dồn vô hạn". `capacity`
> là **trần của cú bung** (burst) — thứ quyết định service chịu tải bao nhiêu
> trong một khoảnh khắc; `refill_per_minute` là **tốc độ trung bình dài hạn**.
> Bỏ trần đi thì tốc độ trung bình vẫn đúng 10/phút, nhưng burst thành vô hạn:
> client im lặng một ngày tích 14.400 token và bắn hết trong một giây, đủ để
> hạ service dù "trung bình" vẫn trong hạn mức. Rate limit sinh ra để chặn
> đúng khoảnh khắc đó, nên trần là phần không thể bỏ.*

---

### Câu 8 — Ngân sách theo ngày (CP3)

So sánh hạn mức $30/tháng với hạn mức $1/ngày cho cùng một client. Giả sử có sự
cố khiến một client gọi liên tục từ 2h sáng. Với mỗi cách, thiệt hại tối đa là
bao nhiêu và service tự hồi phục khi nào?

> ***Hạn mức $30/tháng.** Sự cố bắt đầu 2h sáng ngày 1. Client gọi liên tục,
> chi phí cộng dồn vào một cái quota duy nhất cho cả tháng — không có gì chặn
> nó tiêu hết $30 ngay trong ngày đầu. Thiệt hại tối đa: **$30**, và nó xảy ra
> trong vài giờ chứ không phải rải đều 30 ngày. Tệ hơn phần tiền là phần dịch
> vụ: quota cạn lúc 5h sáng ngày 1 thì service trả 402 cho **mọi** request
> đến hết tháng. Hồi phục: **00:00 ngày 1 tháng sau** — tức là gần 30 ngày
> chết, và chắc chắn phải có người vào nâng hạn mức bằng tay.*
>
> ***Hạn mức $1/ngày** (bản tôi làm — `CostGuard._key()` gắn nhãn ngày vào khóa
> Redis `spend:<client>:<YYYY-MM-DD>`). Cùng sự cố đó: client tiêu hết $1 lúc
> khoảng 2h30, từ đó nhận 402. Thiệt hại tối đa: **$1** cho ngày hôm đó. Hồi
> phục: **00:00 UTC hôm sau, tự động** — vì `today()` trả nhãn ngày mới nên
> `_key()` trỏ sang một khóa Redis khác, chưa tồn tại, `spent()` đọc ra 0.0.
> Không ai phải thức dậy làm gì cả.*
>
> *Ba điểm khác biệt tôi thấy đáng giá nhất:*
>
> *1. **Thiệt hại nhỏ hơn 30 lần** ($1 so với $30) cho cùng một sự cố.*
>
> *2. **Tự hồi phục.** Hạn mức tháng cần con người can thiệp mới sống lại;
> hạn mức ngày tự hết hạn. Sự cố xảy ra lúc 2h sáng thì việc "không cần ai
> thức dậy" mới là giá trị thật.*
>
> *3. **Phát hiện sớm.** Với hạn mức tháng, ngày 1 tiêu $5 trông vẫn "bình
> thường" (mới 1/6 quota) nên không ai để ý — chỉ đến ngày 20 hết tiền mới
> biết. Với hạn mức ngày, chạm trần là biết ngay hôm đó có gì bất thường.*
>
> *Đánh đổi: ngày cao điểm hợp lệ cũng bị chặn ở $1 dù cả tháng chưa tiêu tới
> $30. Với tôi đây là đánh đổi đúng — chặn nhầm một client đang dùng thật thì
> họ báo và tôi nâng hạn mức; để lọt một sự cố thì tôi mất tiền và không biết.*

---

### Câu 9 — /healthz khác /readyz (CP4)

Nếu gộp hai endpoint làm một và cho nó kiểm tra Redis, chuyện gì xảy ra với cụm
3 container khi Redis mất kết nối 30 giây? Trả lời theo đúng thứ tự sự kiện.

> *Giả định theo cấu hình thật của tôi: `HEALTHCHECK --interval=30s
> --timeout=3s --retries=3` trong Dockerfile, và endpoint gộp đó vừa là
> liveness probe (sai → restart) vừa là readiness probe (sai → ngừng gửi
> traffic).*
>
> *`T+0s` — Redis mất kết nối. Cả 3 container vẫn đang chạy bình thường,
> `/chat` bắt đầu lỗi nhưng process không chết.*
>
> *`T+0..30s` — Lần probe kế tiếp: `store.ping()` trả False ở **cả 3
> container cùng lúc** (chúng nhìn vào cùng một Redis, nên hỏng là hỏng đồng
> loạt — không có container nào "may mắn" hơn). Endpoint gộp trả 503. Đây là
> điểm cốt tử: một tín hiệu 503 duy nhất mang hai nghĩa xung đột, và
> orchestrator buộc phải hiểu nó theo cả hai.*
>
> *`T+30..90s` — Load balancer thấy 503 nên rút cả 3 instance khỏi vòng xoay:
> **không còn instance nào nhận traffic**, người dùng nhận 502/503 từ Nginx.
> Song song, healthcheck đếm `retries`: sau 3 lần liên tiếp fail (~90 giây)
> container bị đánh dấu unhealthy và bị **restart**.*
>
> *`T+~90s` — Cả 3 container restart đồng thời (đây là chỗ tệ nhất: không có
> container nào giữ lại được để phục vụ). Chúng khởi động lại, nhưng Redis vẫn
> chưa lên, nên probe lại 503, lại restart. Với `restart: unless-stopped`,
> đây là **crash-loop**.*
>
> *`T+30s` — Redis thực ra đã hồi phục ở đây rồi. Nhưng cả 3 container đang ở
> giữa chu kỳ restart nên chưa phục vụ được ngay: phải chờ container khởi động
> xong, chờ hết `start_period=10s`, chờ probe kế tiếp xanh, rồi load balancer
> mới đưa trở lại vòng xoay. Ngoài ra Docker áp backoff tăng dần cho container
> restart liên tục, nên lần restart sau chờ lâu hơn lần trước.*
>
> *Kết quả: **Redis chết 30 giây, service chết vài phút.** Sự cố tự nhân lên
> nhiều lần so với nguyên nhân, và toàn bộ phần nhân lên đó do chính cơ chế
> "chữa bệnh" gây ra.*
>
> *Tách hai endpoint thì chuyện xảy ra khác hẳn: `/readyz` đỏ nên load
> balancer tạm ngừng đẩy traffic, `/healthz` vẫn xanh (không chạm Redis) nên
> **không container nào bị restart**. Đúng `T+30s` Redis lên, probe kế tiếp
> xanh, cả 3 instance quay lại vòng xoay ngay — process vẫn sống nguyên,
> không có gì phải khởi động lại. Đây là lý do tôi giữ `/healthz` nhẹ, không
> gọi Redis, còn `/readyz` mới được phép kiểm tra dependency.*

---

### Câu 10 — Deploy thật (CP5)

Ghi lại **một** lỗi bạn gặp khi deploy lên cloud (build fail, health check
timeout, sai REDIS_URL, app không đọc `$PORT`...): thông báo lỗi là gì, bạn
tìm ra nguyên nhân bằng cách nào, và sửa ra sao?

> *Lỗi tôi gặp: **job `deploy` trên GitHub Actions fail ở bước SSH vào VPS**
> (commit sửa: `2ba511a fix: fix ssh`). Hai job `test` và `build` đều xanh,
> image đã đẩy lên GHCR thành công, nhưng bước cuối không vào được server nên
> bản mới không bao giờ tới VPS.*
>
> *Thông báo lỗi trong log của `appleboy/ssh-action`:*
>
> ```
> ssh: handshake failed: ssh: unable to authenticate,
> attempted methods [none publickey], no supported methods remain
> ```
>
> *Cách tìm ra nguyên nhân: dòng `attempted methods [none publickey]` nói rõ
> client chỉ thử mỗi publickey — tức là action có đọc được `SERVER_SSH_KEY`
> nhưng server không chấp nhận. Tôi loại trừ dần: `SERVER_HOST` và
> `SERVER_PORT` đúng (nếu sai thì lỗi phải là `connection refused` hoặc
> timeout, không phải `handshake failed`), nên vấn đề nằm ở khâu xác thực.
> Tôi SSH tay từ máy mình vào VPS bằng đúng user đó và thành công — bằng mật
> khẩu, không phải key. Đến đây thì rõ: tôi chưa hề đưa public key nào vào
> `~/.ssh/authorized_keys` trên VPS, nên phía server không có gì để đối chiếu,
> còn secret `SERVER_SSH_KEY` thì trống.*
>
> *Cách sửa: đổi sang xác thực bằng mật khẩu — thêm secret `SERVER_PASSWORD`
> và sửa `.github/workflows/ci.yml` từ `key: ${{ secrets.SERVER_SSH_KEY }}`
> thành `password: ${{ secrets.SERVER_PASSWORD }}`. Push lại thì job `deploy`
> xanh, `docker compose pull` và `up -d` chạy trên VPS, bản mới lên sống.*
>
> *Một thay đổi nữa tôi làm cùng commit đó: thêm `paths:` vào trigger để
> workflow chỉ chạy khi `app/`, `utils/`, `Dockerfile`, `requirements.txt`,
> `docker-compose.yml` hoặc `.github/workflows/` đổi — sửa README thì không
> cần build lại image và deploy lại.*
>
> *Điều tôi rút ra: dùng mật khẩu là cách nhanh nhất để job xanh, nhưng đó
> không phải cách đúng lâu dài — mật khẩu SSH đi qua CI thì mọi người có quyền
> sửa workflow đều dùng lại được, và nó cũng mở cửa cho brute-force vào port
> SSH. Việc nên làm tiếp là sinh một cặp key riêng cho deploy, đưa public key
> vào `authorized_keys` của VPS, cất private key vào `SERVER_SSH_KEY`, rồi tắt
> `PasswordAuthentication` trong `sshd_config`.*
