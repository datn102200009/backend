# Hướng Dẫn Chi Tiết Từng Bước: Quản Lý Định Mức Vật Tư (BOM) Và Lệnh Sản Xuất (Work Order)

Tài liệu này hướng dẫn bạn cách khai báo danh sách nguyên liệu để làm ra một sản phẩm và cách tạo ra các lệnh yêu cầu xưởng tiến hành sản xuất sản phẩm đó. Mọi chỉ dẫn dưới đây đều khớp 100% với giao diện, nhãn trường và nút bấm thực tế trên hệ thống.

---

## 1. Cách Quản Lý Định Mức Vật Tư (BOM)

Định mức vật tư là bản khai báo quy định rõ cần những linh kiện, nguyên liệu nào và số lượng bao nhiêu để tạo ra được một sản phẩm hoàn chỉnh. Để bắt đầu làm việc, hãy nhìn vào danh mục menu ở cột bên trái màn hình, tìm và nhấp chuột trái vào dòng chữ **"BOM"**. Trang **"Danh Sách Định Mức (BOM)"** sẽ hiện ra.

### 1.1. Cách Thêm Mới Một Danh Sách Định Mức (BOM)
* **Bước 1:** Ở góc bên phải phía trên màn hình, nhấp chuột trái vào nút bấm có dòng chữ **"Thêm BOM"** (kèm hình dấu cộng). Một ô cửa sổ lớn có tiêu đề **"Thêm Định Mức Mới"** sẽ hiện ra.
* **Bước 2:** Nhấp chuột vào ô trống dưới nhãn **"Tên định mức"** và gõ tên gợi nhớ cho định mức này (ví dụ: gõ `BOM Đèn Học Sinh Xuân Hòa`).
* **Bước 3:** Nhấp chuột vào ô chọn dưới nhãn **"Sản phẩm"** (phía dưới có dòng chữ mờ *-- Chọn sản phẩm --*). Gõ tên sản phẩm cần tìm vào ô tìm kiếm hoặc cuộn danh sách và nhấp chọn đúng sản phẩm đầu ra (ví dụ: chọn `Đèn LED học sinh - SP-LED-01`).
* **Bước 4:** Nhấp chuột vào ô trống dưới nhãn **"Ghi chú"** và gõ mô tả ngắn nếu cần.
* **Bước 5:** Khai báo danh sách các linh kiện cần dùng ở phần **"Danh sách linh kiện"**:
  - Nhấp chuột trái vào nút bấm **"Thêm"** (có hình dấu cộng nhỏ) ở thanh tiêu đề của mục này. Một dòng vật tư trống mới xuất hiện trong bảng.
  - Tại cột **"Linh kiện"**, nhấp chọn ô có chữ mờ *-- Chọn linh kiện --* và chọn đúng linh kiện đầu vào (ví dụ: chọn `Mạch Chip LED - LK-LED-02`).
  - Tại cột **"Số lượng"**, nhấp chuột vào ô nhập và gõ số lượng linh kiện cần để làm ra 1 sản phẩm đầu ra (ví dụ: gõ `1`). Cột **"ĐVT"** bên cạnh sẽ tự hiển thị đơn vị tính của linh kiện đó (ví dụ: `Cái`).
  - Nếu muốn thêm linh kiện tiếp theo, lặp lại việc nhấp nút **"Thêm"** và điền thông tin.
  - Nếu muốn xóa một dòng linh kiện đã chọn nhầm, nhấp chuột vào biểu tượng hình thùng rác màu xám ở cuối dòng đó.
* **Bước 6:** Sau khi hoàn tất khai báo, nhấp chuột trái vào nút bấm **"Tạo mới"** ở góc dưới bên phải màn hình để lưu lại. (Nếu muốn hủy bỏ không lưu, nhấp nút **"Hủy"** bên cạnh).

### 1.2. Cách Chỉnh Sửa Định Mức Đang Có
* **Bước 1:** Trên bảng danh sách định mức, tìm định mức bạn muốn chỉnh sửa.
* **Bước 2:** Nhấp chuột vào nút biểu tượng hình chiếc bút chì có chữ **"Chỉnh sửa"** ở cột **"Thao Tác"** cuối dòng. Ô cửa sổ **"Chỉnh Sửa Định Mức"** sẽ hiện ra.
* **Bước 3:** Bạn có thể thay đổi tên định mức, ghi chú, thêm linh kiện mới hoặc thay đổi số lượng linh kiện. *Lưu ý: Không thể thay đổi ô chọn "Sản phẩm" đầu ra khi đang sửa định mức.*
* **Bước 4:** Nhấp chuột trái vào nút bấm **"Cập nhật"** ở góc dưới bên phải để hoàn tất lưu lại thay đổi.

### 1.3. Cách Xóa Định Mức Khỏi Hệ Thống
* **Bước 1:** Tìm định mức cần xóa trên bảng danh sách định mức.
* **Bước 2:** Nhấp chuột vào nút biểu tượng hình thùng rác màu đỏ có chữ **"Xóa"** ở cột **"Thao Tác"** cuối dòng.
* **Bước 3:** Một ô cửa sổ nhỏ có tiêu đề **"Xác Nhận Xóa"** hiện lên kèm thông tin cảnh báo: *Bạn có chắc chắn muốn xóa định mức "{tên định mức}" không? Hành động này không thể hoàn tác.*
* **Bước 4:** Nhấp chuột vào nút **"Xóa định mức"** màu đỏ để xác nhận xóa vĩnh viễn, hoặc nhấp nút **"Hủy"** để bỏ qua. *Lưu ý: Hệ thống sẽ báo lỗi và ngăn chặn không cho xóa nếu định mức này đang được gán vào một lệnh sản xuất chưa hoàn tất thực tế.*

---

## 2. Cách Quản Lý Lệnh Sản Xuất (Work Order)

Lệnh sản xuất là yêu cầu chính thức gửi tới xưởng để tiến hành sản xuất sản phẩm theo định mức đã duyệt. Hãy nhìn vào danh mục menu ở cột bên trái màn hình, tìm và nhấp chuột trái vào dòng chữ **"Lệnh Sản Xuất"** để mở trang quản lý.

### 2.1. Cách Tạo Một Lệnh Sản Xuất Mới
* **Bước 1:** Ở góc trên bên phải màn hình, nhấp chuột trái vào nút bấm màu xanh dương có dòng chữ **"Tạo lệnh"** (kèm hình dấu cộng). Một ô cửa sổ lớn có tiêu đề **"Tạo Lệnh Sản Xuất"** sẽ hiện ra.
* **Bước 2:** Nhấp chuột vào ô trống dưới nhãn **"Mã Lệnh Sản Xuất"** và nhập mã số quản lý cho lệnh (ví dụ: gõ `LSX-2026-001`).
* **Bước 3:** Nhấp chuột vào ô chọn dưới nhãn **"Chọn định mức (BOM)"**. Chọn định mức tương ứng với sản phẩm cần làm từ danh sách hiện ra. Hệ thống sẽ tự hiển thị tên sản phẩm liên kết ở ngay phía dưới để bạn kiểm tra.
* **Bước 4:** Nhấp chuột vào ô trống dưới nhãn **"Số lượng yêu cầu"** và nhập số lượng sản phẩm cần xưởng làm ra (ví dụ: gõ `500`).
* **Bước 5:** Lựa chọn các kho hàng liên quan:
  - Chọn ô **"Kho nguồn (Nguyên liệu)"** để chỉ định nơi lấy linh kiện ra sản xuất.
  - Chọn ô **"Kho sản xuất (Tạm giữ)"** để chỉ định nơi chứa nguyên liệu đang trong quá trình lắp ráp tại xưởng.
  - Chọn ô **"Kho đích (Thành phẩm)"** để chỉ định nơi cất sản phẩm sau khi xưởng làm xong.
* **Bước 6:** Nhấp chọn ngày bắt đầu dự kiến tại ô **"Ngày bắt đầu (Dự kiến)"** và ngày kết thúc dự kiến tại ô **"Ngày kết thúc (Dự kiến)"** trên lịch hiện ra.
* **Bước 7:** Nhìn sang phần **"Dự trù nguyên liệu"** ở cột bên phải cửa sổ. Hệ thống sẽ tự động đối chiếu số lượng linh kiện cần dùng với số lượng thực tế đang có sẵn trong kho nguồn:
  - *Nếu cột "Thiếu" toàn bộ hiển thị số 0:* Kho hàng có đủ linh kiện cho xưởng sản xuất.
  - *Nếu cột "Thiếu" hiển thị số lượng màu đỏ:* Kho đang thiếu hụt nguyên vật liệu đó.
* **Bước 8:** Nhấp chuột trái vào nút **"Tạo lệnh"** ở góc dưới bên phải để hoàn tất.
  - *Nếu thiếu nguyên liệu:* Hệ thống sẽ mở hộp thoại cảnh báo: **"Cảnh báo thiếu hụt nguyên liệu"** với nội dung: *Có nguyên liệu bị thiếu hụt so với yêu cầu. Bạn có chắc chắn muốn tiếp tục tạo lệnh sản xuất này không?*. Nếu bạn vẫn muốn lập lệnh trước để chuẩn bị, nhấp nút **"Đồng ý"** để tiếp tục tạo lệnh dưới dạng **Bản nháp**.

### 2.2. Cách Điều Chỉnh Lệnh Sản Xuất (Trước Khi Thực Hiện)
* **Bước 1:** Trên bảng danh sách, tìm lệnh sản xuất ở trạng thái màu xám chữ **"Bản nháp"** (draft) cần điều chỉnh.
* **Bước 2:** Di chuyển chuột đến cột **"Thao Tác"** cuối dòng, nhấp chuột trái vào nút biểu tượng hình chiếc bút chì có chữ **"Chỉnh sửa"**. Cửa sổ **"Chỉnh Sửa Lệnh Sản Xuất"** hiện ra.
* **Bước 3:** Thay đổi số lượng yêu cầu, điều chỉnh các kho hàng liên kết hoặc thay đổi ngày dự kiến sản xuất.
* **Bước 4:** Nhấp chọn nút bấm **"Cập nhật"** ở góc dưới bên phải để hoàn tất lưu lại thay đổi. *Lưu ý: Hệ thống chỉ cho phép chỉnh sửa thông tin khi lệnh còn đang ở trạng thái Bản nháp.*

### 2.3. Cách Phê Duyệt Lệnh Sản Xuất Để Xưởng Bắt Đầu Làm
* **Bước 1:** Tìm lệnh sản xuất có trạng thái màu vàng chữ **"Chờ duyệt"** (pending_approval) cần phê duyệt trên bảng danh sách.
* **Bước 2:** Rê chuột đến cuối dòng đó ở cột **"Thao Tác"**, nhấp chuột trái vào nút biểu tượng hình nút Play màu xanh có chữ **"Phê duyệt"**.
* **Bước 3:** Một hộp thoại xác nhận hiện ra hỏi lại: *Bạn có chắc chắn muốn phê duyệt lệnh {tên lệnh}? Quá trình này sẽ xuất nguyên liệu từ kho nguồn.* Nhấp chọn nút xác nhận để duyệt. Trạng thái của lệnh sản xuất sẽ chuyển thành màu vàng chữ **"Đang sản xuất"** (in_progress).

### 2.4. Cách Nhập Số Liệu Giám Sát Sản Lượng Thực Tế
* **Bước 1:** Tìm lệnh sản xuất cần cập nhật đang ở trạng thái **"Đang sản xuất"** (in_progress).
* **Bước 2:** Di chuyển chuột đến cuối dòng ở cột **"Thao Tác"**, nhấp chuột trái vào nút biểu tượng mũi tên hướng phải màu cam có chữ **"Nhập liệu"**. Một cửa sổ có tiêu đề **"Nhập Liệu Sản Xuất"** sẽ hiện ra.
* **Bước 3:** Nhìn thông tin hiển thị gồm: Mã lệnh, Sản phẩm, SL yêu cầu, Đã SX, Còn lại. Nhấp chuột vào ô nhập dưới nhãn **"Số lượng sản xuất đợt này"** và nhập số lượng sản phẩm xưởng vừa hoàn thành trong đợt (ví dụ: gõ `200`).
* **Bước 4:** Nhìn bảng đối chiếu nguyên liệu sử dụng thực tế tại Kho Bán Thành Phẩm ở bên dưới. Nhấp chuột trái vào nút **"Xác nhận"** ở góc dưới để cập nhật. Hệ thống sẽ tự động trừ kho nguyên liệu và cộng dồn số lượng vừa nhập vào thông số tiến độ hiển thị ngoài bảng danh sách.

### 2.5. Cách Nghiệm Thu Hoàn Thành Lệnh Sản Xuất
* **Bước 1:** Khi xưởng đã sản xuất đủ số lượng yêu cầu, hoặc lệnh sản xuất hiển thị trạng thái màu xanh dương là **"Chờ nghiệm thu hoàn tất"** (pending_production_complete).
* **Bước 2:** Tìm lệnh sản xuất đó trên danh sách, rê chuột đến cột **"Thao Tác"** cuối dòng, nhấp chuột trái vào nút biểu tượng dấu tích xanh có chữ **"Hoàn thành"** hoặc **"Phê duyệt hoàn tất"**.
* **Bước 3:** Một hộp thoại xác nhận hiện ra: *Bạn có chắc chắn muốn hoàn thành lệnh {tên lệnh}? Quá trình này sẽ nhập thành phẩm vào kho đích.* Nhấp chọn xác nhận. Trạng thái lệnh sản xuất chuyển sang màu xanh lá hiển thị chữ **"Hoàn tất"** (completed).

### 2.6. Cách Hủy Lệnh Sản Xuất
* **Bước 1:** Tìm lệnh sản xuất muốn xóa hoặc hủy trong bảng danh sách.
* **Bước 2:** Ở cột **"Thao Tác"** cuối dòng, thực hiện thao tác tương ứng với trạng thái của lệnh:
  - *Nếu lệnh đang ở trạng thái Bản nháp:* Nhấp chọn nút biểu tượng thùng rác màu đỏ có chữ **"Xóa nháp"** để xóa hoàn toàn lệnh khỏi hệ thống.
  - *Nếu lệnh đang ở trạng thái Chờ duyệt:* Nhấp chọn nút biểu tượng dấu nhân màu đỏ có chữ **"Hủy"** để hủy lệnh. Một hộp thoại xác nhận hiện ra hỏi lại: *Bạn có chắc chắn muốn hủy lệnh {tên lệnh}?*. Nhấp chọn xác nhận để hủy, trạng thái lệnh chuyển sang màu đỏ là **"Đã hủy"** (cancelled).
