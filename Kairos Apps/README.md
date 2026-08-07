# Kairos Apps

Monorepo / workspace cho **Kairos** — AI Work Assistant (1 user).

Spec đầy đủ: [KAIROS.md](./KAIROS.md).

## Apps & packages

| Path | Vai trò | Chạy ở đâu | Trạng thái |
|------|---------|------------|------------|
| [`kairos/`](./kairos/) | Frappe custom app: DocTypes, API nhận Event, Day Report, Copy to Clipboard | **VPS** (bench) | Chưa scaffold (Phase A) |
| [`collectors/codex/`](./collectors/codex/) | CLI collector `codex@1`: đọc `~/.codex/sessions` → map Event → POST Frappe | **Máy Developer** | Chưa scaffold (Phase B) |

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

1. **A** — Scaffold `kairos` + API `upsert_events`
2. **B** — CLI `collectors/codex` + Task Scheduler
3. **C** — Generate Day Report + Copy to Clipboard
4. **D** — Soft launch 3–5 ngày

Backlog: collectors Git / Cursor CLI / ChatGPT, service nền, Teams webhook.

## Tài liệu

- [KAIROS.md](./KAIROS.md) — sản phẩm, event model, mapper Codex, kế hoạch chốt
