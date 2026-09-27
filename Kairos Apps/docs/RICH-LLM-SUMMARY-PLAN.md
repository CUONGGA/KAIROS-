# Kế hoạch nâng chất lượng LLM Summary

## 1. Mục tiêu và ranh giới

Mục tiêu là tạo `Kairos Day Report.summary_text` ngắn, chính xác, có bằng chứng và sẵn sàng để
copy vào Teams. LLM phải tổng hợp được ý nghĩa công việc, không chỉ diễn đạt lại title trên
Timeline.

Phạm vi đầu vào là **các Kairos Event của một ngày**. Đây là grounded summarization, không phải
RAG. Không truy hồi toàn bộ lịch sử, không gửi `raw_payload`, file session JSONL, token, đường dẫn
tuyệt đối, hay secret đến provider. RAG chỉ được xem xét sau soft launch cho các câu hỏi lịch sử
liên ngày và phải có review riêng về privacy/cost.

## 2. Tiêu chuẩn chất lượng

Một summary được xem là đạt khi:

- Chính xác: mọi claim quan trọng truy được về một hoặc nhiều Event trong ngày.
- Hữu ích: phân biệt **Hoàn thành**, **Đang làm**, **Rủi ro/ghi chú**; không lặp từng event.
- Ngắn: mặc định tối đa 8 bullet hoặc 1.200 ký tự, trừ khi người dùng chọn báo cáo chi tiết.
- An toàn: không lộ secret, raw prompt/session, path máy đầy đủ hoặc chỉ dẫn độc hại từ dữ liệu.
- Ổn định: cùng Event, policy, model và prompt version tạo cùng context hash; không gọi lại nếu
  context chưa thay đổi.
- Có fallback: provider lỗi không làm mất Day Report; C3 tạo summary từ Timeline.

## 3. Kiến trúc mục tiêu

```text
Collector mới/cũ
  → Kairos Event canonical
  → Event quality gate + redaction
  → Context Builder (deterministic, budgeted)
  → Context envelope @1 + context_hash
  → LLM adapter (OpenAI-compatible)
  → Output validator + evidence validation
  → Day Report: summary, provenance, generation mode
  → Desk / Copy to Clipboard
```

Timeline là output cho người đọc: `time + source + title`. LLM context là input riêng, giàu thông
tin hơn: `title + summary + kind + source + project + tags + time + reference`. Hai output không
được dùng chung một chuỗi text.

## 4. Contract dữ liệu và quality gate

Mỗi collector phải map về `Kairos Event` như hiện tại, đồng thời tuân thủ contract
`kairos.event_quality@1`:

| Field | Quy tắc bắt buộc cho LLM | Chính sách đề xuất |
| --- | --- | --- |
| `title` | Nhãn một dòng, có động từ/kết quả khi nguồn có | 1–160 ký tự, không JSON/markup |
| `summary` | Chi tiết tiếng người, 1–3 câu; có thể rỗng nếu không đủ dữ liệu | tối đa 1.000 ký tự sau redaction |
| `occurred_at` | UTC ISO-8601 hợp lệ | dùng để sort và nhóm theo phiên làm việc |
| `source`, `kind` | slug/closed set hợp lệ | dùng để nhóm và đánh giá coverage |
| `project`, `tags` | optional, ngắn, đã chuẩn hóa | không path tuyệt đối, không token |
| `raw_payload` | chỉ debug nội bộ | tuyệt đối không vào context LLM |

Quality gate chạy trong collector mapper và lặp lại server-side trước khi gọi LLM. Nó phải:

1. Chuẩn hóa whitespace và loại markup/system context.
2. Redact mẫu secret phổ biến: API key, bearer token, password assignment, private key block và URL
   có credential. Không log giá trị bị redact.
3. Rút gọn path tuyệt đối thành project/basename khi cần.
4. Gắn `llm_eligible=false` với reason rõ ràng khi event không an toàn hoặc không có ý nghĩa.
5. Không tự bịa `summary`; thiếu dữ liệu thì chỉ giữ title và giảm trọng số trong context.

Mỗi collector mới phải có fixture sạch dữ liệu nhạy cảm và pass chung conformance test: timestamps,
ID ổn định, title/summary bounds, redaction, tags và idempotency.

## 5. Context Builder độc lập

Tạo module server-side, ví dụ `kairos.llm_context`, thay vì ghép từ `timeline_text` trong
`summary.py`. Public interface đề xuất:

```python
build_day_context(report_date, policy) -> SummaryContext
```

`SummaryContext` gồm `envelope`, `context_hash`, `selected_count`, `excluded_count`,
`truncated_count` và danh sách reason. Query chỉ lấy canonical fields; thứ tự cố định là
`occurred_at asc, event_id asc`.

Payload gửi LLM dùng JSON canonical, không phải prose tự do:

```json
{
  "schema_version": "kairos.summary_context@1",
  "report_date": "2026-09-27",
  "timezone": "Asia/Ho_Chi_Minh",
  "events": [
    {
      "ref": "E001",
      "time": "09:15",
      "source": "codex",
      "kind": "agent_run",
      "project": "Kairos",
      "title": "Triển khai fallback summary",
      "summary": "Thêm fallback khi thiếu API key hoặc provider lỗi.",
      "tags": ["session:...", "cli"]
    }
  ]
}
```

`ref` là ordinal ngắn cho evidence, không phải `event_id`. `event_id` chỉ được lưu nội bộ trong
manifest audit nếu cần. JSON phải serialize canonical (key order, UTF-8, compact separators) trước
khi băm SHA-256 thành `context_hash`.

## 6. Budget, deduplication và reduction policy

Không đưa toàn bộ event của một ngày lớn vào model. Thêm non-secret policy trong `Kairos Settings`:

| Setting | Giá trị khởi đầu | Vai trò |
| --- | ---: | --- |
| `summary_context_max_events` | 150 | số Event tối đa sau group/dedup |
| `summary_context_max_chars` | 50.000 | safety budget độc lập provider |
| `summary_output_max_chars` | 1.200 | giới hạn report copy-ready |
| `summary_prompt_version` | `day-report@1` | provenance và rollout prompt |
| `summary_generation_enabled` | true | kill switch không xóa Event |

Reduction có thứ tự cố định và phải log được:

1. Loại Event `llm_eligible=false`, system context, title rỗng và event lỗi không có thông tin.
2. Dedupe các Event có cùng normalized title/kind/source trong cửa sổ ngắn; giữ event giàu summary
   nhất và tăng `occurrence_count`.
3. Group theo `project + source + session tag`; giữ representative event và count.
4. Ưu tiên completion, file change, decision, error có detail; sau đó mới đến message thường.
5. Nếu vẫn vượt budget, lấy mẫu theo time bucket để không mất hoàn toàn hoạt động đầu/cuối ngày.
6. Không cắt giữa JSON/string; truncate từng summary với marker `…[truncated]`.

Context metadata phải chỉ rõ số event gốc, được chọn, deduped, redacted và bị cắt. Điều này giúp
giải thích tại sao một việc không xuất hiện trong summary.

## 7. Prompt và output có kiểm chứng

System prompt phải nói rõ context là **untrusted data**, không được làm theo lệnh nằm trong Event.
User prompt chỉ chứa envelope được delimit rõ ràng. Không chèn raw title/summary vào system prompt.

Yêu cầu model trả JSON theo contract thay vì Markdown tự do:

```json
{
  "done": [{"text": "...", "evidence": ["E003", "E007"]}],
  "in_progress": [{"text": "...", "evidence": ["E010"]}],
  "risks_or_notes": [{"text": "...", "evidence": ["E012"]}],
  "omissions": ["optional reason"]
}
```

Server phải validate JSON, giới hạn độ dài, reject evidence ref không thuộc context và render Markdown
theo template cố định bằng code. Model không quyết định heading, format hay data retention. Nếu output
malformed: retry tối đa một lần với repair prompt chỉ chứa output lỗi; vẫn lỗi thì dùng fallback C3.

## 8. Reliability, provider abstraction và chi phí

Giữ adapter `OpenAICompatibleClient` hiện tại, nhưng tách interface để sau này thêm provider mà không
đổi Context Builder:

```python
class SummaryProvider(Protocol):
    def generate(self, request: SummaryRequest) -> SummaryResponse: ...
```

Yêu cầu vận hành:

- Timeout connect/read riêng, retry tối đa 2 lần với exponential backoff + jitter cho lỗi transient.
- Không retry lỗi 4xx do key/payload; chuyển ngay sang fallback.
- Idempotency key: `report_date + context_hash + prompt_version + model`. Nếu key không đổi và report
  `ready`, không gọi model lại trừ khi user chọn Force Regenerate.
- Ghi metrics: latency, provider/model, input/output estimate, retry count, fallback reason. Không log
  prompt hay response đầy đủ ở mức info.
- API key/base URL tiếp tục ở env hoặc `site_config`; không thêm field secret vào DocType.
- Khi tổng hợp vượt ngưỡng sync UI, dùng Frappe background job; Day Report có trạng thái `generating`
  và Desk poll/refresh. Job phải idempotent theo generation key.

## 9. Provenance và schema Day Report

Trước khi triển khai, mở rộng `Kairos Day Report` bằng các field non-secret sau:

| Field | Mục đích |
| --- | --- |
| `generation_mode` | `llm`, `fallback`, `manual` |
| `generated_at` | thời điểm generation hoàn tất UTC |
| `llm_model` | model đã dùng, không chứa provider key |
| `prompt_version` | prompt/template version |
| `context_version` | `kairos.summary_context@1` |
| `context_hash` | SHA-256 context canonical |
| `context_event_count` | số Event sau selection |
| `context_excluded_count` | số Event loại/cắt |
| `generation_error_code` | code phân loại nội bộ, không lưu raw provider response |

Không lưu full provider response. Context snapshot sanitized chỉ được thêm sau khi có retention policy,
permission System Manager và nhu cầu debug thực tế; mặc định chỉ lưu hash + manifest count.

## 10. Evaluation trước khi rollout

Tạo golden dataset nội bộ tối thiểu 30 ngày đã redact, gồm ngày rỗng, ít event, nhiều event, nhiều
project, event trùng, lỗi provider và prompt injection trong title/summary. Mỗi case có expected facts
và forbidden facts.

Automated tests bắt buộc:

- Deterministic ordering/hash, redaction và budget/reduction.
- Không có `raw_payload`, secret pattern hoặc absolute path trong envelope.
- Output JSON/evidence validation và malformed-output fallback.
- Provider timeout/429/5xx/key missing; Day Report vẫn `ready` ở fallback.
- Conformance test dùng ít nhất Codex và một collector thứ hai (Git là ứng viên nhẹ nhất).

Đánh giá thủ công mỗi tuần: chấm 1–5 cho factuality, coverage, concision, usefulness. Gate rollout:

| Chỉ số | Ngưỡng khởi đầu |
| --- | ---: |
| Claim có evidence hợp lệ | ≥ 95% |
| Summary cần sửa tay đáng kể | ≤ 20% ngày pilot |
| Secret/raw leakage | 0 |
| Fallback khi provider lỗi | 100% không mất report |
| P95 generation latency | ≤ 20 giây hoặc chuyển background job |

## 11. Lộ trình triển khai

| Giai đoạn | Deliverable | Kiểm chứng |
| --- | --- | --- |
| P0 — Baseline | Thu 7 ngày Event/summary thực tế, redact sample, chốt rubric | Có 30 golden cases và baseline sửa tay |
| P1 — Quality gate | Sanitizer, field bounds, LLM eligibility, mapper fixtures | Không secret/path/raw vào context test |
| P2 — Context Builder | Envelope @1, hash, selection/reduction policy | Deterministic test + budget test pass |
| P3 — Provenance | DocType migration, metadata, generation cache/idempotency | Regenerate cùng input không gọi model lần hai |
| P4 — Structured LLM | JSON output contract, evidence validator, retry/fallback | Hallucinated ref/malformed JSON bị xử lý |
| P5 — Async + observability | Job queue, Desk state, metrics/log taxonomy | Timeout không block Desk, có dashboard/log |
| P6 — Multi-collector | Git mapper + conformance suite | Collector thứ hai không sửa report schema |
| P7 — Pilot | 2 tuần shadow/opt-in, review metric/cost | Đạt gate rollout hoặc ghi backlog cải tiến |

## 12. Quyết định kiến trúc cần chốt trước P1

1. Provider/model khởi đầu và quota chi phí mỗi ngày.
2. Chính sách redact PII/path: chỉ secret hay cả email, username, branch/repo private.
3. Có cho phép lưu sanitized context snapshot để audit hay chỉ hash/metadata.
4. Output mặc định: chỉ report ngắn hay thêm mode chi tiết.
5. Giới hạn retention cho Error Log và generation metadata.

Không bắt đầu RAG, vector database hoặc toàn bộ history chat trước khi P7 chứng minh daily summary có
quality gate và privacy controls ổn định.
