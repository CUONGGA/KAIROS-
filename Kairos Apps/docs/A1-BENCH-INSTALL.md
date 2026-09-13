# A1 — Cài bench & gắn app `kairos` (tự làm)

Mục tiêu A1: app skeleton đã có trong repo → bạn **tự** cài Frappe Bench (học) → `get-app` / `install-app` → thấy **Kairos** trên site.

Repo đã chuẩn bị code tại [`kairos/`](../kairos/). **Không** cần AI chạy lệnh cài bench giúp bạn.

---

## 0. Chuẩn bị kiến thức

Đọc nhanh (chọn 1 nguồn):

- [Frappe Framework — Installation](https://frappeframework.com/docs/user/en/installation)
- [Bench Cheatsheet](https://frappeframework.com/docs/user/en/bench)

Trên Windows, nhiều người học Frappe bằng:

- **WSL2 (Ubuntu)** — gần guide chính thức nhất, hoặc
- **Docker** / VM Linux

Các lệnh dưới đây giả định bạn đang ở shell Linux/WSL, đã có Python 3.10+, git, MariaDB/Postgres theo guide.

---

## 1. Cài Bench (một lần trên máy học / VPS)

Làm theo docs chính thức. Ví dụ (tóm tắt — đối chiếu version mới nhất trên docs):

```bash
# Cài bench CLI (ví dụ)
pip install frappe-bench

# Tạo thư mục bench (đổi tên/path tùy bạn)
bench init frappe-bench --frappe-branch version-15
cd frappe-bench
```

Tạo site:

```bash
bench new-site kairos.local
# nhập MariaDB root password + Administrator password khi được hỏi
```

Bật developer mode (tiện lúc học):

```bash
bench --site kairos.local set-config developer_mode 1
bench --site kairos.local clear-cache
```

Chạy Desk local:

```bash
bench start
# Mở http://kairos.local:8000 (hoặc URL bench in ra)
```

**Done bước 1:** login Administrator được trên Desk.

---

## 2. Gắn app `kairos` từ repo này

App nằm ở:

`c:\Projects\Kairos Apps\kairos`  
(trên WSL có thể là `/mnt/c/Projects/Kairos Apps/kairos`)

Từ thư mục `frappe-bench`:

```bash
# Cách A — path local (học trên cùng máy / mount)
bench get-app "/mnt/c/Projects/Kairos Apps/kairos"

# Cách B — nếu bạn clone repo lên VPS
# bench get-app /path/to/Kairos\ Apps/kairos
```

Cài vào site:

```bash
bench --site kairos.local install-app kairos
```

Migrate (an toàn sau install):

```bash
bench --site kairos.local migrate
```

Restart nếu đang `bench start` (Ctrl+C rồi `bench start` lại), hoặc:

```bash
bench --site kairos.local clear-cache
```

**Done bước 2:** trong Desk → Awesome Bar gõ **Kairos**, hoặc xem Installed Apps có `kairos`.

---

## 3. Kiểm tra A1 (checklist)

- [x] `bench init` + `new-site` xong, login Desk được *(kairos-bench, port 8001)*
- [x] Gắn app `kairos/` (symlink / install-app)
- [x] `install-app kairos` + `migrate` không lỗi
- [x] App **Kairos** / login Desk OK
- [ ] Chưa cần DocType Event/Report (đó là **A2–A4**)

---

## 4. Lỗi hay gặp (học)

| Hiện tượng | Gợi ý |
|------------|--------|
| `get-app` path có khoảng trắng | Bọc path trong dấu `"..."` |
| App không hiện | `install-app` đúng `--site`; `migrate`; clear-cache |
| MariaDB access denied | Kiểm tra root password lúc `new-site` |
| Port 8000 bận | Đổi hoặc tắt process cũ |

---

## 5. Sau A1

Báo lại khi đã thấy app trên site → làm tiếp **A2** (`Kairos Settings` DocType).

Cấu trúc skeleton hiện có:

```text
kairos/
  pyproject.toml
  kairos/
    hooks.py
    modules.txt
    patches.txt
    kairos/doctype/   # trống — A2+
```
