# Kairos

**Kairos** là AI Work Assistant.

Nguồn sự thật duy nhất trong repo.

**Trạng thái spec: ĐÃ CHỐT** (công nghệ + kế hoạch MVP). Được phép chuyển sang implement theo § Kế hoạch bên dưới.

---

## Mục tiêu

- Thu thập hoạt động làm việc trong ngày.
- Tự động tạo timeline.
- AI tổng hợp thành báo cáo.
- Cho phép **Copy** hoặc **gửi Teams**.
- Lưu lịch sử để tìm kiếm sau này.

## Không phải

- Task Manager
- Jira
- CRM

## Phạm vi hiện tại

| Mục | Quyết định |
|-----|------------|
| Người dùng | **1 user** |
| Sản phẩm | Personal AI Work Assistant (không multi-team / không quản lý task) |
| Đầu ra chính | Báo cáo hằng ngày (timeline → summary) |
| Đưa báo cáo lên team | **Copy to Clipboard** trên Desk → user paste (Teams hoặc nơi khác) |
| Gửi Teams | Paste tay sau Copy — PAD/AHK = backlog |
| Xuất MVP | **Copy to Clipboard** |
| UI MVP | **Frappe Desk** |
| Nguồn thu thập | **API của các AI dùng hằng ngày** (ví dụ: ChatGPT, Codex, Cursor CLI) |
| Connector MVP tuần 1 | **Codex** (ChatGPT / Cursor CLI = backlog sau) |
| Stack | **Frappe** custom app |
| Lưu trữ | **DocType** trên DB site (không DB riêng; local chỉ tạm/secret) |
| Auth / API key | **`site_config.json` (chính)** + OS env **override** khi deploy |
| Timezone | **Asia/Ho_Chi_Minh** (dùng cho `activity_date`) |

## Nguồn thu thập (đã chốt hướng)

Mọi collector **chỉ** được ghi vào DocType `Kairos Event` qua **canonical event model** (§ bên dưới). Không ghi schema riêng theo nguồn.

| `source` | Collector | Trạng thái |
|----------|-----------|------------|
| `codex` | Local `~/.codex/sessions` trên Dev → collector CLI | **MVP tuần 1** |
| `chatgpt` | ChatGPT / OpenAI usage | backlog |
| `cursor_cli` | Cursor CLI | backlog |
| `git` | Git commits / local repo activity | backlog |
| `frappe` | Frappe Desk / server actions của user | backlog |
| `terminal` | Shell/terminal session commands | backlog |

`source` là slug `snake_case`, ổn định; thêm collector mới = đăng ký thêm một slug + mapper, **không** đổi field canonical.

## Kairos Event — canonical event model

Một `Kairos Event` = **một đơn vị hoạt động** đã chuẩn hóa trên timeline. Collector (Codex, Git, Frappe, Terminal, …) map payload gốc → model này rồi upsert.

### Field bắt buộc

| Field | Type | Ý nghĩa |
|-------|------|---------|
| `event_id` | Data (unique) | ID ổn định toàn cục: `{source}:{external_id}` — dùng để idempotent upsert |
| `source` | Select / Data | Slug collector (`codex`, `git`, `frappe`, `terminal`, …) |
| `external_id` | Data | ID phía nguồn (commit hash, session id, command id, …). Trong một `source` phải unique |
| `occurred_at` | Datetime | Thời điểm sự kiện xảy ra (UTC lưu DB; Desk hiển thị local) |
| `activity_date` | Date | Ngày timeline (derived từ `occurred_at` theo timezone user) |
| `title` | Data | Tiêu đề ngắn 1 dòng cho list/timeline (≤ ~120 ký tự) |

### Field khuyến nghị (nên có)

| Field | Type | Ý nghĩa |
|-------|------|---------|
| `summary` | Text | Mô tả đủ nghĩa cho LLM / báo cáo (vài câu hoặc bullet gọn) |
| `kind` | Select | Loại hoạt động chung — xem bảng `kind` |
| `status` | Select | `ok` \| `error` \| `cancelled` \| `unknown` |
| `duration_seconds` | Float | Thời lượng nếu nguồn có (optional) |
| `project` | Data | Repo / app / workspace gợi ý nhóm timeline (optional) |
| `tags` | Small Text / JSON list | Tag tự do, lowercase, cách nhau bởi dấu phẩy hoặc JSON array |

### Field hệ thống / raw

| Field | Type | Ý nghĩa |
|-------|------|---------|
| `raw_payload` | Code (JSON) | Payload gốc (hoặc subset) để debug / re-map; không đưa nguyên vào Copy báo cáo |
| `collected_at` | Datetime | Lúc collector ghi vào Kairos |
| `collector_version` | Data | Version mapper (vd. `codex@1`) — optional nhưng hữu ích khi đổi schema nguồn |

### `kind` (closed set — mở rộng có kiểm soát)

| `kind` | Dùng khi |
|--------|----------|
| `session` | Bắt đầu / kết thúc phiên AI hoặc terminal |
| `message` | Prompt / reply đáng kể trong phiên chat |
| `agent_run` | Agent/tool run (Codex, Cursor agent, …) |
| `command` | Lệnh shell / CLI |
| `commit` | Git commit |
| `file_change` | Đổi file có ý nghĩa (nếu nguồn cung cấp) |
| `desk_action` | Thao tác trên Frappe Desk / server method user-facing |
| `note` | Ghi chú thủ công / import không rõ loại |
| `other` | Fallback — hạn chế dùng |

### Quy ước bắt buộc cho mọi collector

1. **Không bypass model** — cấm DocType/log riêng theo nguồn làm timeline chính.
2. **Idempotent** — cùng `(source, external_id)` → cùng `event_id` → update-in-place, không nhân đôi khi collect lại.
3. **`occurred_at` thật** — thời điểm sự kiện tại nguồn, không dùng giờ chạy job (giờ job → `collected_at`).
4. **`title` luôn có** — nếu nguồn thiếu, derive từ `summary` (cắt 1 dòng) hoặc `kind` + `external_id` ngắn.
5. **`summary` ưu tiên tiếng người** — đủ để đọc trên timeline và đưa vào LLM; không dump JSON vào `summary`.
6. **`raw_payload` giữ JSON serialize được** — không binary; cắt/ truncated có đánh dấu nếu quá lớn.
7. **Timezone** — normalize `occurred_at` về UTC khi lưu; `activity_date` luôn theo **Asia/Ho_Chi_Minh**.
8. **1 user MVP** — không bắt buộc field `user`; mặc định owner = user site / Administrator. Khi multi-user sau này mới thêm `user` Link.
9. **Không biến Event thành task** — không status workflow assignee/due; `status` chỉ kết quả chạy (ok/error/…).

### Hợp đồng mapper (mọi collector)

```text
raw_items[]  →  map_to_kairos_event(item)  →  Kairos Event fields
             →  event_id = f"{source}:{external_id}"
             →  upsert by event_id
```

Pseudo-interface:

```python
def map_to_kairos_event(raw: dict) -> dict:
    """Return canonical fields; raise / skip nếu thiếu external_id hoặc occurred_at."""
    return {
        "source": "...",          # required slug
        "external_id": "...",     # required
        "event_id": "source:external_id",
        "occurred_at": "...",     # required ISO/datetime
        "activity_date": "...",   # derived
        "title": "...",           # required
        "summary": "...",         # recommended
        "kind": "...",            # from closed set
        "status": "ok|error|cancelled|unknown",
        "duration_seconds": None,
        "project": None,
        "tags": None,
        "raw_payload": raw,
        "collector_version": "name@1",
    }
```

### Ví dụ map nhanh

| Collector | `source` | `external_id` | `kind` | `title` gợi ý |
|-----------|----------|---------------|--------|----------------|
| Codex | `codex` | run/session id phía API | `agent_run` | short goal / first prompt line |
| Git | `git` | commit SHA (full hoặc 40) | `commit` | commit subject |
| Frappe | `frappe` | `{doctype}:{name}:{timestamp}` hoặc action log name | `desk_action` | `{doctype} {action}` |
| Terminal | `terminal` | hash(session+ts+cmd) hoặc tool id | `command` | lệnh rút gọn |
| ChatGPT | `chatgpt` | message/conversation id | `message` / `session` | topic hoặc first user line |
| Cursor CLI | `cursor_cli` | run id | `agent_run` / `command` | task summary |

### Timeline & báo cáo đọc Event thế nào

- **Timeline ngày** = `Kairos Event` filter `activity_date = D` order by `occurred_at asc`.
- **LLM summarize** input = `title` + `summary` (+ `kind`, `source`, `status`); **không** nhét full `raw_payload` trừ khi Settings bật debug.
- **Copy to Clipboard** lấy từ `Kairos Day Report` (đã tổng hợp), không copy từng raw event.

## Luồng MVP (1 user)

```text
[Dev] ~/.codex/sessions
    → collector codex@1 CLI định kỳ (Task Scheduler)
    → API Frappe (VPS)
    → Kairos Event (DocType)
    → timeline
    → AI tổng hợp báo cáo
    → Copy to Clipboard (Desk)
    → user paste (Teams / …)
    → lưu lịch sử (tra cứu sau)
```

## Báo cáo hằng ngày

Nội dung tối thiểu (có thể tinh chỉnh sau):

1. **Timeline** — chuỗi sự kiện/hoạt động trong ngày (theo thời gian).
2. **Tóm tắt AI** — đoạn báo cáo sẵn để **Copy to Clipboard**.
3. **Lịch sử** — các ngày trước, tìm kiếm được.

**Xuất MVP (đã chốt):** nút **Copy to Clipboard** trên `Kairos Day Report` (Desk). User tự paste vào Teams.

**Backlog:** AutoHotkey, Power Automate Desktop, webhook Teams trực tiếp.

## Ranh giới sản phẩm

| Làm | Không làm |
|-----|-----------|
| Thu thập từ API AI tools → timeline cá nhân | Assign task, sprint, backlog |
| Timeline + summary + history | Ticket workflow kiểu Jira |
| Hỗ trợ Copy to Clipboard → paste Teams | CRM, pipeline, khách hàng |

## Lưu trữ (đã chốt): DocType

**DocType trên DB của site Frappe** là nguồn sự thật. Không DB riêng. Local file chỉ dump/cache tạm — không thay DocType.

| DocType | Vai trò |
|---------|---------|
| `Kairos Settings` (Single) | Cấu hình thu thập / LLM model name / prompt — **không** chứa API key |
| `Kairos Event` | 1 row = 1 canonical event (§ model trên); unique `event_id` |
| `Kairos Day Report` | Timeline + tóm tắt AI theo ngày; nút **Copy to Clipboard** |

Tìm kiếm lịch sử = Desk search / filter trên `Kairos Event` + `Kairos Day Report`.

**Secrets — quy ước tối ưu (đã chốt)**

| Ưu tiên | Nơi | Vì sao |
|---------|-----|--------|
| 1 (chính) | `sites/<site>/site_config.json` qua `bench --site <site> set-config` | Worker/scheduler Frappe luôn đọc được; ổn định trên Windows/local bench |
| 2 (override) | OS environment | Docker / CI / máy khác inject secret không sửa file site |
| Không | DocType / commit `.env` vào git | Đã chốt; tránh lộ key trên Desk backup |

**Tên key (snake_case trong `site_config` = chuẩn Frappe):**

| `site_config` / `frappe.conf` | OS env (override) | Dùng cho |
|-------------------------------|-------------------|----------|
| `kairos_llm_api_key` | `KAIROS_LLM_API_KEY` | Summarize trên VPS |
| `kairos_llm_base_url` | `KAIROS_LLM_BASE_URL` | Optional; OpenAI-compatible |
| *(Dev only, không trên VPS site_config)* | `KAIROS_FRAPPE_URL` | URL site Frappe |
| *(Dev only)* | `KAIROS_FRAPPE_TOKEN` | Token API đẩy Event |
| `codex_api_key` | `CODEX_API_KEY` | Optional VPS — chỉ khi dùng Compliance/HTTP sau này |

**Cách set (VPS):**

```bash
bench --site <site> set-config kairos_llm_api_key "..."
bench --site <site> set-config kairos_llm_base_url "https://api.openai.com/v1"
```

**Cách set (Dev — collector):** OS env hoặc file `.env` local (gitignore): `KAIROS_FRAPPE_URL`, `KAIROS_FRAPPE_TOKEN`.

**Cách đọc trong app (thứ tự):** OS env → nếu trống thì `frappe.conf` → nếu vẫn trống thì fail rõ (không silent).

```python
import os
import frappe

def kairos_secret(conf_key: str, env_key: str) -> str:
    return (os.environ.get(env_key) or frappe.conf.get(conf_key) or "").strip()
```

`Kairos Settings` chỉ giữ non-secret (model name, prompt, bật/tắt collect).

## Mapper `codex@1` (local sessions; đơn vị Event đã chốt)

### Nguồn dữ liệu nên dùng

Với **1 user cá nhân**, tối ưu nhất **không** phải Analytics API (chỉ bucket tổng hợp threads/turns/credits — kém cho timeline/`title`/`summary`).

| Nguồn | Phù hợp Kairos? | Ghi chú |
|-------|-----------------|---------|
| **Local Codex sessions / rollout** trên **máy Developer** | **Có — nguồn `codex@1`** | Path: `$CODEX_HOME/sessions` hoặc `~/.codex/sessions` — **không** nằm trên VPS |
| Compliance / logs API (`api.chatgpt.com` … enterprise) | Có nếu có workspace Enterprise | Log audit; backlog `codex_compliance@1` |
| Analytics API (`…/analytics/codex/.../usage`) | **Không** cho Event timeline | Aggregate — không dùng cho Event |

### Topologi thu thập (đã chốt)

**Bench Frappe chạy trên VPS — không đọc được `$CODEX_HOME` / `~/.codex/sessions` trên máy Developer.**

```text
[Developer PC]
  ~/.codex/sessions (JSONL)
       → kairos-codex-collector (local process)
       → map codex@1 → canonical events[]
       → POST /api/method/... (Frappe trên VPS)
              ↓
[VPS — Frappe bench]
  upsert Kairos Event (DocType)
  → timeline / Day Report / Copy
```

| Thành phần | Chạy ở đâu | Việc |
|------------|------------|------|
| Codex CLI / sessions | Máy Developer | Sinh rollout |
| **Collector `codex@1`** | Máy Developer | Đọc sessions, map, đẩy lên VPS — **CLI/script định kỳ** (tuần 1) |
| Frappe app Kairos | VPS | Nhận Event, lưu DocType, summarize, Copy |

**Cách chạy collector tuần 1 (đã chốt):** script/CLI định kỳ (Windows Task Scheduler hoặc tương đương), không service nền.

Ví dụ: `kairos-codex sync` — **mỗi 30 phút** trong giờ làm việc (Task Scheduler), và/hoặc chạy tay trước khi tạo Day Report.

**Backlog:** service nền / file watcher realtime.

**Không:** mount `~/.codex` từ Dev lên VPS; không giả định shared filesystem.

**Auth đẩy Event:** API key / token Frappe user (hoặc site token) trên máy Dev — lưu local env trên Dev (`KAIROS_FRAPPE_URL`, `KAIROS_FRAPPE_TOKEN`); **không** nhầm với `codex_api_key` trên VPS. VPS `site_config` giữ `kairos_llm_*` cho summarize.

`codex_api_key` trên VPS: chỉ cần nếu sau này dùng Compliance/HTTP API; **MVP local-file collector trên Dev không bắt buộc key Codex trên VPS**.

### Đơn vị Event (đã chốt)

**1 Codex session → nhiều `Kairos Event`.**

| Đơn vị emit | `kind` | Khi nào |
|-------------|--------|---------|
| User turn / prompt đáng kể | `message` | Mỗi lượt user (hoặc cặp turn) có text đủ nghĩa |
| Agent/tool run trong session | `agent_run` | Mỗi lần agent chạy / hoàn thành khối việc rõ |
| Lệnh shell trong session (nếu parse được) | `command` | Optional; gộp vào `agent_run` nếu nhiễu |
| Session mở / đóng | `session` | **Optional** bookend (0–2 Event); không thay thế turn events |

Không emit 1 Event duy nhất cho cả session. Không emit từng token.

**Nhóm timeline:** mọi Event từ cùng session chia sẻ `tags` có `session:<id>` và cùng `project` (từ `cwd`).

### Bảng map field-by-field — turn/item trong session → canonical (`codex@1`)

**Session metadata** (context chung cho mọi Event trong file):

```json
{
  "id": "rollout-2026-08-07T10-15-00-abc123",
  "path": "~/.codex/sessions/2026/08/07/rollout-....jsonl",
  "started_at": "2026-08-07T03:15:00Z",
  "updated_at": "2026-08-07T04:02:00Z",
  "cwd": "C:/Projects/Kairos Apps",
  "originator": "cli"
}
```

**Item trong rollout JSONL** (mỗi dòng / turn đáng emit), ví dụ logic:

```json
{
  "item_id": "turn-3",
  "type": "user_message",
  "timestamp": "2026-08-07T03:22:10Z",
  "text": "Implement Kairos Event mapper for Codex",
  "status": "ok"
}
```

| Canonical field | Nguồn | Quy tắc |
|-----------------|-------|---------|
| `source` | — | Luôn `"codex"` |
| `external_id` | `session.id` + `item_id` (hoặc index ổn định) | `"{session_id}:{item_id}"` — bắt buộc unique trong session |
| `event_id` | — | `"codex:" + external_id` |
| `occurred_at` | `item.timestamp` | Fallback: `session.started_at` + offset theo thứ tự dòng |
| `activity_date` | derived | **Asia/Ho_Chi_Minh** từ `occurred_at` |
| `title` | `item.text` / goal | Cắt ≤120; user message ưu tiên; agent_run → rút từ task/result 1 dòng |
| `summary` | item + context | Vài câu: ý user hoặc kết quả agent; kèm `cwd` basename; không full transcript |
| `kind` | `item.type` | Map: user/assistant message → `message`; agent/tool run → `agent_run`; shell → `command`; bookend → `session` |
| `status` | `item.status` | `ok` / `error` / `cancelled` / `unknown` |
| `duration_seconds` | item nếu có | Null nếu không đo được từng turn |
| `project` | `session.cwd` | Basename / path rút gọn — **giống nhau** cho mọi Event trong session |
| `tags` | — | Bắt buộc có `session:<session_id>`; thêm `cli` / originator |
| `raw_payload` | object nhỏ | `{ "session_id", "item_id", "type", "rollout_path", "snippet": truncated }` — không nhét cả JSONL |
| `collected_at` | — | Now UTC |
| `collector_version` | — | `"codex@1"` |

### Quy tắc chọn item nào được emit

1. Duyệt rollout JSONL theo thứ tự thời gian.
2. Emit khi gặp: user message có text; agent_run hoàn tất (hoặc fail); (optional) command đáng chú ý.
3. **Bỏ qua:** token_count, heartbeat, meta nhiễu, message rỗng.
4. Gộp: nếu user message ngay sát agent_run chỉ là “go” ngắn — có thể chỉ giữ `agent_run` + dùng user text làm `title` (tránh đôi Event vô nghĩa).
5. Idempotent: collect lại cùng session chỉ upsert theo `event_id`, không xóa Event cũ của session trừ khi Settings có “resync replace session:*”.

### Pseudo mapper

```python
def map_codex_session_items_v1(session: dict, items: list[dict]) -> list[dict]:
    sid = session["id"]
    project = basename(session.get("cwd"))
    out = []
    for item in items:
        if not should_emit(item):
            continue
        item_id = item.get("item_id") or stable_index_id(item)
        ext = f"{sid}:{item_id}"
        occurred = item.get("timestamp") or session.get("started_at")
        out.append({
            "source": "codex",
            "external_id": ext,
            "event_id": f"codex:{ext}",
            "occurred_at": occurred,
            "activity_date": to_date_hcm(occurred),
            "title": make_title(item)[:120],
            "summary": make_summary(item, session),
            "kind": map_kind(item),
            "status": item.get("status") or "ok",
            "duration_seconds": item.get("duration_seconds"),
            "project": project,
            "tags": f"session:{sid},{session.get('originator') or 'cli'}",
            "raw_payload": compact_raw(session, item),
            "collector_version": "codex@1",
        })
    return out
```

### Backlog liên quan

| Version | Việc |
|---------|------|
| `codex@1.1` | Tinh chỉnh heuristic gộp user+agent_run; parse file_change → `kind=file_change` |
| `codex_compliance@1` | Map Compliance log API → cùng canonical |
| Usage-only | Analytics API → không vào `Kairos Event` |

### Việc cần bạn xác nhận để chốt hẳn `codex@1`

1. ~~1 session → nhiều Event~~ — **đã chốt**.  
2. ~~Bench đọc trực tiếp `~/.codex`?~~ — **Không** (Dev ≠ VPS) — **đã chốt**.  
3. ~~Cách chạy collector Dev tuần 1~~ — **CLI định kỳ mỗi 30 phút** — **đã chốt**.

---

## Công nghệ đã chốt (tóm tắt)

| Layer | Công nghệ |
|-------|-----------|
| Backend / UI | Frappe custom app + Desk |
| Data | DocType trên DB site: `Kairos Settings`, `Kairos Event`, `Kairos Day Report` |
| Event model | Canonical `Kairos Event` (mọi collector map vào) |
| Collector MVP | `codex@1`: đọc `~/.codex/sessions` trên **Dev**, 1 session → nhiều Event |
| Vận hành collector | CLI/script + Windows Task Scheduler (~30 phút) |
| Sync Dev→VPS | HTTP API Frappe (`KAIROS_FRAPPE_URL` + token) |
| Summarize | LLM OpenAI-compatible; key trên VPS `site_config` / env |
| Xuất | Copy to Clipboard trên Day Report |
| TZ | Asia/Ho_Chi_Minh cho `activity_date`; `occurred_at` UTC |

**Repo layout đề xuất khi implement:**

```text
Kairos Apps/
  KAIROS.md                 # spec (file này)
  kairos/                   # Frappe app (VPS)
  collectors/codex/         # CLI collector (Dev)
```

## Kế hoạch triển khai MVP

**Thứ tự bắt buộc:** A → B → C → D (xong gate phase trước mới sang phase sau).  
Không làm SPA, PAD/AHK, multi-collector trong MVP.

---

### Phase A — Frappe app

**Mục tiêu phase:** App `kairos` trên bench nhận được batch Event từ ngoài qua API, lưu DocType ổn định.

**A1 — Scaffold + bench** [x]  
Hướng dẫn: [`docs/A1-BENCH-INSTALL.md`](./docs/A1-BENCH-INSTALL.md).

#### A2 — DocType `Kairos Settings` (Single) [x]

**Mục tiêu A2:** Có 1 màn hình cấu hình non-secret trên Desk; Phase C đọc model/prompt từ đây. **Không** chứa API key (key = `site_config` / env → A5).

**Phạm vi làm**

| Việc | Chi tiết |
|------|----------|
| Tạo DocType | `Kairos Settings`, **issingle = 1**, module `Kairos` |
| Field non-secret | Xem bảng field bên dưới |
| Default hợp lý | Model mặc định + prompt mẫu đủ dùng summarize ngày |
| Migrate + Desk | `bench migrate` → mở **Kairos Settings** trên Desk, sửa/lưu được |
| Code layout | `kairos/kairos/doctype/kairos_settings/` (`*.json` + `kairos_settings.py`) |

**Field (MVP — chỉ những cái này)**

| Fieldname | Type | Default / ý nghĩa |
|-----------|------|-------------------|
| `llm_model` | Data | VD. `gpt-4o-mini` — tên model gửi LLM (không phải key) |
| `day_report_system_prompt` | Text / Long Text | System prompt cho summarize Day Report |
| `day_report_user_prompt_template` | Text / Long Text | Template user message; placeholder `{date}`, `{timeline}` |
| `collection_enabled` | Check | Bật/tắt chấp nhận Event từ collector (default On) |
| `timezone` | Data (Read Only hoặc Data) | `Asia/Ho_Chi_Minh` — khớp spec; không đổi linh tinh trong MVP |

**Không làm trong A2**

- Không field API key / token / base URL secret trên DocType
- Không Client Script / custom button Generate (→ Phase C)
- Không DocType Event / Day Report (→ A3, A4)
- Không helper `kairos_secret` (→ A5)
- Không API `upsert_events` (→ A6)

**Done khi**

1. `bench --site <site> migrate` OK  
2. Desk → tìm **Kairos Settings** → mở được (Single)  
3. Đổi `llm_model` / prompt → Save → reload vẫn còn  
4. Không có field secret trên form  

**Cách kiểm tra nhanh**

```bash
# trong kairos-bench
bench --site <site> migrate
bench --site <site> console
>>> frappe.get_single("Kairos Settings")
```

Desk: AwesomeBar → `Kairos Settings` → sửa → Save.

---

#### A3 — DocType `Kairos Event` [x]

**Mục tiêu:** Lưu 1 row = 1 canonical event (§ model); unique `event_id`.

| Việc | Chi tiết |
|------|----------|
| Fields | Bắt buộc + khuyến nghị + hệ thống theo § Kairos Event |
| Unique | `event_id` unique; index `activity_date`, `source` nếu cần list |
| Permissions | System Manager / role Kairos (A7 tinh chỉnh) |
| Kiểm tra | Tạo tay 1 Event trên Desk |

**Done khi:** Tạo tay 1 Event với `event_id` hợp lệ; trùng `event_id` bị chặn.  
**Không làm:** API upsert (A6), mapper Codex (B).

---

#### A4 — DocType `Kairos Day Report` [x]

**Mục tiêu:** 1 báo cáo / ngày (timeline + summary text); chỗ gắn nút Copy sau (C).

| Việc | Chi tiết |
|------|----------|
| Fields | `report_date` (unique), `timeline_text`, `summary_text`, `status` (draft/ready…), optional link meta |
| Permissions | Mở/sửa trên Desk |
| Kiểm tra | Tạo tay 1 report ngày hôm nay |
| Test Frappe | `bench --site <site> run-tests --app kairos --module kairos.kairos.doctype.kairos_day_report.test_kairos_day_report` |

**Done khi:** Tạo tay 1 `Kairos Day Report`.  
**Không làm:** Generate LLM / Copy button (C).

---

#### A5 — Helper secrets `kairos_llm_*` [x]

**Mục tiêu:** Đọc key theo thứ tự env → `frappe.conf`; thiếu thì lỗi rõ.

| Việc | Chi tiết |
|------|----------|
| Module helper | VD. `kairos/kairos/secrets.py` — `kairos_secret(conf_key, env_key)` |
| Keys | `kairos_llm_api_key` / `KAIROS_LLM_API_KEY`; `kairos_llm_base_url` / `KAIROS_LLM_BASE_URL` |
| Fail rõ | Raise / msg rõ khi thiếu key lúc cần summarize |
| Test Frappe | `bench --site <site> run-tests --app kairos --module kairos.test_secrets` |

**Done khi:** Console/test: có key → trả về; không key → lỗi rõ.  
**Không làm:** Gọi LLM thật (C2); không đưa key lên Settings.

---

#### A6 — API `upsert_events` [x]

**Mục tiêu:** Whitelist method nhận batch Event; idempotent theo `event_id`.

| Việc | Chi tiết |
|------|----------|
| Method | VD. `kairos.api.upsert_events` — nhận `events: list[dict]` |
| Validate | Field bắt buộc; derive `activity_date` từ TZ Settings/spec |
| Upsert | Trùng `event_id` → update-in-place, không nhân đôi |
| Respect Settings | Nếu `collection_enabled = 0` → từ chối rõ |
| Test Frappe | `bench --site <site> run-tests --app kairos --module kairos.test_api` |

**Done khi:** Postman/curl tạo Event; gọi lại cùng payload → không tăng số row.  
**Không làm:** Collector CLI (B).

---

#### A7 — Role + token API cho collector [x]

**Mục tiêu:** User/token trên Dev gọi được `upsert_events` mà không cần login Desk.

| Việc | Chi tiết |
|------|----------|
| Role | VD. `Kairos Collector` — permission Event (write) + method |
| Token | API Key / token user; doc ngắn cách set `KAIROS_FRAPPE_*` trên Dev |
| Test Frappe | `bench --site <site> run-tests --app kairos --module kairos.test_install` |

**Done khi:** Token gọi `upsert_events` thành công từ máy ngoài bench.

**Gate A:** [ ] Chờ xác nhận token gọi `upsert_events` từ máy ngoài Bench.

---

### Phase B — Collector Dev (`codex@1`)

**Mục tiêu phase:** Trên máy Dev, CLI đọc `~/.codex/sessions` → map `codex@1` → POST `upsert_events` định kỳ ~30 phút.

| # | Việc | Chi tiết làm | Done khi | TT |
|---|------|--------------|----------|----|
| **B1** | Skeleton CLI | Package `collectors/codex`, entry `kairos-codex`, lệnh `sync` / `--help` | `--help` chạy được | [x] |
| **B2** | Parser | Quét sessions dir; parse rollout JSONL → session + items | Dry-run in số session/item | [x] |
| **B3** | Mapper `codex@1` | 1 session → nhiều Event canonical (field-by-field § mapper) | Dry-run in JSON canonical | [x] |
| **B4** | Client HTTP | POST batch với `KAIROS_FRAPPE_URL` + `KAIROS_FRAPPE_TOKEN` | Sync tay → Event trên Desk | [x] |
| **B5** | Idempotent E2E | `--verify-idempotency` gửi cùng batch 2 lần; đã xác nhận với token/site thật | Số Event không nhân đôi | [x] |
| **B6** | Scheduler | Windows Task Scheduler ~30 phút + incremental checkpoint + batch delivery + log file/stdout | Chạy ≥ 1 lần OK | [x] |

**Không làm Phase B:** Day Report, LLM, Copy, multi-collector.

**Gate B:** [x] Event Codex ngày hiện tại lên Desk sau sync.

---

### Phase C — Day Report + Copy

**Mục tiêu phase:** Từ Event theo ngày → Generate summary (LLM + fallback) → Copy to Clipboard paste Teams.

| # | Việc | Chi tiết làm | Done khi | TT |
|---|------|--------------|----------|----|
| **C1** | Timeline builder | Query Event theo `activity_date` → text timeline | Preview timeline trên Report / dialog | [x] |
| **C2** | Generate + LLM | Nút trên Day Report; gọi OpenAI-compatible với model/prompt Settings + secret A5 | Draft `summary_text` trên Desk | [x] |
| **C3** | Fallback | Không key / LLM lỗi → timeline-only hoặc summary heuristic | Vẫn có báo cáo đọc được | [ ] |
| **C4** | Copy to Clipboard | Nút Desk copy `summary` (+ timeline nếu cần) | Paste Notepad/Teams được | [ ] |
| **C5** | (Optional) | Scheduler draft cuối ngày | Có hoặc bỏ; không chặn gate | [ ] |

- 2026-09-13 — C2 triển khai: tạo Summary bằng LLM OpenAI-compatible, dùng model/prompt từ Kairos Settings và secret server-side; nút Generate Summary, API và test thành công/lỗi LLM.

**Không làm Phase C:** PAD/AHK, Teams webhook, SPA.

**Gate C:** [ ] Event → Generate → Copy → paste Teams dùng được.

---

### Phase D — Soft launch

**Mục tiêu phase:** Dùng thật ≥ 3 ngày; chỉnh heuristic; doc vận hành; quyết định backlog.

| # | Việc | Chi tiết làm | Done khi | TT |
|---|------|--------------|----------|----|
| **D1** | Dùng thật | Mỗi ngày: sync → Generate → Copy → paste | Checklist ≥ 3 ngày Pass | [ ] |
| **D2** | Chỉnh emit | Giảm Event rác / parse JSONL lỗi từ log thật | Ít Event nhiễu | [ ] |
| **D3** | README vận hành | Lệnh bench, env Dev, scheduler, Generate/Copy | Người khác (hoặc bạn sau 1 tuần) chạy lại được | [ ] |
| **D4** | Go / no-go | Ghi changelog + backlog ưu tiên (Git, Cursor CLI, …) | Quyết định bước tiếp theo | [ ] |

**Gate D:** [ ] Báo cáo hàng ngày ổn, ít sửa tay.

---

**Backlog sau MVP:** Git / Cursor CLI / ChatGPT collectors; service nền; Teams webhook; Compliance API; multi-user; SPA.

## Changelog

- 2026-08-07 — Spec Kairos: 1 user, Frappe DocType, Codex MVP, Copy to Clipboard, secrets `site_config`+env, timezone Asia/Ho_Chi_Minh, canonical Event model.
- 2026-08-07 — `codex@1`: **1 session → nhiều Event** (`external_id = session_id:item_id`, tag `session:<id>`).
- 2026-08-07 — Topologi: Codex sessions trên **Developer PC**; bench trên **VPS**; collector local đẩy Event qua API.
- 2026-08-07 — Collector Dev tuần 1: **CLI/script định kỳ ~30 phút** (không service nền).
- 2026-08-07 — **Chốt xong công nghệ + kế hoạch MVP** (phase A→D). Spec sẵn sàng implement.
- 2026-08-10 — A1 hoàn thành (kairos-bench riêng, install, migrate, login Desk) — đánh dấu [x] trong kế hoạch.
- 2026-08-10 — Làm rõ kế hoạch từng phase; chi tiết A2 (field Settings, phạm vi / không làm, done khi).
- 2026-08-10 — A2 hoàn thành: DocType Single `Kairos Settings` (model, prompts, collection_enabled, timezone) + migrate `kairos.local`.
- 2026-08-10 — A3 hoàn thành: DocType `Kairos Event` (canonical fields, unique `event_id`, derive `activity_date` Asia/Ho_Chi_Minh); sample + duplicate blocked.
- 2026-08-31 — A4 triển khai: DocType `Kairos Day Report` (một report/ngày, timeline, summary, status) + test Frappe.
- 2026-08-31 — A5 triển khai: helper secrets ưu tiên environment, fallback `site_config`, và báo lỗi rõ khi thiếu cấu hình.
- 2026-08-31 — A6 triển khai: API batch `upsert_events`, validation, collection switch, và upsert idempotent theo `event_id`.
- 2026-08-31 — A7 triển khai: role `Kairos Collector`, quyền Event tối thiểu, hook cài/migrate và hướng dẫn tạo API token.
- 2026-09-01 — B1 triển khai: package CLI `kairos-codex`, command `sync`, dry-run, logging và test standard library.
- 2026-09-01 — B2 triển khai: parser rollout JSONL, chịu lỗi từng dòng, session/item models và thống kê dry-run.
- 2026-09-01 — B3 triển khai: mapper `codex@1` cho user request và task completion, canonical JSON dry-run, ID ổn định và test.
- 2026-09-01 — B4 triển khai: HTTP client stdlib, environment config, token auth, timeout/error handling và test request payload.
- 2026-09-03 — B5 triển khai và E2E pass: CLI verify idempotency gửi batch hai lần; lần hai không tạo Event mới.
- 2026-09-04 — B6 triển khai: WSL runner có log theo ngày, PowerShell launcher cho Windows Task Scheduler và hướng dẫn cấu hình lịch 30 phút.
- 2026-09-05 — B6 tăng cường: checkpoint local chỉ parse session mới/đổi, gửi batch tối đa 100 event và timeout runner cấu hình được.
- 2026-09-12 — Collector fix: bỏ qua Codex system-context chỉ gồm markup để Frappe không làm rỗng title bắt buộc.
- 2026-09-12 — B6 E2E pass: initial sync 2,778 event qua 28 batch, checkpoint 25 session và lần tiếp theo bỏ qua session không đổi.
- 2026-09-12 — C1 E2E pass: tạo Kairos Day Report từ Event theo ngày, preview 24 event trên Desk/API và test Frappe pass.
