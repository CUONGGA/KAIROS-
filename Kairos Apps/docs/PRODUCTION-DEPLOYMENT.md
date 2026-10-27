# Kairos Production Deployment and Readiness

Tài liệu này mô tả hướng triển khai Kairos lên production sau khi MVP đạt các gate chất lượng.
Đây là runbook định hướng và checklist ra quyết định, không phải xác nhận rằng hệ thống hiện tại đã
sẵn sàng production.

**Cập nhật trạng thái:** 2026-10-10

**Phạm vi:** một người dùng, một site Frappe, collector Codex chạy trên máy developer.

## 1. Hiện trạng thực tế

| Thành phần | Hiện trạng | Production readiness |
| --- | --- | --- |
| Frappe app | DocType, API ingest, Timeline, Summary, Copy và scheduler đã chạy local | Cần đóng các gate còn lại |
| Roadmap | C1–C5, C.5.1–C.5.3 và C.5.4a hoàn thành | C.5.4b/C.5.4c, C.5.5 và Phase D chưa hoàn thành |
| Runtime | Hai Bench development trong WSL: LMS và Kairos; Kairos dùng web `8002` | `bench start` không dùng cho production |
| Collector | Codex collector incremental, checkpoint, batch và Windows Task Scheduler | Cần đổi URL sang HTTPS production và kiểm tra token rotation/retry |
| Nguồn dữ liệu | Chỉ `codex` là nguồn MVP | Git, Cursor, ChatGPT, terminal vẫn là backlog |
| LLM | OpenAI-compatible Chat Completions; có fallback khi provider lỗi | Cần quota, timeout, provenance, evaluation và cảnh báo |
| Secrets | Local hỗ trợ `llm.env`; app ưu tiên OS env rồi fallback `site_config` | Production phải dùng site config hoặc secret injection của service/container |
| Database | MariaDB của site là nguồn sự thật | Chưa có bằng chứng backup/restore drill và retention policy |
| Operations | Có log Frappe, worker, scheduler và collector | Chưa có health check, alerting, dashboard hoặc incident runbook |
| Security | Có role collector và redaction trước LLM | Chưa hoàn tất hardening host, TLS, firewall và secret-rotation runbook |

Kết luận hiện tại: Kairos là **development MVP chạy được end-to-end**, nhưng **chưa production-ready**.
Việc chạy được trên WSL không thay thế các yêu cầu vận hành, bảo mật và khôi phục dữ liệu.

## 2. Phân biệt các scheduler

Kairos có hai scheduler độc lập:

1. **Windows Task Scheduler / B6** chạy trên máy developer, đọc Codex sessions và gửi
   `Kairos Event` lên API Frappe.
2. **Frappe Scheduler / C5** chạy trên server, dùng Event đã có để tạo hoặc làm mới
   `Kairos Day Report` lúc 18:30.

C5 không thu thập Event. Nếu collector B6 lỗi, C5 vẫn có thể chạy nhưng Timeline sẽ thiếu dữ liệu.
Production monitoring phải kiểm tra riêng cả hai luồng.

## 3. Kiến trúc production mục tiêu

```text
[Developer machine]
  Codex sessions
      -> kairos-codex collector
      -> HTTPS + dedicated Frappe token
              |
              v
[Production host / private network]
  Reverse proxy + TLS
      -> Frappe web / Gunicorn
      -> MariaDB: Kairos Event + Kairos Day Report
      -> Redis cache + queue
      -> background workers
      -> Frappe scheduler
              |
              v
  OpenAI-compatible LLM provider
```

Không mount thư mục Codex từ máy developer lên server. Collector chỉ gửi canonical Event qua HTTPS.
Không expose trực tiếp MariaDB, Redis hoặc development port ra Internet.

## 4. Chọn phương án triển khai

### Phương án khuyến nghị: container/Docker

Frappe hiện khuyến nghị container cho production mới. Container giúp định nghĩa rõ web, queue,
scheduler, Redis, database, volumes và secret injection; đồng thời dễ tái tạo môi trường hơn bare
metal.

Phù hợp khi:

- cần triển khai lặp lại hoặc chuyển máy;
- có người vận hành quen Docker/Compose;
- muốn quản lý secret bằng Docker/Kubernetes secret;
- muốn tách Kairos khỏi Bench LMS hoàn toàn.

Tham khảo tài liệu chính thức: [Frappe Docker](https://github.com/frappe/frappe_docker).

### Phương án chấp nhận được: Supervisor + Nginx trên Linux VPS

Frappe v15 vẫn hỗ trợ Supervisor quản lý process và Nginx làm reverse proxy. Không dùng
`bench start`; web, worker, scheduler và Redis phải được process manager tự khởi động lại.

Phù hợp khi:

- chỉ có một VPS nhỏ;
- đội vận hành đã quen Bench bare metal;
- có quy trình quản lý package, OS update và service rõ ràng.

Tham khảo: [Frappe v15 Production Setup](https://docs.frappe.io/framework/v15/user/en/bench/guides/setup-production).

Không nên tự tạo một shell wrapper chạy nền thay cho Docker, Supervisor hoặc systemd.
`scripts/run_kairos_bench.sh` chỉ phục vụ local development.

## 5. Quản lý cấu hình và secret

### Local development

- Collector đọc `~/.config/kairos/collector.env`.
- Wrapper local có thể đọc `~/.config/kairos/llm.env`.
- Không commit hai file này.

### Production một VPS đơn giản

Lưu cấu hình LLM theo site bằng Bench CLI:

```bash
bench --site <production-site> set-config kairos_llm_api_key "<secret>"
bench --site <production-site> set-config kairos_llm_base_url "<provider-base-url>"
```

`site_config.json` thuộc trạng thái của site, phải có quyền file hạn chế và nằm trong phạm vi backup
được bảo vệ. Không in `bench show-config` vào log công khai vì output có thể chứa secret.

### Production có secret manager/container

Inject `KAIROS_LLM_API_KEY` và `KAIROS_LLM_BASE_URL` vào **mọi** process cần dùng cấu hình:

- web;
- background worker;
- scheduler nếu sau này scheduler gọi LLM.

Kairos ưu tiên OS environment, sau đó mới fallback về `site_config`. Không phụ thuộc `source` từ
một terminal tương tác trong production.

### Collector credential

- Dùng user riêng có role `Kairos Collector`, không dùng Administrator.
- Token nằm trên máy developer, không nằm trên server LLM config.
- Production URL phải là HTTPS và dùng hostname ổn định, không dùng `127.0.0.1`.
- Có lịch rotate/revoke token và quy trình cấp lại khi máy developer bị mất.

Mọi key từng xuất hiện trong chat, log, shell history hoặc repository phải được coi là đã lộ và thu
hồi trước khi go-live.

## 6. Kế hoạch triển khai theo giai đoạn

### P0 — Đóng gate ứng dụng

- Hoàn thành C.5.4b: validated audit snapshot, evidence manifest, retention và admin-only audit access.
- Hoàn thành C.5.4c: async reliability, retry transient và metrics/log taxonomy.
- Hoàn thành C.5.5: golden evaluation dùng audit snapshot và collector conformance.
- Chạy Phase D ít nhất ba ngày làm việc thật.
- Ghi nhận tỷ lệ fallback, Event rác, latency và mức sửa tay của báo cáo.

### P1 — Chuẩn bị hạ tầng

- Chọn Docker hoặc Supervisor/Nginx và ghi decision record.
- Chuẩn bị Linux host/VPS riêng cho Kairos.
- Thiết lập domain, DNS, TLS và firewall.
- Chỉ mở các cổng cần thiết như SSH hạn chế, HTTP/HTTPS; không public Redis/MariaDB.
- Chuẩn bị persistent volumes hoặc backup path cho site, database và private files.
- Đồng bộ timezone host và site với `Asia/Ho_Chi_Minh`.

### P2 — Deploy app và schema

- Pin phiên bản Frappe, Kairos và dependency; không deploy trực tiếp từ working tree bẩn.
- Tạo production site và cài app Kairos.
- Chạy migration có backup trước đó.
- Build asset production.
- Cấu hình model, context budgets và prompt non-secret trong `Kairos Settings`.
- Cấu hình LLM secret ngoài DocType.

### P3 — Bật dịch vụ nền

- Web chạy bằng production WSGI/Gunicorn sau reverse proxy.
- Worker queue tự restart khi crash.
- Frappe Scheduler được bật và kiểm tra job C5.
- Redis và MariaDB có health check, persistence và giới hạn truy cập.
- Không chạy file watcher hoặc development debugger.

### P4 — Chuyển collector

- Tạo dedicated collector user/token trên production.
- Đổi `KAIROS_FRAPPE_URL` thành HTTPS production URL.
- Dry-run parser trước, sau đó sync một batch nhỏ.
- Xác nhận idempotency và `activity_date` theo timezone.
- Chỉ cập nhật checkpoint sau khi API trả thành công.
- Theo dõi log ít nhất một chu kỳ Task Scheduler đầy đủ.

### P5 — Backup, monitoring và bảo mật

- Lập lịch backup database, site config, public/private files theo chính sách retention.
- Mã hóa backup và tách backup khỏi production host.
- Thực hiện restore drill trên môi trường sạch; backup chưa restore thử không được coi là an toàn.
- Theo dõi web health, queue backlog, scheduler heartbeat, collector exit code và LLM fallback.
- Cảnh báo khi không có Event mới trong giờ làm việc hoặc collector liên tục exit khác `0`.
- Thiết lập log rotation; không log API key, token, raw payload nhạy cảm hoặc full prompt riêng tư.

### P6 — Cutover và rollback

- Chọn thời điểm ít hoạt động và tạo backup trước cutover.
- Chạy local và production ở chế độ quan sát có kiểm soát; tránh hai collector dùng checkpoint chung.
- So sánh Event count, Timeline và Summary trong một ngày mẫu.
- Ghi rõ tiêu chí rollback: lỗi ingest, mất Event, queue kẹt, LLM leak hoặc không restore được.
- Rollback app phải đi kèm đánh giá tương thích schema; không chỉ checkout code cũ.

## 7. Go-live gates bắt buộc

### Chức năng

- [ ] Collector production tạo/cập nhật Event idempotent.
- [ ] Timeline đúng ngày và timezone.
- [ ] Generate Summary dùng đúng model/provider.
- [ ] Fallback vẫn tạo report khi provider lỗi.
- [ ] Copy Summary và Summary + Timeline pass trên trình duyệt production.
- [ ] C5 scheduler tạo/làm mới draft đúng 18:30.

### Chất lượng LLM

- [ ] Không gửi `raw_payload`, secret hoặc absolute path tới provider.
- [ ] Structured output được validate và claim tham chiếu Event hợp lệ.
- [ ] Có provenance: model, prompt/context version và context hash.
- [ ] Có timeout, retry giới hạn và không retry vô hạn.
- [ ] Có quota/cost limit và cách tắt LLM khẩn cấp.

### Bảo mật

- [ ] Tất cả key đã lộ trong quá trình phát triển được revoke.
- [ ] Không có secret trong Git history, log, screenshot hoặc tài liệu.
- [ ] HTTPS hợp lệ; HTTP được redirect hoặc vô hiệu.
- [ ] Collector dùng least-privilege user/token.
- [ ] Redis và database không public Internet.
- [ ] File config/backup có quyền truy cập tối thiểu.
- [ ] OS, Python, Node, Frappe và dependency đã được đánh giá bản vá.

### Vận hành và khôi phục

- [ ] Web, worker, scheduler tự chạy lại sau reboot.
- [ ] Health check và alert hoạt động.
- [ ] Backup tự động chạy và có retention.
- [ ] Restore drill thành công, có ghi thời gian RPO/RTO thực tế.
- [ ] Có runbook xử lý collector lỗi, queue kẹt, provider lỗi và database đầy.
- [ ] Có người chịu trách nhiệm nhận cảnh báo và thực hiện rollback.

Chỉ go-live khi các gate bắt buộc phù hợp với phạm vi deployment đã được đánh dấu và có bằng chứng
kiểm thử. Không đánh dấu theo giả định.

## 8. Những điều đặc biệt đáng cân nhắc

### Dữ liệu công việc là dữ liệu nhạy cảm

Codex sessions có thể chứa source code, đường dẫn nội bộ, prompt, tên dự án và secret vô tình được
nhập. Redaction hiện có giảm rủi ro nhưng không thay thế data-classification policy, retention và
đánh giá điều khoản của LLM provider.

### Fallback có thể che giấu lỗi provider

Kairos cố ý tạo fallback để không mất Day Report. Vì report vẫn chuyển `ready`, người vận hành có
thể tưởng LLM hoạt động. Production phải ghi metric/cảnh báo riêng cho fallback reason.

### Checkpoint không phải nguồn sự thật

Checkpoint collector chỉ tối ưu incremental scan. Nguồn sự thật vẫn là sessions gốc ở máy developer
và DocType trên server. Mất checkpoint có thể làm sync lại nhiều dữ liệu nhưng `event_id` phải ngăn
duplicate.

### Hai timezone có thể làm lệch ngày

`occurred_at` lưu theo UTC, còn `activity_date` derive theo `Asia/Ho_Chi_Minh`. Host, database, Frappe
site và collector cần được kiểm thử quanh 00:00; không sửa ngày bằng giờ chạy scheduler.

### Một user không có nghĩa là không cần bảo mật

MVP một user vẫn có API ingest từ máy khác và dữ liệu công việc riêng tư. Dedicated token, TLS,
backup encryption, audit và revocation vẫn là yêu cầu production.

### Kairos và LMS phải được cô lập

Local hiện dùng hai Bench và hai bộ port. Production không nên dựa vào đổi port thủ công. Dùng
container/host/service namespace rõ ràng, domain riêng và cấu hình process manager riêng để tránh
khởi động nhầm Bench hoặc dùng nhầm Redis.

## 9. Quyết định chưa chốt

Trước khi triển khai thật cần chốt bằng văn bản:

1. Docker hay Supervisor/Nginx.
2. VPS/on-prem/cloud nào và ai quản trị.
3. Domain, TLS termination và network access policy.
4. Secret manager hay `site_config` được bảo vệ.
5. LLM provider/model, data-processing policy, quota và chi phí tối đa.
6. Backup retention, vị trí off-site, RPO và RTO.
7. Log/metric stack và kênh nhận cảnh báo.
8. Thời hạn lưu Event/raw payload và quyền xóa dữ liệu.
9. Tiêu chí kết thúc pilot và người phê duyệt go-live.

## 10. Trạng thái tài liệu

Tài liệu này phải được cập nhật khi một gate production thay đổi. Mỗi mục hoàn thành cần dẫn tới
bằng chứng: log kiểm thử, restore drill, screenshot cấu hình đã che secret, hoặc commit triển khai.
Không đưa secret thật vào bằng chứng.
