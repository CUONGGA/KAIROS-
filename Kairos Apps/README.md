# Kairos Apps

Monorepo / workspace cho **Kairos** — AI Work Assistant (1 user).

Spec đầy đủ: [KAIROS.md](./KAIROS.md).

## Apps & packages

| Path | Vai trò | Chạy ở đâu | Trạng thái |
|------|---------|------------|------------|
| [`kairos/`](./kairos/) | Frappe custom app: DocTypes, API nhận Event, Day Report, Copy to Clipboard | **kairos-bench** (local) / VPS | **A1–A7 xong** — Event API + collector auth sẵn sàng; tiếp Phase B |
| [`collectors/codex/`](./collectors/codex/) | CLI collector `codex@1`: đọc `~/.codex/sessions` → map Event → POST Frappe | **Máy Developer** | **B1–B4 xong** — CLI + parser + mapper + HTTP; tiếp B5 E2E |

Hiện workspace mới có spec; code app sẽ thêm theo phase A→D trong [KAIROS.md](./KAIROS.md).

## Kairos làm gì

- Thu thập hoạt động từ AI (MVP: **Codex** local sessions).
- Chuẩn hóa thành **Kairos Event** (canonical model).
- Timeline theo ngày → AI tổng hợp **Kairos Day Report**.
- **Copy to Clipboard** → paste Teams (hoặc nơi khác).
- Lưu lịch sử trên Frappe Desk để tìm lại.

**Không phải:** Task Manager, Jira, CRM.

## Kiến trúc ngắn

```text
[Developer PC]                    [VPS]
~/.codex/sessions
    → collectors/codex (CLI ~30m)
    → POST API ─────────────────→  kairos (Frappe)
                                      → Kairos Event
                                      → Kairos Day Report
                                      → Copy to Clipboard
```

## DocTypes (app `kairos`)

| DocType | Mục đích |
|---------|----------|
| `Kairos Settings` | Cấu hình non-secret (model, prompt) |
| `Kairos Event` | 1 hoạt động đã chuẩn hóa |
| `Kairos Day Report` | Báo cáo ngày + nút Copy |

## Secrets

| Máy | Biến / config |
|-----|----------------|
| VPS | `kairos_llm_api_key`, `kairos_llm_base_url` (`site_config` hoặc env) |
| Dev | `KAIROS_FRAPPE_URL`, `KAIROS_FRAPPE_TOKEN` (env local, không commit) |

## Roadmap MVP

Chi tiết + tick: [KAIROS.md § Kế hoạch](./KAIROS.md#kế-hoạch-triển-khai-mvp).

| Phase | TT | Tóm tắt |
|-------|----|---------|
| **A** Frappe | A1–A7 [x] | Settings → Event → Day Report → secrets → upsert API → token |
| **B** Collector | [ ] | CLI Codex → POST Frappe |
| **C** Day Report | [ ] | Generate + Copy to Clipboard |
| **D** Soft launch | [ ] | 3–5 ngày thật |

Backlog: collectors Git / Cursor CLI / ChatGPT, service nền, Teams webhook.

## Tài liệu

- [KAIROS.md](./KAIROS.md) — sản phẩm, event model, mapper Codex, kế hoạch chốt
