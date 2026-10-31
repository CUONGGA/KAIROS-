# Kairos — Sổ đăng ký rủi ro

Ghi nhận rủi ro theo từng lần đánh giá. Mỗi lần đánh giá giữ nguyên ngày và bằng chứng; khi xử lý xong một
rủi ro, cập nhật cột trạng thái và thêm ngày đóng thay vì xóa dòng.

## Đánh giá 2026-10-31 — Test lại Phase A → C.5

- **Nhánh:** `feat/trusted-llm-context`, commit `192ecbc`
- **Môi trường:** WSL Ubuntu 24.04, `~/kairos-bench`, site dev `kairos.local`, Frappe 15.117.0
- **Phạm vi:** test tự động toàn bộ module, collector dry-run, kiểm tra redaction trên dữ liệu thật

### Kết quả kiểm thử

| Phase | Phạm vi | Lệnh | Kết quả |
|---|---|---|---|
| B | Collector `collectors/codex` | `PYTHONPATH=src python3 -m unittest discover -s tests` | 19/19 OK |
| B | Collector dry-run trên session thật | `python3 -m kairos_codex sync --dry-run` | OK, không gửi Event |
| A, C, C.5 | 7 module `FrappeTestCase` | `bench --site kairos.local run-tests --module <module>` | 38/38 OK |
| C.5 | 4 module unittest thuần | `PYTHONPATH=kairos python -m unittest kairos.<module>` | 21/21 OK |
| — | Lint | `ruff format .` / `ruff check .` | Chưa chạy: môi trường chưa cài ruff |

Chi tiết Frappe: `test_api` 11, `test_summary` 14, `test_kairos_day_report` 4, `test_secrets` 4,
`test_scheduler` 2, `test_timeline` 2, `test_install` 1. Unittest thuần: `test_generation`,
`test_llm_context`, `test_quality`, `test_summary_output`.

### Danh sách rủi ro

| ID | Mức | Rủi ro | Bằng chứng | Hướng xử lý | Trạng thái |
|---|---|---|---|---|---|
| R-01 | Cao | Redaction C.5.1 bỏ sót secret có tiền tố tên biến | `_SECRET_ASSIGNMENT_PATTERN` (`kairos/kairos/quality.py`) bắt đầu bằng `\b`; `KAIROS_LLM_API_KEY=<value>` không bị che vì `_` trước `API_KEY` là ký tự word | Bỏ yêu cầu word boundary trước tên khóa hoặc cho phép tiền tố `[A-Z0-9_]*`; thêm test hồi quy | Mở |
| R-02 | Cao | `Authorization: token <key>:<secret>` chỉ che chữ `token`, lộ giá trị | Thử `sanitize_text` cho kết quả `Authorization: [REDACTED] <key>:<secret>` | Xử lý riêng scheme `token`/`Basic`, che toàn bộ phần credential | Mở |
| R-03 | Cao | Token đứng riêng không được che: `sk-…`, `AIza…`, `ghp_…`, `github_pat_…`, `glpat-…`, JWT | Thử `sanitize_text` với từng dạng: giữ nguyên | Thêm pattern theo tiền tố nhà cung cấp và JWT; thêm test | Mở |
| R-04 | Cao | Dữ liệu thật đã có Event còn chuỗi giống secret sau sanitize | Trên 11.140 Event của `kairos.local`: 43 Event khớp dạng `XXX_API_KEY=…`, 2 Event khớp `sk-…`. Chỉ đếm, chưa xem nội dung nên chưa xác định là secret thật hay placeholder | Sau khi sửa R-01→R-03: rà 45 Event; nếu là secret thật thì xoay vòng key và xem lại các summary đã sinh | Mở |
| R-05 | Cao / chờ xác nhận | Nội dung Event đã sanitize được gửi tới provider LLM bên ngoài | `kairos_llm_base_url` của site dev trỏ tới Google Gemini (OpenAI-compatible) | Chủ dự án xác nhận dữ liệu Codex session có thuộc phạm vi cần phê duyệt khi gửi ra ngoài không; trong lúc R-01→R-04 còn mở, hạn chế Generate Summary bằng LLM thật | Chờ xác nhận |
| R-06 | Trung bình | `bench run-tests --app kairos` chỉ phát hiện 4 test, dễ tưởng đã chạy đủ | Chạy `--app` ra 4 test; chạy từng module ra 38 test | Ghi rõ lệnh theo module trong `AGENTS.md` hoặc thêm script chạy toàn bộ | Mở |
| R-07 | Trung bình | DocType `Kairos Event` và `Kairos Settings` chưa có test | Không tồn tại `test_kairos_event.py`, `test_kairos_settings.py` | Thêm test cho derive `activity_date`, unique `event_id`, ràng buộc timezone | Mở |
| R-08 | Trung bình | Không có CI và chưa chạy lint | Không có workflow; ruff chưa cài trong `kairos-bench/env` | Cài ruff vào môi trường dev; cân nhắc pipeline GitLab cho collector và unittest thuần | Mở |
| R-09 | Trung bình | LLM được gọi đồng bộ trong web request | C.5.4c (background job, retry) chưa triển khai; `generate_day_summary` gọi provider trực tiếp | Triển khai C.5.4c | Mở — theo kế hoạch |
| R-10 | Trung bình | Chưa có audit snapshot cho claim đã validate | C.5.4b chưa triển khai | Triển khai C.5.4b theo thiết kế đã chốt trong `KAIROS.md` | Mở — theo kế hoạch |
| R-11 | Trung bình | Chỉ tiêu Gate C.5 chưa được đo | Chưa có số liệu ≥95% claim có evidence, ≤20% ngày cần sửa tay | Đo trong C.5.5 và Phase D | Mở — theo kế hoạch |
| R-12 | Trung bình | `raw_payload` lưu đường dẫn tuyệt đối và trích đoạn hội thoại, chưa có retention | Collector dry-run cho thấy `rollout_path` tuyệt đối và `snippet` trong `raw_payload` | Định nghĩa retention cho `Kairos Event`; cân nhắc rút gọn `raw_payload` | Mở |
| R-13 | Thấp | `upsert_events` không giới hạn kích thước batch | `_parse_events` chỉ kiểm tra list rỗng | Thêm giới hạn số Event mỗi request | Mở |
| R-14 | Thấp | 15 commit trên nhánh chưa merge, chưa có MR | `git log main..HEAD -- "Kairos Apps"`; GitLab MCP lỗi 502 nên chưa kiểm tra MR | Mở MR sau khi xử lý R-01→R-03 | Mở |
| R-15 | Thấp | Phase D chưa bắt đầu | `KAIROS.md` Phase D: D1–D4 chưa đánh dấu | Bắt đầu sau Gate C.5 | Mở — theo kế hoạch |

### Ghi chú thực hiện

- Test Frappe ghi dữ liệu vào DB dev `kairos.local`; không dùng site production.
- Redis cache/queue của bench (cổng 13001, 11001) được khởi động để chạy test.
- Kiểm tra R-04 dùng script tạm chỉ đếm số Event khớp pattern, không in nội dung; script đã được xóa.
