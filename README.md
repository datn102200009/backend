# DATN - ERP System Backend API

Phân hệ Backend xử lý logic nghiệp vụ, quản lý cơ sở dữ liệu và cung cấp RESTful API cho hệ thống Đồ Án Tốt Nghiệp - Quản trị Doanh nghiệp (ERP System).

## Công nghệ sử dụng
* **Language:** Python 3.10+
* **Framework:** Django 5.2.x & Django REST Framework (DRF) 3.14.0
* **Database:** PostgreSQL 15+
* **Authentication:** JWT (Simple JWT)
* **Caching & Message Broker:** Redis
* **Testing:** pytest & pytest-django
* **Linter & Formatter:** black, flake8, isort, pre-commit
* **Containerization:** Docker & Docker Compose

## Cấu trúc Thư mục Chính
```text
datn_backend/
├── apps/                  # Nơi chứa các app chức năng (Domain modules)
│   ├── accounts/          # Quản lý tài khoản, xác thực (JWT) & phân quyền (RBAC)
│   ├── common/            # Các tiện ích dùng chung (BaseModel, middleware, exceptions, v.v.)
│   ├── master_data/       # Dữ liệu danh mục cốt lõi (Sản phẩm, Đối tác, Khách hàng, Nhà cung cấp...)
│   ├── manufacturing/     # Quản lý quy trình sản xuất (Lệnh sản xuất, BOM, Công đoạn...)
│   ├── inventory/         # Quản lý kho hàng & Hàng tồn kho (Nhập kho, Xuất kho, Thẻ kho...)
│   ├── hrm/               # Quản lý nguồn nhân lực (Nhân sự, chấm công, lương...)
│   ├── finance/           # Quản lý tài chính, kế toán (Doanh thu, chi phí, công nợ...)
│   ├── purchasing/        # Quản lý mua hàng & đơn mua hàng
│   ├── sales/             # Quản lý bán hàng & đơn bán hàng
│   ├── crm/               # Quản lý quan hệ khách hàng
│   └── procurement/       # Quản lý cung ứng & mua sắm
├── datn_backend/          # Thư mục cấu hình dự án Django chính
│   ├── settings/          # Cấu hình phân chia theo môi trường (base.py, dev.py, production.py, test.py)
│   └── urls.py            # Định tuyến URL chính cho hệ thống
├── requirements/          # Danh sách các thư viện Python cần thiết
│   ├── base.txt           # Thư viện core chạy dự án
│   └── dev.txt            # Thư viện cho môi trường phát triển & kiểm thử (pytest, flake8, black...)
├── Dockerfile             # Cấu hình Docker image cho ứng dụng web backend
├── docker-compose.yml     # File Docker Compose khởi chạy các service (web, db, redis) ở môi trường dev
├── Makefile               # Chứa các lệnh tắt hữu ích cho quá trình phát triển (make command)
├── manage.py              # File CLI quản trị Django
└── pyproject.toml         # Cấu hình định dạng code (black, isort, pytest...)
```

## Hướng dẫn Cài đặt & Chạy Local

Có hai cách để khởi chạy dự án tại local: Chạy trực tiếp qua virtual environment hoặc chạy thông qua Docker Compose.

### Cách 1: Chạy trực tiếp (Local Development)

#### 1. Yêu cầu hệ thống
* Python phiên bản 3.10 trở lên.
* Đã cài đặt và đang chạy cơ sở dữ liệu **PostgreSQL** trên máy local.
* Đã cài đặt và đang chạy **Redis** (dành cho caching).

#### 2. Các bước triển khai

**Bước 1: Clone repository và di chuyển vào thư mục backend**
```bash
git clone [URL_REPO_BACKEND]
cd datn_backend
```

**Bước 2: Khởi tạo và kích hoạt môi trường ảo (Virtual Environment)**
```bash
# Trên Windows
python -m venv venv
.\venv\Scripts\activate

# Trên macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

**Bước 3: Cài đặt các thư viện phụ thuộc**
```bash
pip install -r requirements/dev.txt
# Hoặc sử dụng Makefile
make install
```

**Bước 4: Cấu hình biến môi trường**
* Tạo file `.env` ở thư mục gốc (cùng cấp với `manage.py`).
* Sao chép nội dung cấu hình từ file `.env.example` và điền các thông số phù hợp của bạn vào.

**Bước 5: Khởi tạo Cơ sở dữ liệu (Migration)**
```bash
python manage.py makemigrations
python manage.py migrate
# Hoặc sử dụng Makefile
make migrate
```

**Bước 6: Tạo tài khoản Admin (Tùy chọn)**
```bash
python manage.py createsuperuser
# Hoặc sử dụng Makefile
make createsuperuser
```

**Bước 7: Chạy Server Development**
```bash
python manage.py runserver
# Hoặc sử dụng Makefile
make dev
```
Server sẽ chạy tại địa chỉ: `http://127.0.0.1:8000/`

---

### Cách 2: Chạy bằng Docker Compose (Khuyên dùng)

Dự án đã tích hợp sẵn Docker Compose bao gồm các service: PostgreSQL, Redis, và Web Backend. Cách này giúp bạn không cần phải cài đặt thủ công cơ sở dữ liệu Postgres và Redis trên máy local của mình.

#### 1. Yêu cầu hệ thống
* Đã cài đặt **Docker** và **Docker Compose** (hoặc Docker Desktop).

#### 2. Các bước triển khai

**Bước 1: Cấu hình biến môi trường**
* Tạo file `.env` tại thư mục gốc tương tự cách 1. Đảm bảo cấu hình kết nối DB trỏ tới host `db` (đây là tên container được định nghĩa trong `docker-compose.yml`).
* Hoặc bạn chỉ cần tạo file `.env` trống, các giá trị mặc định trong `docker-compose.yml` sẽ tự động được sử dụng.

**Bước 2: Khởi chạy các container**
Sử dụng Makefile để thực hiện các thao tác:
```bash
# Build Docker image cho backend
make docker-build

# Khởi chạy các container ở chế độ background (Postgres, Redis, Web Backend)
make docker-up

# Theo dõi log của web backend
make docker-logs
```
*Lưu ý: Service web backend sẽ tự động chạy các file migrations và khởi chạy server ngay khi các container Database và Redis đã sẵn sàng hoạt động.*

**Bước 3: Dừng hệ thống**
Để dừng tất cả các container đang chạy:
```bash
make docker-down
```

---

## Kiểm thử & Định dạng Code (Testing & Formatting)

Để đảm bảo chất lượng code và tính ổn định của hệ thống:

* **Chạy Unit Tests (sử dụng pytest):**
  ```bash
  pytest
  # Hoặc dùng Makefile
  make test
  ```
  *(Các test coverage report dưới dạng HTML sẽ được lưu vào thư mục `htmlcov/`)*

* **Kiểm tra định dạng và chuẩn hóa code (Linter):**
  ```bash
  # Kiểm tra lỗi linter
  make lint

  # Tự động format code theo chuẩn black và sắp xếp import bằng isort
  make format
  ```

---

## Tài liệu API (API Documentation)

Hệ thống tích hợp tài liệu API trực quan ngay trong codebase thông qua giao diện Swagger UI. Sau khi chạy server backend thành công, bạn có thể truy cập tài liệu tại:

* **API Documentation UI:** `http://127.0.0.1:8000/api/docs/`

Tại giao diện Swagger UI, bạn có thể dễ dàng chuyển đổi qua lại giữa tài liệu API của các phân hệ (module) khác nhau thông qua thanh chọn menu thả xuống (dropdown selector) ở góc trên cùng bên phải. Các module được hỗ trợ tài liệu hóa bao gồm:
1. Accounts & Authorization
2. Master Data
3. Inventory Management
4. Manufacturing
5. Purchasing
6. Procurement
7. Sales & Orders
8. Finance & Accounting
9. CRM
