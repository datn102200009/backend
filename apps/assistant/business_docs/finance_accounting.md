# Hướng Dẫn Chi Tiết Từng Bước: Quản Lý Dòng Tiền, Hóa Đơn Và Tài Sản Cố Định

Tài liệu này chỉ dẫn chi tiết từng bước để quản lý các hoạt động tài chính bao gồm theo dõi dòng tiền thu chi thực tế, duyệt giao dịch dòng tiền chờ xử lý, chi trả lương nhân viên, đối soát thanh toán hóa đơn công nợ và khấu hao tài sản cố định. Các bước dưới đây được viết chính xác theo giao diện, nhãn trường và nút bấm thực tế của hệ thống.

---

## 1. Quy Trình Quản Lý Dòng Tiền (Thu / Chi Tiền Thực Tế)

Để bắt đầu làm việc, hãy tìm ở menu cột bên trái màn hình và nhấp chuột trái vào dòng chữ **"Dòng Tiền"**.

### 1.1. Cách Xem Dòng Tiền Thu / Chi Thực Tế
- Tab **"Dòng Tiền"** mặc định hiển thị bảng danh sách các giao dịch dòng tiền đã hoàn tất và ghi nhận thành công (trạng thái `posted`).
- Cột **"Loại"** hiển thị Badge màu xanh lá chữ **"Thu Tiền"** hoặc Badge màu đỏ chữ **"Chi Tiền"**.
- Cột **"Số Tiền"** hiển thị số tiền có màu xanh lá đối với thu tiền và màu đỏ đối với chi tiền để thủ quỹ dễ dàng kiểm soát.

### 1.2. Cách Duyệt Các Giao Dịch Cần Thanh Toán Hoặc Cần Thu (Chờ Phê Duyệt)
* **Quy trình hoạt động:** Khi người dùng thực hiện thanh toán hóa đơn mua (AP) hoặc thu tiền hóa đơn bán (AR) trên màn hình Quản Lý Hóa Đơn, hệ thống sẽ tự động tạo ra một giao dịch dòng tiền tương ứng ở trạng thái **Chờ duyệt** (pending_approval). Các giao dịch này bắt buộc phải được người quản lý dòng tiền duyệt thì mới thực tế trừ/cộng quỹ tiền và ghi sổ.
* **Cách duyệt:**
  - **Bước 1:** Tại trang Quản Lý Dòng Tiền, nhấp chọn tab **"Duyệt Giao Dịch"** ở đầu trang. Bảng danh sách các giao dịch dòng tiền đang chờ duyệt hiện ra.
  - **Bước 2:** Rà soát kỹ thông tin số tiền, loại giao dịch (Thu/Chi), phân loại và ghi chú của từng dòng.
  - **Bước 3:**
    - **Để duyệt giao dịch:** Rê chuột đến cuối dòng, nhấp chuột trái vào nút **"Duyệt"** (có hình dấu tích xanh). Số quỹ tiền sẽ được cập nhật và giao dịch chuyển sang trạng thái ghi sổ thành công.
    - **Để từ chối giao dịch:** Nhấp chuột trái vào nút **"Từ chối"** (có hình dấu nhân đỏ) ở cuối dòng giao dịch. Một hộp thoại xác nhận **"Từ chối phê duyệt giao dịch"** hiện lên, hãy nhập lý do từ chối vào ô trống và nhấn nút **"Từ chối"** màu đỏ để hoàn tất. Giao dịch sẽ bị từ chối phê duyệt.

### 1.3. Cách Duyệt Chi Tiền Cho Phiếu Lương Nhân Viên
* **Bước 1:** Tại trang Quản Lý Dòng Tiền, nhấp chọn tab **"Duyệt Lương"** ở đầu trang. Bảng danh sách các phiếu lương của nhân viên đang chờ duyệt chi trả tiền mặt/chuyển khoản sẽ hiện ra.
* **Bước 2:** Để duyệt chi lương:
  - **Duyệt chi lương từng người:** Tại dòng phiếu lương tương ứng, rê chuột đến cột **"Thao Tác"** cuối dòng và nhấp chuột trái vào nút **"Chi Trả"** (có biểu tượng hình chiếc thẻ tín dụng). Một ô cửa sổ **"Xác nhận chi trả lương"** hiện lên hiển thị số tiền lương thực lĩnh, hãy chọn **"Phương thức thanh toán:"** (chuyển khoản hoặc tiền mặt) rồi nhấn nút **"Xác nhận chi trả"** màu xanh ở góc dưới.
  - **Duyệt chi lương hàng loạt toàn công ty:** Nhấp chuột trái vào nút **"Chi Trả Toàn Bộ"** màu xám ở góc trên bên phải bảng danh sách. Một ô cửa sổ **"Chi trả toàn bộ bảng lương kỳ {kỳ lương}"** hiện lên hiển thị tổng số tiền chi trả, hãy chọn phương thức thanh toán hàng loạt và nhấn nút **"Xác nhận chi trả toàn bộ"** màu xanh để hoàn tất duyệt chi lương cho toàn bộ nhân viên.

---

## 2. Quy Trình Quản Lý Hóa Đơn (Thanh Toán / Thu Tiền Công Nợ)

Hãy tìm ở menu cột bên trái màn hình và nhấp chuột trái vào dòng chữ **"Hoá Đơn Mua/Bán"**. Màn hình hiển thị trang hóa đơn gồm hai tab ở đầu trang: Tab **"Hoá Đơn Mua"** (các hóa đơn phải trả nhà cung cấp - AP) và Tab **"Hoá Đơn Bán"** (các hóa đơn phải thu tiền của khách hàng - AR).

### 2.1. Cách Xem Danh Sách Hóa Đơn Mua / Bán
- Giao diện hóa đơn chia làm 2 phần: Tab **"Hoá Đơn Mua"** và Tab **"Hoá Đơn Bán"**. Bạn có thể xem nhanh trạng thái từng hóa đơn: *Chưa Thanh Toán*, *Thanh Toán Một Phần*, hoặc *Đã Thanh Toán*.

### 2.2. Cách Thanh Toán Hóa Đơn Mua Hàng (Chi Tiền Cho Nhà Cung Cấp)
* **Bước 1:** Nhấp chọn tab **"Hoá Đơn Mua"** ở đầu trang.
* **Bước 2:** Tìm hóa đơn cần chi trả đang hiển thị Badge trạng thái màu đỏ chữ **"Chưa Thanh Toán"** hoặc Badge màu vàng chữ **"Thanh Toán Một Phần"**.
* **Bước 3:** Di chuyển chuột đến cuối dòng đó ở cột **"Thao Tác"**, nhấp chuột trái vào nút bấm có biểu tượng hình thẻ tín dụng (khi rê chuột vào sẽ hiển thị chữ *Thanh toán*). Một ô cửa sổ có tiêu đề **"Thanh Toán Hóa Đơn Mua (AP)"** sẽ hiện lên ở giữa màn hình.
* **Bước 4:** Nhìn thông tin hiển thị dòng chữ **"Số tiền còn nợ:"** được in đậm màu đỏ. Nhấp chuột vào ô trống dưới nhãn **"Số tiền thanh toán (VND)"** và gõ số tiền thực tế bạn chi trả trong đợt này.
* **Bước 5:** Nhấp chuột vào ô chọn dưới nhãn **"Phương thức thanh toán"** và chọn phương thức thực tế (chọn `Chuyển khoản ngân hàng` hoặc `Tiền mặt`).
* **Bước 6:** Nhấp chuột trái vào nút bấm **"Xác nhận thanh toán"** màu xanh ở góc dưới cùng bên phải.
* **Bước 7:** Hộp thoại xác nhận có tiêu đề **"Xác nhận thanh toán hóa đơn"** hiện ra hỏi lại: *Bạn có chắc chắn muốn thanh toán số tiền {số tiền} cho hóa đơn mua hàng này không? Dòng tiền chi sẽ được tạo và ghi nhận hoàn tất ngay lập tức.* Nhấp chọn **"Xác nhận thanh toán"** trên hộp thoại để hoàn thành.

### 2.3. Cách Thu Tiền Hóa Đơn Bán Hàng (Thu Tiền Nợ Từ Khách Hàng)
* **Bước 1:** Nhấp chọn tab **"Hoá Đơn Bán"** ở đầu trang hóa đơn.
* **Bước 2:** Tìm hóa đơn của khách hàng cần thu tiền đang hiển thị Badge trạng thái **"Chưa Thanh Toán"** hoặc **"Thanh Toán Một Phần"**.
* **Bước 3:** Ở cột **"Thao Tác"** cuối dòng, nhấp chuột trái vào nút biểu tượng hình chiếc thẻ tín dụng (khi rê chuột vào hiển thị chữ *Thu tiền*). Cửa sổ có tiêu đề **"Thu Tiền Hóa Đơn Bán (AR)"** hiện ra.
* **Bước 4:** Giao diện hiển thị tên khách hàng và số tiền còn nợ. Nhấp chuột vào ô trống dưới nhãn **"Số tiền thu nợ (VND)"** và gõ số tiền khách hàng trả thực tế.
* **Bước 5:** Chọn phương thức tại ô chọn **"Phương thức thu tiền"** (chọn `Chuyển khoản ngân hàng` hoặc `Tiền mặt`).
* **Bước 6:** Nhấp chuột trái vào nút bấm **"Xác nhận thu tiền"** ở góc dưới cùng bên phải.
* **Bước 7:** Hộp thoại xác nhận có tiêu đề **"Xác nhận thu tiền hóa đơn"** hiện lên: *Bạn có chắc chắn muốn thu số tiền {số tiền} từ khách hàng {tên khách} cho hóa đơn bán hàng này không? Dòng tiền thu sẽ được tạo và ghi nhận hoàn tất ngay lập tức.* Nhấp chọn **"Xác nhận thu tiền"** trên hộp thoại để hoàn thành.

---

## 3. Quy Trình Quản Lý Tài Sản Cố Định (Fixed Assets)

Quản lý thông tin và tính khấu hao các tài sản có giá trị lớn (như xe tải, máy hàn chip...). Hãy nhấp chọn menu **"Tài Sản Cố Định"** ở menu bên trái màn hình.

### 3.1. Cách Ghi Nhận Mua Tài Sản Cố Định Mới
* **Bước 1:** Tại tab **"Danh Sách Tài Sản"**, nhấp chuột trái vào nút bấm **"Thêm tài sản cố định"** (hình dấu cộng) ở góc trên bên phải màn hình. Hộp thoại **"Ghi Nhận Mua Tài Sản Cố Định"** hiện ra ở giữa màn hình.
* **Bước 2:** Nhập đầy đủ các thông tin của tài sản:
  - Nhập **"Tên tài sản"** và **"Nguyên giá (VND)"**.
  - Nhập tên nhà cung cấp bán tài sản vào ô **"Nhà cung cấp"** và chọn **"Phương thức thanh toán"** (Tiền mặt / Chuyển khoản ngân hàng).
  - Tại ô **"Phương pháp khấu hao"**, nhấp chọn:
    - **"Đường thẳng"**: Hệ thống sẽ mở thêm ô nhập **"Số tháng khấu hao hữu ích"**. Hãy nhập số tháng tài sản có thể hoạt động (ví dụ: gõ `60` cho 5 năm).
    - **"Sản lượng (UOP)"**: Hệ thống mở thêm ô nhập **"Công suất thiết kế (Tổng sản lượng)"**. Hãy nhập tổng số sản phẩm dự kiến tài sản làm ra trong vòng đời (ví dụ: gõ `100.000` sản phẩm).
* **Bước 3:** Nhấp chọn nút bấm **"Ghi nhận mua"** ở góc dưới bên phải hộp thoại để hoàn tất.

### 3.2. Cách Xem Thông Tin Và Lịch Sử Khấu Hao Tài Sản
* **Bước 1:** Tìm tài sản cố định cần xem trong bảng danh sách tài sản.
* **Bước 2:** Ở cột **"Thao Tác"** cuối dòng, nhấp chọn nút biểu tượng hình con mắt có chữ **"Xem chi tiết"**. Hộp thoại chi tiết tài sản hiện ra hiển thị Nguyên giá, Lũy kế khấu hao, và tab **"Lịch Sử Khấu Hao"** của tài sản đó.
* **Bước 3:** Bạn cũng có thể nhấp chọn tab **"Lịch Sử Khấu Hao"** ở ngay đầu màn hình chính của Tài Sản Cố Định để theo dõi toàn bộ nhật ký trích khấu hao hàng tháng của tất cả tài sản trong hệ thống.

### 3.3. Cách Chỉnh Sửa Thông Tin Tài Sản Cố Định
* **Bước 1:** Tìm tài sản cần sửa trên danh sách (tài sản bắt buộc phải ở trạng thái **Đang nhàn rỗi** (idle) thì mới có thể chỉnh sửa).
* **Bước 2:** Nhấp chọn nút biểu tượng hình chiếc bút chì có chữ **"Chỉnh sửa"** ở cột **"Thao Tác"** cuối dòng.
* **Bước 3:** Điều chỉnh tên tài sản, phương pháp khấu hao, hoặc số tháng khấu hao/công suất thiết kế.
* **Bước 4:** Nhấp chọn nút bấm **"Cập nhật"** ở góc dưới bên phải để hoàn tất lưu lại thay đổi.

### 3.4. Cách Yêu Cầu Thanh Lý Tài Sản Cố Định
* **Bước 1:** Tìm tài sản cần thanh lý trên danh sách (bắt buộc ở trạng thái **Đang nhàn rỗi** (idle) và bạn phải được phân quyền).
* **Bước 2:** Nhấp chọn nút biểu tượng hình mũi tên xoay tròn màu đỏ có chữ **"Yêu cầu thanh lý"** ở cột **"Thao Tác"** cuối dòng. Hộp thoại **"Yêu Cầu Thanh Lý Tài Sản Cố Định"** hiện ra.
* **Bước 3:** Nhập số tiền thu hồi dự kiến vào ô **"Giá trị thu về dự kiến (VND)"** (nếu bán thanh lý không lấy tiền thì gõ `0`) và nhập lý do vào ô **"Ghi chú / Lý do thanh lý"**.
* **Bước 4:** Nhấp chọn nút bấm **"Ghi nhận yêu cầu"** màu đỏ ở góc dưới bên phải. Hộp thoại xác nhận **"Xác nhận yêu cầu thanh lý tài sản"** hiện ra:
  - *Nếu giá trị thu hồi bằng 0:* Xuất hiện dòng chữ cảnh báo màu vàng: *Giá trị thu hồi bằng 0 — tài sản sẽ được thanh lý ngay khi bạn xác nhận (không qua bước duyệt Dòng Tiền).* Khi bạn bấm **"Xác nhận thanh lý"**, trạng thái tài sản sẽ chuyển sang màu đỏ là **"Đã thanh lý"** (disposed) ngay lập tức.
  - *Nếu giá trị thu hồi lớn hơn 0:* Khi bạn bấm **"Xác nhận thanh lý"**, trạng thái tài sản sẽ chuyển sang màu vàng là **"Chờ duyệt thanh lý"** (pending_dispose). Hệ thống tự tạo một giao dịch dòng tiền thu chờ duyệt. Tài sản chỉ thực sự chuyển sang trạng thái màu đỏ **"Đã thanh lý"** khi thủ quỹ phê duyệt dòng tiền thu thanh lý tương ứng này.
