# Cài Kairos trên máy mới (Local Development)

Runbook này mô tả cách dựng Kairos từ một máy mới cho môi trường **local/dev**, một user, dùng
Windows + WSL2 hoặc Linux. Production dùng quy trình khác; xem
[PRODUCTION-DEPLOYMENT.md](PRODUCTION-DEPLOYMENT.md).

## 0. Kết quả cần đạt

Sau khi làm xong, máy sẽ có:

- Frappe Bench và site `kairos.local`.
- App `kairos` đã cài và migrate, có role `Kairos Collector` cùng default cho `Kairos Settings`.
- Desk mở được, tạo được `Kairos Event` và `Kairos Day Report`.
- Collector đọc Codex sessions, sync event lên Frappe.
- Timeline, Summary và Copy hoạt động end-to-end.
- (Tuỳ chọn) Windows Task Scheduler sync collector mỗi 30 phút.

## 1. Kiến trúc cần hiểu

```text
Codex sessions trên máy developer
  -> kairos-codex collector
  -> POST /api/method/kairos.api.upsert_events
  -> Kairos Event
  -> timeline.py
  -> Kairos Day Report
  -> summary.py -> LLM provider (hoặc fallback local)
```

Có hai scheduler độc lập:

1. **Collector scheduler** trên máy developer (Windows Task Scheduler qua WSL) đẩy event lên Frappe.
2. **Frappe scheduler** trên server chạy lúc `18:30` để tạo/làm mới timeline draft; job này không gọi LLM.

## 2. Yêu cầu môi trường

| Thành phần | Yêu cầu |
| --- | --- |
| OS | WSL2 Ubuntu 22.04/24.04 hoặc Linux. Không chạy Frappe Bench trực tiếp trên Windows. |
| Python | 3.10+ |
| Công cụ | Git, MariaDB, Redis, Node.js + Yarn, `frappe-bench` |
| Frappe | Bench v15 |
| Codex sessions | `~/.codex/sessions` trong WSL, hoặc `/mnt/c/Users/<windows-user>/.codex/sessions` nếu Codex chạy trên Windows |
| LLM | API key OpenAI-compatible. Có thể bỏ trống; summary sẽ dùng fallback local. |
| Timezone | Host/Bench nên đặt `Asia/Ho_Chi_Minh`; app cố định timezone này. |

Native Windows Python không có IANA timezone data. Collector dùng
`ZoneInfo("Asia/Ho_Chi_Minh")`, nên chạy trong WSL/Linux hoặc cài `tzdata` trước
(`python3 -m pip install tzdata`).

## 3. Lấy source code

Clone hoặc copy repo về máy. Repo này là monorepo; app Frappe nằm trong `Kairos Apps/kairos`.

Ví dụ đường dẫn trong WSL:

```text
/mnt/c/Projects/Kairos Apps
```

Các lệnh bên dưới dùng đường dẫn này. Nếu repo nằm ở chỗ khác, thay path tương ứng và luôn bọc
path có khoảng trắng trong dấu `"..."`.

## 4. Tạo Bench và site

Chạy ngoài repo, trong WSL/Linux:

```bash
# pipx tránh lỗi PEP 668 (externally-managed-environment) trên Ubuntu 22.04/24.04
sudo apt update
sudo apt install -y pipx
pipx ensurepath
export PATH="$HOME/.local/bin:$PATH"
pipx install frappe-bench

bench init "$HOME/kairos-bench" --frappe-branch version-15
cd "$HOME/kairos-bench"

bench new-site kairos.local
bench --site kairos.local set-config developer_mode 1
```

Nếu không dùng `pipx`, có thể tạo venv riêng:

```bash
python3 -m venv "$HOME/.bench-venv"
source "$HOME/.bench-venv/bin/activate"
pip install frappe-bench
```

`bench new-site` sẽ hỏi mật khẩu MariaDB root và mật khẩu Administrator. Ghi nhớ mật khẩu
Administrator để đăng nhập Desk.

Nếu `bench` không có trong PATH, dùng đường dẫn đầy đủ hoặc kích hoạt môi trường Python đã cài
`frappe-bench`.

## 5. Cài app Kairos

Vẫn trong thư mục Bench:

```bash
bench get-app --soft-link "/mnt/c/Projects/Kairos Apps/kairos"
bench --site kairos.local install-app kairos
bench --site kairos.local migrate
```

Dùng `--soft-link` vì `kairos/` nằm trong monorepo và không phải git repo riêng. Nếu bỏ `--soft-link`,
Bench sẽ cố `git clone` đường dẫn này và thất bại. Symlink cũng giúp sửa code trong repo là Bench thấy
ngay.

`migrate` tạo role `Kairos Collector` và seed các giá trị mặc định cho `Kairos Settings`. Chạy lại
lệnh này sau mỗi lần sửa JSON DocType.

Nếu Desk chưa thấy thay đổi hoặc asset/JS cũ:

```bash
bench --site kairos.local clear-cache
bench build --app kairos
```

Sau đó khởi động lại Bench.

## 6. Cấu hình secret và biến môi trường

Từ thư mục repo:

```bash
cd "/mnt/c/Projects/Kairos Apps"
bash scripts/setup_local_env.sh
```

Script chỉ tạo file nếu chưa tồn tại và không ghi đè cấu hình sẵn có:

```text
~/.config/kairos/
├── collector.env   # máy developer -> Frappe URL/token
└── llm.env         # tiến trình Bench -> LLM key/base URL
```

### 6.1. `collector.env`

```bash
export KAIROS_FRAPPE_URL="http://127.0.0.1:8000"
export KAIROS_FRAPPE_TOKEN="<api_key>:<api_secret>"
export KAIROS_CODEX_SESSIONS_DIR="/mnt/c/Users/<windows-user>/.codex/sessions"
export KAIROS_CODEX_BATCH_SIZE="100"
export KAIROS_CODEX_TIMEOUT="120"
```

- `KAIROS_FRAPPE_URL`: URL Frappe mà collector gọi tới. Nếu Bench chạy port khác, sửa lại, ví dụ
  `http://127.0.0.1:8002`.
- `KAIROS_FRAPPE_TOKEN`: token của user có role `Kairos Collector`, định dạng
  `<api_key>:<api_secret>`.
- `KAIROS_CODEX_SESSIONS_DIR`, `KAIROS_CODEX_BATCH_SIZE`, `KAIROS_CODEX_TIMEOUT`: được
  `scripts/run_kairos_codex_sync.sh` đọc và truyền vào CLI.

Collector CLI chỉ tự đọc `KAIROS_FRAPPE_URL` và `KAIROS_FRAPPE_TOKEN`. Khi chạy CLI thủ công với
đường dẫn sessions khác mặc định, truyền thêm `--sessions-dir`.

### 6.2. `llm.env`

```bash
export KAIROS_LLM_API_KEY="<llm-api-key>"
# Tuỳ chọn, cho provider OpenAI-compatible khác:
# export KAIROS_LLM_BASE_URL="https://provider.example/v1"
```

Có thể cấu hình LLM bằng `site_config` thay vì `llm.env`. Chạy các lệnh này từ thư mục Bench:

```bash
cd "$HOME/kairos-bench"
bench --site kairos.local set-config kairos_llm_api_key "<secret>"
bench --site kairos.local set-config kairos_llm_base_url "<provider-base-url>"
```

Thứ tự ưu tiên là **environment trước, `site_config` sau**. Không đưa secret vào DocType, source,
log hoặc Git.

Lưu ý: `scripts/run_kairos_bench.sh` luôn đọc `llm.env` và yêu cầu `KAIROS_LLM_API_KEY` không rỗng.
Nếu chỉ dùng `site_config`, chạy `bench start` trực tiếp thay vì wrapper.

## 7. Chạy Bench

Cách khuyến nghị cho local, để web/worker/scheduler nhận được biến LLM:

```bash
export KAIROS_BENCH_DIR="$HOME/kairos-bench"
bash "/mnt/c/Projects/Kairos Apps/scripts/run_kairos_bench.sh"
```

Các biến có thể override:

| Biến | Mặc định |
| --- | --- |
| `KAIROS_BENCH_DIR` | `~/kairos-bench` |
| `KAIROS_LLM_ENV_FILE` | `~/.config/kairos/llm.env` |
| `KAIROS_BENCH_BIN` | `bench` trong PATH |

Mở URL mà Bench in ra, thường là `http://kairos.local:8000` hoặc `:8002` nếu port đã đổi.

Nếu chưa có LLM key hoặc muốn dùng `site_config`:

```bash
cd "$HOME/kairos-bench"
bench start
```

`bench start` và wrapper chỉ dành cho development.

## 8. Cấu hình Desk

Đăng nhập Desk bằng Administrator.

### 8.1. Kairos Settings

Mở **Kairos Settings** và kiểm tra:

- **LLM Model**: model OpenAI-compatible, mặc định `gpt-4o-mini`.
- **Collection Enabled**: bật để collector được ghi event.
- **Timezone**: `Asia/Ho_Chi_Minh`, read-only và không đổi được sang giá trị khác.
- **Summary Context Max Events**: mặc định `150`.
- **Summary Context Max Characters**: mặc định `50000`.
- **Summary Prompt Version**: mặc định `day-report@1`; tăng version khi đổi semantics prompt.
- **Day Report System Prompt** / **User Prompt Template**: có thể giữ mặc định.

Để cron `18:30` chạy đúng giờ Việt Nam, đặt timezone cho host/WSL và cho Frappe:

```bash
sudo timedatectl set-timezone Asia/Ho_Chi_Minh
```

Trong Desk, mở **System Settings** và đặt **Time Zone** là `Asia/Ho_Chi_Minh`.

### 8.2. User và token cho collector

1. Tạo user riêng, ví dụ `kairos-collector@example.invalid`, trạng thái enabled.
2. Gán role **Kairos Collector**. Role này không có Desk access, chỉ có Read/Create/Write trên
   `Kairos Event` và không được xoá event.
3. Trong user, mở **API Access**, tạo API key/secret.
4. Đưa token vào `collector.env` dưới dạng `KAIROS_FRAPPE_TOKEN=<api_key>:<api_secret>`.

Không dùng Administrator làm token collector. Nếu token từng bị lộ, revoke và tạo lại.

## 9. Cấu hình và chạy collector

Cài collector từ thư mục package:

```bash
cd "/mnt/c/Projects/Kairos Apps/collectors/codex"
python3 -m pip install -e .
```

Hoặc không cài editable, dùng `PYTHONPATH`:

```bash
export PYTHONPATH=src
```

Nạp cấu hình collector:

```bash
source ~/.config/kairos/collector.env
```

Dry run trước, không gửi dữ liệu:

```bash
python3 -m kairos_codex sync --dry-run \
  --sessions-dir "${KAIROS_CODEX_SESSIONS_DIR:-$HOME/.codex/sessions}"
```

Nếu Codex sessions nằm trên ổ Windows, đặt `KAIROS_CODEX_SESSIONS_DIR` trong `collector.env` thành
`/mnt/c/Users/<windows-user>/.codex/sessions` hoặc truyền path đó trực tiếp qua `--sessions-dir`.

`--dry-run` in canonical event JSON và có thể kèm snippet. Không redirect output này vào log dùng
chung.

Sync thật:

```bash
python3 -m kairos_codex sync \
  --sessions-dir "${KAIROS_CODEX_SESSIONS_DIR:-$HOME/.codex/sessions}" \
  --timeout "${KAIROS_CODEX_TIMEOUT:-120}" \
  --batch-size "${KAIROS_CODEX_BATCH_SIZE:-100}"
```

Hoặc dùng runner để khớp với lịch chạy tự động:

```bash
bash "/mnt/c/Projects/Kairos Apps/collectors/codex/scripts/run_kairos_codex_sync.sh"
```

Runner tự source `collector.env`, ghi log theo ngày dưới `~/.local/state/kairos/`, và dùng
`KAIROS_CODEX_SESSIONS_DIR`, `KAIROS_CODEX_BATCH_SIZE`, `KAIROS_CODEX_TIMEOUT`.

Checkpoint incremental mặc định:

```text
~/.local/state/kairos/codex-sync-state.json
```

Chỉ xoá checkpoint khi thật sự muốn replay toàn bộ lịch sử; `event_id` vẫn ngăn duplicate. Không
dùng `--verify-idempotency` với toàn bộ lịch sử sessions; chỉ dùng với thư mục test nhỏ.

## 10. Kiểm tra end-to-end

### 10.1. Trong Desk

1. Mở **Kairos Event**; kiểm tra có event với `event_id` dạng `codex:<external_id>`.
2. Mở **Kairos Day Report**, chọn ngày hôm nay.
3. Bấm **Generate Timeline**; report chuyển sang `draft` và có timeline.
4. Bấm **Generate Summary**; report chuyển sang `ready`.
5. Kiểm tra `Generation Mode`:
   - `llm`: gọi provider thành công.
   - `fallback`: thiếu key hoặc provider lỗi; report vẫn có summary local.
6. Thử **Copy → Summary** và **Copy → Summary + Timeline**.
7. **Force Regenerate** bỏ qua cache và gọi lại provider (nếu có key), dù input chưa đổi.

### 10.2. Bằng Bench CLI

```bash
cd "$HOME/kairos-bench"

bench --site kairos.local execute kairos.api.generate_day_timeline \
  --kwargs '{"report_date":"YYYY-MM-DD"}'

bench --site kairos.local execute kairos.api.generate_day_summary \
  --kwargs '{"report_date":"YYYY-MM-DD"}'
```

Thay `YYYY-MM-DD` bằng ngày thực tế; `report_date` là ngày theo timezone `Asia/Ho_Chi_Minh`.
`generate_day_summary` có thể gọi LLM thật và phát sinh chi phí; nếu chưa có key, nó dùng fallback.

### 10.3. Scheduler 18:30

Job Frappe `30 18 * * *` chỉ tạo/làm mới timeline draft, không gọi LLM. Chạy thử thủ công từ thư
mục Bench:

```bash
cd "$HOME/kairos-bench"
bench --site kairos.local trigger-scheduler-event kairos.scheduler.generate_daily_draft
```

Lệnh này cần `Scheduled Job Type` đã được đăng ký; chạy `bench --site kairos.local migrate` hoặc để
scheduler đồng bộ job sau khi `bench start`. Không dùng `bench execute` cho hàm này vì giá trị trả về
chứa `Timeline` không serialize được.

Job chỉ chạy khi Frappe scheduler của site đang hoạt động. Trong dev, `bench start` có process
`schedule`; nếu chạy web/worker riêng thì phải chạy scheduler. Đảm bảo timezone host/Bench là
`Asia/Ho_Chi_Minh`, nếu không cron sẽ chạy sai giờ địa phương.

## 11. Chạy test

Collector:

```bash
cd "/mnt/c/Projects/Kairos Apps/collectors/codex"
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m unittest tests.test_mapper
```

Dùng WSL/Linux, hoặc cài `tzdata` (`python3 -m pip install tzdata`) nếu chạy Python native trên Windows.

Frappe `FrappeTestCase` cần site dev đã migrate:

```bash
cd "$HOME/kairos-bench"
bench --site kairos.local run-tests --app kairos --module kairos.test_api
```

Ví dụ module khác: `kairos.test_summary`, `kairos.test_timeline`,
`kairos.kairos.doctype.kairos_day_report.test_kairos_day_report`. Không chạy test trên production.

Các module `unittest` thuần chạy bằng Python của Bench:

```bash
cd "/mnt/c/Projects/Kairos Apps"
PYTHONPATH=kairos "$HOME/kairos-bench/env/bin/python" -m unittest \
  kairos.test_quality kairos.test_llm_context kairos.test_generation
```

Format và lint trong từng package đã sửa:

```bash
cd "/mnt/c/Projects/Kairos Apps/kairos"
ruff format .
ruff check .

cd "/mnt/c/Projects/Kairos Apps/collectors/codex"
ruff format .
ruff check .
```

## 12. Tự động sync collector (tuỳ chọn)

Trên Windows, tạo task trong **Task Scheduler**:

```text
Program/script: powershell.exe
Arguments: -NoProfile -ExecutionPolicy Bypass -File "C:\Projects\Kairos Apps\collectors\codex\scripts\run_kairos_codex_sync.ps1"
Start in: C:\Projects\Kairos Apps\collectors\codex\scripts
```

Trigger: hằng ngày, lặp mỗi 30 phút. Nếu repo ở path khác, sửa `-File` và `Start in`. Nếu WSL distro
có tên khác, thêm `-Distro "<name>"`.

Runner `.ps1` gọi script bash trong WSL; script bash đọc `collector.env`, nên secret vẫn nằm ngoài
repo. Không schedule `--verify-idempotency`.

Kiểm tra log:

```bash
tail -n 30 ~/.local/state/kairos/codex-sync-$(date +%F).log
```

Chi tiết xem [B6-SCHEDULED-COLLECTOR.md](B6-SCHEDULED-COLLECTOR.md).

## 13. Xử lý lỗi thường gặp

Các lệnh `bench` trong bảng dưới chạy từ thư mục Bench (`cd "$HOME/kairos-bench"`).

| Hiện tượng | Cách xử lý |
| --- | --- |
| `bench: command not found` | Kích hoạt môi trường cài `frappe-bench` hoặc dùng đường dẫn đầy đủ. |
| `pip install` báo `externally-managed-environment` | Dùng `pipx install frappe-bench`, tạo venv, hoặc cài theo hướng dẫn Frappe cho distro. |
| `get-app` lỗi vì path có khoảng trắng | Bọc path trong dấu `"..."`. |
| `get-app` báo không phải git repository | Dùng `--soft-link` khi trỏ tới `Kairos Apps/kairos`. |
| `bench new-site` báo MariaDB access denied | Kiểm tra MariaDB đang chạy và mật khẩu root. |
| Desk không thấy thay đổi | `bench --site kairos.local clear-cache`, `bench build --app kairos`, khởi động lại. |
| `KAIROS_FRAPPE_TOKEN is required` | `source ~/.config/kairos/collector.env` hoặc điền token. |
| `ZoneInfoNotFoundError` | Chạy trong WSL/Linux hoặc cài `tzdata`. |
| `sessions directory does not exist` | Sửa `KAIROS_CODEX_SESSIONS_DIR` hoặc truyền `--sessions-dir` đúng. |
| `Kairos event collection is disabled` | Bật **Collection Enabled** trong `Kairos Settings`. |
| Summary dùng fallback | Kiểm tra `KAIROS_LLM_API_KEY`/`site_config`, base URL, `generation_error_code`. |
| `run_kairos_bench.sh` báo thiếu `llm.env` hoặc key | Điền `llm.env`, hoặc chạy `bench start` nếu dùng `site_config`. |
| Port bị chiếm | Dừng Bench cũ hoặc đổi port trong cấu hình Bench. |
| Không mở được `kairos.local` | Chạy `bench use kairos.local`; thêm `127.0.0.1 kairos.local` vào hosts, hoặc thử `http://localhost:<port>`. |
| `trigger-scheduler-event` báo event không tồn tại | Chạy `bench --site kairos.local migrate`, sau đó khởi động `bench start` để scheduler đăng ký job. |
| Scheduler không chạy lúc 18:30 | Kiểm tra Frappe scheduler và timezone host/Bench. |

## 14. Production

Không dùng `bench start` hoặc `scripts/run_kairos_bench.sh` cho production. Production cần
process manager/reverse proxy, TLS, backup, secret management và monitoring. Xem
[PRODUCTION-DEPLOYMENT.md](PRODUCTION-DEPLOYMENT.md).

## 15. Checklist

- [ ] WSL/Linux, Python 3.10+, MariaDB, Redis, Node/Yarn đã sẵn sàng.
- [ ] Bench `~/kairos-bench` và site `kairos.local` đã tạo.
- [ ] App `kairos` đã `install-app` và `migrate`.
- [ ] `collector.env` và `llm.env` đã cấu hình, không commit.
- [ ] User collector có role `Kairos Collector` và token đã đưa vào `collector.env`.
- [ ] Timezone host/WSL và Frappe System Settings là `Asia/Ho_Chi_Minh`.
- [ ] `Kairos Settings` đã kiểm tra; collection đang bật.
- [ ] Collector `--dry-run` chạy thành công.
- [ ] Sync thật tạo event trên Frappe.
- [ ] Generate Timeline và Generate Summary thành công.
- [ ] Copy Summary hoạt động.
- [ ] (Tuỳ chọn) Task Scheduler sync mỗi 30 phút.
- [ ] (Tuỳ chọn) Test collector và Frappe app đã chạy.
