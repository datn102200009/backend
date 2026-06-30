# Hướng Dẫn Chi Tiết Từng Bước: Quản Lý Sản Phẩm Và Giao Dịch Kho

Tài liệu này hướng dẫn bạn từng bước nhỏ để thực hiện các thao tác thêm mới sản phẩm vật tư, lập các phiếu nhập kho, xuất kho, chuyển kho và cách tra cứu tồn kho thực tế của doanh nghiệp. Mọi chỉ dẫn dưới đây đều được viết dựa trên giao diện, nhãn trường và nút bấm thực tế của hệ thống.

---

## 1. Cách Quản Lý Danh Mục Sản Phẩm (Vật Tư)

Để quản lý thông tin các mặt hàng, trước hết hãy nhìn sang danh mục menu ở cột bên trái màn hình, tìm và nhấp chuột trái vào dòng chữ **"Kho"**. Mặc định, màn hình sẽ hiển thị tab **"Sản Phẩm"** với danh sách các sản phẩm đang có.

### 1.1. Cách Thêm Mới Một Sản Phẩm (Vật Tư)
* **Bước 1:** Ở góc trên cùng bên phải màn hình, nhấp chuột trái vào nút bấm màu xanh dương có dòng chữ **"Thêm SP"** (kèm hình dấu cộng). Một ô cửa sổ (hộp thoại) có tiêu đề **"Thêm Sản Phẩm Mới"** hiện ra ở giữa màn hình.
* **Bước 2:** Nhấp chuột vào ô trống dưới nhãn **"Mã sản phẩm"** và gõ mã số duy nhất của sản phẩm (ví dụ: gõ `SP-LED-01`).
* **Bước 3:** Nhấp chuột vào ô trống dưới nhãn **"Tên sản phẩm"** và gõ tên đầy đủ của sản phẩm (ví dụ: gõ `Đèn LED học sinh`).
* **Bước 4:** Nhấp chuột vào ô trống dưới nhãn **"Ngưỡng tối thiểu tồn kho"** và nhập số lượng giới hạn cảnh báo (ví dụ: gõ `100` để hệ thống cảnh báo khi sản phẩm trong kho còn dưới 100 cái).
* **Bước 5:** Lựa chọn các thông tin thuộc tính của sản phẩm ở phía dưới:
  - Tại ô **"Đơn vị tính"**, nhấp chọn đơn vị tính thích hợp từ danh sách hiện ra (ví dụ: chọn `Cái`).
  - Tại ô **"Trạng thái"**, nhấp chọn trạng thái hoạt động (chọn `Hoạt động` để cho phép giao dịch, hoặc `Ngừng HĐ` / `Ngừng kinh doanh` nếu ngừng sử dụng).
* **Bước 6:** Nếu sản phẩm này là hàng nhập khẩu từ nước ngoài, nhấp chuột tích chọn vào ô vuông nhỏ trước dòng chữ **"Hàng nhập khẩu"**.
* **Bước 7:** Nhấp chuột trái vào nút bấm **"Tạo mới"** ở góc dưới cùng bên phải cửa sổ để hoàn tất lưu thông tin (hoặc nhấp **"Hủy"** bên cạnh nếu không muốn lưu).

### 1.2. Cách Sửa Đổi Thông Tin Sản Phẩm
* **Bước 1:** Tìm sản phẩm bạn cần chỉnh sửa trong bảng danh sách sản phẩm.
* **Bước 2:** Di chuyển chuột đến cuối dòng sản phẩm đó, tại cột **"Thao Tác"**, nhấp chuột trái vào nút biểu tượng hình chiếc bút chì có chữ **"Chỉnh sửa"**. Cửa sổ **"Chỉnh Sửa Sản Phẩm"** hiện ra.
* **Bước 3:** Thay đổi tên sản phẩm, ngưỡng tối thiểu tồn kho, đơn vị tính, trạng thái hoặc tích chọn hàng nhập khẩu tùy theo nhu cầu. *Lưu ý: Mã sản phẩm được hiển thị cố định và không thể chỉnh sửa.*
* **Bước 4:** Nhấp chuột trái vào nút **"Cập nhật"** ở phía dưới để lưu lại thay đổi.

### 1.3. Cách Xóa Sản Phẩm Khỏi Hệ Thống
* **Bước 1:** Tìm sản phẩm muốn xóa trong danh sách sản phẩm.
* **Bước 2:** Di chuyển chuột đến cuối dòng sản phẩm, tại cột **"Thao Tác"**, nhấp chuột trái vào nút biểu tượng hình thùng rác màu đỏ có chữ **"Xóa"**.
* **Bước 3:** Một hộp thoại xác nhận có tiêu đề **"Xác Nhận Xóa"** hiện lên kèm thông báo: *Bạn có chắc chắn muốn xóa sản phẩm "{tên sản phẩm}" không? Nếu sản phẩm đã phát sinh giao dịch, hệ thống sẽ từ chối thao tác này.*
* **Bước 4:** Nhấp chọn nút bấm màu đỏ **"Xóa Sản Phẩm"** để hoàn tất xóa sản phẩm, hoặc nhấp nút **"Hủy"** bên cạnh nếu muốn giữ lại.
  * *Lưu ý:* Hệ thống sẽ tự động chặn thao tác xóa và báo lỗi nếu sản phẩm này đã từng phát sinh phiếu nhập/xuất kho hoặc nằm trong định mức vật tư (BOM) để bảo vệ tính toàn vẹn dữ liệu.

---

## 2. Cách Tạo Phiếu Kho (Nhập Kho / Xuất Kho / Chuyển Kho)

Tất cả các giao dịch đưa hàng vào kho, lấy hàng ra khỏi kho hoặc chuyển hàng qua lại giữa các kho đều phải lập phiếu kho. Hãy nhấp chọn menu **"Kho"** ở menu bên trái màn hình, sau đó nhấp chọn tab **"Phiếu Kho"** ở đầu trang.

### 2.1. Cách Lập Phiếu Kho Mới (Phiếu Nháp)
* **Bước 1:** Ở góc trên bên phải màn hình, nhấp chuột trái vào một trong 3 nút bấm tương ứng với loại giao dịch thực tế bạn muốn thực hiện:
  - Nhấp nút **"Nhập Kho"** để lập phiếu nhập hàng hóa, thành phẩm từ nhà cung cấp hoặc xưởng về kho.
  - Nhấp nút **"Xuất Kho"** để xuất nguyên liệu cho xưởng sản xuất hoặc xuất giao hàng bán đi.
  - Nhấp nút **"Chuyển Kho"** để lập phiếu điều chuyển hàng nội bộ giữa các kho trong công ty.
* **Bước 2:** Ô cửa sổ tương ứng với loại phiếu đã chọn hiện ra (ví dụ: có tiêu đề *Tạo Phiếu Nhập Kho*). Nhấp chuột vào ô nhập dưới nhãn **"Tên phiếu"** và gõ tên mô tả ngắn cho phiếu (ví dụ: gõ `Phiếu nhập hàng linh kiện LED tháng 6`).
* **Bước 3:** Lựa chọn kho hàng liên quan theo loại phiếu bạn đang lập:
  - *Nếu là phiếu Nhập kho:* Chọn ô **"Kho đích"** và nhấp chọn kho nhận hàng đến.
  - *Nếu là phiếu Xuất kho:* Chọn ô **"Kho nguồn"** và nhấp chọn kho xuất hàng đi.
  - *Nếu là phiếu Chuyển kho:* Chọn cả hai ô **"Kho nguồn"** (kho xuất đi) và **"Kho đích"** (kho nhận đến).
* **Bước 4:** Nhập nội dung vào ô **"Ghi chú"** (nếu cần).
* **Bước 5:** Khai báo danh sách các sản phẩm cần giao dịch ở phần **"Danh sách vật tư"**:
  - Nhấp chuột trái vào nút bấm **"Thêm"** (có hình dấu cộng nhỏ) ở góc trên bên phải mục này. Một dòng vật tư trống mới xuất hiện trong bảng.
  - Tại cột **"Vật tư"**, nhấp chọn ô select và chọn đúng mặt hàng.
  - Tại cột **"Số lượng"**, gõ số lượng hàng thực tế cần giao dịch. Cột bên cạnh hiển thị đơn vị tính và số lượng đang còn tồn thực tế của mặt hàng đó tại kho nguồn (ví dụ: hiển thị `Cái` và dòng chữ nhỏ màu xanh/đỏ `Tồn: 1500` để bạn kiểm soát số lượng).
  - *Lưu ý:* Hệ thống sẽ báo lỗi nếu bạn chọn trùng lặp cùng một sản phẩm ở nhiều dòng trên cùng một phiếu kho. Đối với phiếu xuất hoặc chuyển kho, nếu số lượng bạn nhập lớn hơn số lượng hiển thị ở cột tồn, hệ thống sẽ hiện cảnh báo đỏ và ngăn không cho tạo phiếu.
* **Bước 6:** Nhấp chuột trái vào nút bấm **"Tạo mới"** ở góc dưới cùng bên phải để hoàn tất lưu phiếu ở trạng thái **Bản Nháp** (draft).

### 2.2. Cách Phê Duyệt Chi Tiết Phiếu Kho Để Ghi Nhận Tồn Kho Thực Tế
* **Bước 1:** Trên bảng danh sách phiếu kho, tìm phiếu có trạng thái màu xám hiển thị chữ **"Nháp"** (draft) và nhấp chọn dòng phiếu đó. Một ô cửa sổ có tiêu đề **"Chi Tiết Phiếu Kho: {Tên phiếu}"** hiện ra.
* **Bước 2:** Kiểm tra kỹ danh sách mặt hàng, số lượng và các kho xuất/kho nhận trong bảng hiển thị.
* **Bước 3:** Nhìn vào góc dưới cùng bên phải của ô cửa sổ:
  - *Lưu ý đối với chu trình mua hàng:* Đối với hàng linh kiện mua từ nhà cung cấp về, hệ thống sẽ hiển thị một Banner thông tin màu xanh dương báo: *“Phiếu nhập kho này thuộc chu trình mua hàng. Vui lòng thực hiện kiểm định QA/QC và gán kho nhận hàng tại tab Quản Lý Lô Hàng.”*. Bạn không được và không cần phê duyệt thủ công phiếu kho mua hàng tại đây; phiếu nhập kho thực tế (ở trạng thái **Đã duyệt**) sẽ được **hệ thống tự động khởi tạo và ghi sổ** khi bạn hoàn tất tiếp nhận lô hàng tại tab **"Quản Lý Lô Hàng"** (nằm trong trang Mua Hàng).
  - *Nếu là các phiếu kho khác (Xuất kho, Chuyển kho nội bộ, Nhập kho xưởng sản xuất):* Nhấp chuột trái vào nút bấm **"Duyệt Phiếu"** màu xanh dương. Hệ thống sẽ mở hộp thoại **"Xác Nhận Phê Duyệt"** -> kiểm tra kho nhận/kho xuất và danh sách vật tư -> nhấp chọn nút **"Phê duyệt"** màu xanh dương ở dưới. Hệ thống sẽ tự động cộng/trừ số lượng tồn kho thực tế và khóa phiếu lại, chuyển trạng thái sang màu xanh lá hiển thị chữ **"Đã duyệt"** (posted).
* **Bước 4:** Nếu muốn hủy bỏ hoàn toàn phiếu nháp này, nhấp chọn nút bấm **"Hủy Phiếu"** màu đỏ ở góc dưới bên trái cửa sổ chi tiết. Hộp thoại xác nhận hiện ra hỏi lại: *Bạn có chắc chắn muốn HỦY phiếu "{tên phiếu}"? Hành động này không thể khôi phục.* Nhấp chọn xác nhận để hủy, phiếu kho sẽ chuyển sang trạng thái màu xám chữ **"Đã hủy"** (cancelled).

---

## 3. Cách Tra Cứu Tồn Kho Thực Tế

Khi bạn cần kiểm tra nhanh xem một sản phẩm bất kỳ hiện còn bao nhiêu cái trong kho:
* **Bước 1:** Nhấp chọn menu **"Kho"** ở menu bên trái màn hình, sau đó nhấp chọn tab **"Tồn Kho"** ở đầu trang.
* **Bước 2:** Nhấp chuột vào ô tìm kiếm ở phía trên bảng danh sách (có chữ mờ *Tìm theo mã hoặc tên sản phẩm...*), gõ mã hoặc tên sản phẩm cần kiểm tra (ví dụ: gõ `Mạch Chip LED`) rồi nhấn phím Enter trên bàn phím.
* **Bước 3:** Bảng danh sách sẽ lọc ra sản phẩm bạn tìm kiếm. Nhìn vào các cột thông tin trên dòng sản phẩm đó để kiểm tra số lượng tồn kho thực tế tại từng kho hàng.
