# Hướng Dẫn Chi Tiết Từng Bước: Quản Lý Mua Hàng, Bán Hàng Và Đối Tác (Khách Hàng / Nhà Cung Cấp)

Tài liệu này chỉ dẫn chi tiết từng bước để thực hiện quy trình lập đơn mua hàng từ nhà cung cấp, quản lý lô hàng nhập kho (Landed Cost), lập đơn bán hàng cho khách hàng, quản lý giao nhận và quản lý thông tin đối tác. Mọi chỉ dẫn dưới đây đều được viết dựa trên giao diện, nhãn trường và nút bấm thực tế của hệ thống.

---

## 1. Quy Trình Quản Lý Mua Hàng (Purchasing)

Để bắt đầu làm việc, hãy tìm ở menu cột bên trái màn hình và nhấp chuột trái vào dòng chữ **"Mua Hàng"**. Trang Quản Lý Mua Hàng sẽ hiển thị hai tab ở đầu trang: **"Đơn Mua Hàng"** và **"Quản Lý Lô Hàng"**.

### 1.1. Cách Tạo Đơn Mua Hàng Mới (Lưu Nháp)
* **Bước 1:** Nhấp chọn tab **"Đơn Mua Hàng"** ở đầu trang.
* **Bước 2:** Ở góc trên cùng bên phải màn hình, nhấp chuột trái vào nút bấm màu xanh dương có dòng chữ **"Thêm Đơn Mua"** (kèm hình dấu cộng). Một ô cửa sổ lớn có tiêu đề **"Thêm Đơn Mua Hàng Mới"** sẽ hiện ra.
* **Bước 3:** Nhấp chuột chọn ô dưới nhãn **"Nhà Cung Cấp"** và chọn đúng nhà cung cấp từ danh sách hiện ra (ví dụ: chọn `Tổng Công ty Thiết bị Điện tử miền Bắc (SUP-001)`).
* **Bước 4:** Lựa chọn ngày giao hàng dự kiến tại ô **"Ngày Giao Dự Kiến"** và hạn thanh toán tại ô **"Hạn Thanh Toán"** trên lịch hiện ra. Mặc định hệ thống tự chọn ngày hôm nay.
* **Bước 5:** Khai báo danh sách các linh kiện cần mua ở phần **"Danh Sách Linh Kiện"**:
  - Nhấp chuột trái vào nút bấm **"Thêm"** (có hình dấu cộng nhỏ) ở góc trên bên phải mục này. Một dòng vật tư trống mới xuất hiện trong bảng.
  - Tại cột **"Linh Kiện"**, nhấp chọn ô select và chọn đúng linh kiện cần mua.
  - Tại cột **"Số Lượng"**, gõ số lượng muốn mua. Cột bên cạnh hiển thị đơn vị tính (ví dụ: `Cái`).
  - Tại cột **"Đơn Giá"**, gõ giá tiền của một linh kiện. Hệ thống sẽ tự động nhân thành tiền và cập nhật số tiền ở dòng **"Tổng giá trị đơn hàng"** bên dưới.
  - Để thêm linh kiện tiếp theo, nhấp nút **"Thêm"** và lặp lại thao tác. Để xóa một dòng linh kiện đã chọn nhầm, nhấp nút biểu tượng thùng rác màu xám ở cuối dòng đó.
* **Bước 6:** Nhấp chuột vào ô nhập bên nhãn **"Số tiền đặt cọc:"** ở góc dưới bên phải và gõ số tiền cọc muốn ứng trước cho nhà cung cấp (nếu không có thì gõ `0`).
* **Bước 7:** Nhấp chuột trái vào nút bấm **"Tạo Đơn Hàng"** màu xanh ở góc dưới bên phải cửa sổ để lưu đơn ở trạng thái **Bản Nháp** (draft).

### 1.2. Cách Điều Chỉnh Đơn Mua Hàng (Khi Đang Nháp)
* **Bước 1:** Tìm đơn mua hàng cần sửa đổi đang hiển thị Badge trạng thái màu xám là **"Nháp"** trong danh sách đơn mua hàng.
* **Bước 2:** Nhấp chọn dòng đơn hàng đó để mở cửa sổ chi tiết (tiêu đề cửa sổ hiển thị: *Chi Tiết Đơn Mua Nháp - {Mã đơn}*).
* **Bước 3:** Thay đổi thông tin nhà cung cấp, ngày giao dự kiến, hạn thanh toán, thêm bớt linh kiện hoặc sửa số lượng/đơn giá.
* **Bước 4:** Nhấp nút **"Cập Nhật"** màu xanh ở góc dưới bên phải để hoàn tất lưu lại thay đổi. *Lưu ý: Hệ thống chỉ cho phép chỉnh sửa khi đơn hàng đang ở trạng thái Nháp.*

### 1.3. Cách Phê Duyệt Đơn Mua Hàng
* **Bước 1:** Mở cửa sổ chi tiết đơn mua hàng đang ở trạng thái **"Nháp"** cần duyệt.
* **Bước 2:** Nhấp chuột trái vào nút bấm màu xanh dương có dòng chữ **"Duyệt Đơn"** (kèm hình dấu tích tròn) ở góc dưới cùng bên phải.
* **Bước 3:** Một hộp thoại xác nhận có tiêu đề **"Xác nhận duyệt đơn mua hàng"** hiện lên, kèm lời thông báo: *Bạn có chắc chắn muốn duyệt đơn mua hàng này? Hệ thống sẽ tự động tạo Hóa đơn mua hàng tương ứng.*
* **Bước 4:** Nhấp chuột vào ô chọn ngày dưới nhãn **"Hạn Thanh Toán Hóa Đơn"** trên hộp thoại và chọn hạn thanh toán cho hóa đơn (bắt buộc chọn ngày từ hôm nay trở đi).
* **Bước 5:** Nhấp chuột trái vào nút bấm **"Xác nhận duyệt"** trên hộp thoại. Đơn mua hàng sẽ được duyệt, hệ thống tự động tạo một Hóa đơn mua hàng (AP) chưa thanh toán để theo dõi chi tiền và mở khóa cho phép tạo hồ sơ tiếp nhận lô hàng tương ứng.

### 1.4. Quy Trình Quản Lý Tiếp Nhận Lô Hàng Và Phân Bổ Chi Phí Vận Chuyển (Landed Cost)
Khi linh kiện được vận chuyển về đến công ty, quy trình nhận hàng vào kho và ghi nhận chi phí vận chuyển đi kèm (Landed Cost) được thực hiện tập trung tại tab **"Quản Lý Lô Hàng"** như sau:

#### A. Tạo Lô Hàng Mới (Mã Lô Hàng Để Tiếp Nhận)
* **Bước 1:** Tại trang Mua Hàng, nhấp chọn tab **"Quản Lý Lô Hàng"** ở đầu trang.
* **Bước 2:** Ở cột bên trái có tiêu đề **"Hồ sơ Lô hàng"**, nhấp chuột trái vào nút bấm **"Tạo Lô Hàng"**. Một hộp thoại **"Tạo Lô Hàng Mới"** hiện ra ở giữa màn hình.
* **Bước 3:** Hệ thống sẽ tự động gõ một mã lô hàng ngẫu nhiên vào ô **"Mã lô hàng"** (ví dụ: `LH-20260629-5482`). Bạn nên giữ nguyên mã này.
* **Bước 4:** Nhấp chọn ô chọn dưới nhãn **"Đơn mua hàng"** (phía dưới có dòng chữ mờ *Chọn đơn mua hàng*). Một danh sách các đơn mua hàng đã duyệt và chưa có lô hàng đang xử lý hiện ra. Nhấp chọn đúng đơn mua liên kết với chuyến hàng này.
* **Bước 5:** Ô **"Tên lô hàng"** sẽ tự động hiển thị gợi ý theo tên nhà cung cấp và ngày hôm nay (ví dụ: `Lô hàng Tổng Công ty Thiết bị Điện tử miền Bắc - 29/06/2026`). Bạn có thể sửa đổi nếu cần.
* **Bước 6:** Gõ ghi chú vào ô **"Ghi chú"** (nếu có).
* **Bước 7:** Nhấp chuột trái vào nút **"Tạo mới"** ở góc dưới cùng bên phải hộp thoại để hoàn tất. Lô hàng mới tạo sẽ hiển thị ở danh sách bên trái dưới trạng thái màu xám chữ **"Chờ Hàng Về"** (draft).

#### B. Xác Nhận Hàng Về (Bắt Đầu Tiếp Nhận)
* **Bước 1:** Nhấp chọn lô hàng vừa tạo trong danh sách ở cột trái.
* **Bước 2:** Tại bảng chi tiết hiện ra ở cột phải, nhấp chuột trái vào nút bấm màu xanh dương **"Xác nhận hàng về (Bắt đầu tiếp nhận)"** ở góc trên bên phải. Trạng thái của lô hàng sẽ chuyển sang màu xanh dương chữ **"Đang Tiếp Nhận"** (inspecting).

#### C. Điền Số Lượng Thực Nhận, Chọn Kho Nhận Và Khai Báo Chi Phí Vận Chuyển
* **Bước 1:** Nhấp chọn lô hàng đang ở trạng thái **"Đang Tiếp Nhận"** (inspecting) trong danh sách.
* **Bước 2:** Nhấp chuột vào ô nhập dưới nhãn **"Chi phí Logistic / Vận chuyển ước tính (VND) *"** ở giữa màn hình và gõ giá trị chi phí vận chuyển ước tính của lô hàng này (ví dụ: gõ `1.500.000` đồng). Nếu lô hàng không phát sinh chi phí vận chuyển, hãy gõ `0`.
* **Bước 3:** Nhìn xuống bảng **"Bảng Tiếp Nhận Hàng Hóa"** ở bên dưới. Đối với từng dòng linh kiện trong đơn hàng, hãy thực hiện:
  - Nhập số lượng linh kiện thực tế nhận được đợt này vào ô trống dưới cột **"Số lượng nhận"**.
  - *Nếu số lượng nhận lớn hơn 0:* Bắt buộc phải nhấp chuột vào ô dropdown dưới cột **"Kho đích"** bên cạnh và chọn kho muốn chứa linh kiện này (hệ thống mặc định chọn sẵn *"Kho Nguyên Vật Liệu"*).
  - *Nếu số lượng nhận bằng 0:* Biểu thị việc từ chối nhận mặt hàng này trong lô hàng. Bạn không cần chọn kho đích.
  - *Lưu ý:* Hệ thống sẽ báo lỗi đỏ ngay lập tức nếu số lượng nhận bạn gõ lớn hơn số lượng còn lại hiển thị ở cột bên cạnh.
* **Bước 4:** Nhìn lên góc trên bên phải, nhấp chuột trái vào nút bấm **"Xác Nhận Hoàn Tất"** (có hình chiếc bảng kẹp dấu kiểm).
  - *Nếu tất cả số lượng nhận của các mặt hàng bạn gõ đều bằng 0:* Một hộp thoại **"Xác nhận từ chối nhận toàn bộ hàng"** hiện lên, hãy nhấp chọn nút đồng ý để tiếp tục.
  - Sau khi xác nhận hoàn tất, hệ thống tự động xử lý dựa trên chi phí vận chuyển bạn đã khai báo:
    - **Nếu chi phí vận chuyển lớn hơn 0:** Lô hàng chuyển sang trạng thái màu vàng chữ **"Chờ Duyệt Chi Phí"** (pending_approval) và tự động tạo một giao dịch chi tiền dòng tiền logistics tạm giữ ở trạng thái Chờ duyệt. Kế toán/CFO sẽ vào duyệt dòng tiền này. Sau khi giao dịch này được duyệt, lô hàng mới chính thức chuyển sang trạng thái màu xanh lá chữ **"Hoàn Tất"** (completed), hệ thống tự động tạo và phê duyệt (posted) phiếu nhập kho thực tế để tăng tồn kho và cập nhật tiến độ nhận hàng của đơn mua ban đầu.
    - **Nếu chi phí vận chuyển bằng 0:** Lô hàng chuyển thẳng sang trạng thái màu xanh lá chữ **"Hoàn Tất"** (completed) ngay lập tức mà không cần qua bước duyệt dòng tiền, đồng thời tự động tạo và phê duyệt phiếu nhập kho để tăng tồn kho thực tế.

#### D. Gửi Duyệt Lại Chi Phí Khi Bị Kế Toán Từ Chối
* **Bước 1:** Nếu Kế toán từ chối giao dịch dòng tiền chi phí vận chuyển, lô hàng sẽ bị trả lại trạng thái **"Đang Tiếp Nhận"** (inspecting) và hiển thị một hộp màu đỏ cảnh báo: *"Yêu cầu duyệt chi phí vận chuyển trước đó bị từ chối: [Lý do từ chối]"*.
* **Bước 2:** Nhấp chuột vào ô **"Chi Phí Logistic / Vận chuyển ước tính (VND) *"** để chỉnh sửa lại số tiền chi phí vận chuyển chính xác theo phản hồi của kế toán.
* **Bước 3:** Nhấp chuột trái vào nút bấm màu xanh dương **"Gửi duyệt lại chi phí"** ở góc trên bên phải để gửi lại yêu cầu duyệt cho kế toán.

### 1.5. Cách Hủy Đơn Mua Hàng
* **Bước 1:** Tìm đơn mua hàng muốn hủy trong danh sách đơn mua hàng.
* **Bước 2:** Mở cửa sổ chi tiết đơn mua hàng đó, nhấp chọn nút bấm **"Hủy Đơn"** màu đỏ ở góc dưới bên trái.
* **Bước 3:** Hệ thống tự động nhận diện tình trạng thực tế để hiển thị hộp thoại xác nhận phù hợp:
  - *Trường hợp chưa nhập kho:* Hộp thoại **"Xác Nhận Hủy Đơn Mua Hàng"** hiển thị dòng chữ *Trạng thái: Chưa nhập kho*. Nếu đơn hàng có đặt cọc, bạn sẽ thấy checkbox **"Nhận lại tiền đặt cọc (Tự động tạo phiếu thu hoàn tiền cọc)"**. Tích chọn nếu muốn hoàn trả cọc trên hệ thống tài chính, hoặc bỏ tích nếu không hoàn tiền. Bấm **"Xác nhận hủy"** màu đỏ.
  - *Trường hợp đã nhập kho:* Hộp thoại **"Xác Nhận Hủy Đơn Mua Hàng"** hiển thị dòng chữ *Trạng thái: Đã nhập hàng thực tế*. Bạn sẽ thấy checkbox **"Giữ lại phần hàng đã nhận (Cân đối công nợ và tiền trả)"**:
    - **Nếu tích chọn:** Hệ thống giữ nguyên các phiếu nhập kho đã ghi sổ, tự động tính chênh lệch giá trị hàng đã nhận với số tiền đã trả để sinh phiếu thu/chi cân đối quỹ tiền.
    - **Nếu bỏ tích chọn:** Hệ thống hiện cảnh báo đỏ *Trả hàng toàn bộ!*. Khi bạn bấm **"Xác nhận hủy"**, hệ thống tự sinh phiếu xuất kho trả lại toàn bộ số hàng đã nhận và tự sinh phiếu thu đối ứng để hoàn trả toàn bộ số tiền đã thanh toán.

---

## 2. Quy Trình Quản Lý Bán Hàng (Sales)

Để bắt đầu làm việc, hãy tìm ở menu cột bên trái màn hình và nhấp chuột trái vào dòng chữ **"Bán Hàng"**.

### 2.1. Cách Tạo Đơn Bán Hàng Mới (Lưu Nháp)
* **Bước 1:** Ở góc trên cùng bên phải màn hình, nhấp chuột trái vào nút bấm màu xanh dương có dòng chữ **"Thêm Đơn Bán"** (kèm hình dấu cộng). Một ô cửa sổ lớn có tiêu đề **"Thêm Đơn Bán Hàng Mới"** sẽ hiện ra.
* **Bước 2:** Nhấp chọn khách hàng tại ô chọn dưới nhãn **"Khách Hàng"** và chọn hạn thanh toán tại ô **"Hạn Thanh Toán"**.
* **Bước 3:** Khai báo danh sách các sản phẩm bán ở phần **"Danh Sách Sản Phẩm"**:
  - Nhấp nút **"Thêm"** (dấu cộng nhỏ) để tạo dòng mới.
  - Tại cột **"Sản Phẩm"**, chọn sản phẩm thành phẩm bán đi.
  - Tại cột **"Số Lượng"**, nhập số lượng bán.
  - Tại cột **"Đơn Giá"**, nhập giá bán đã thỏa thuận cho một sản phẩm.
* **Bước 4:** Nhập số tiền đặt cọc vào ô **"Số tiền đặt cọc:"** (nếu khách hàng có trả trước).
* **Bước 5:** Nhấp nút **"Tạo Đơn Hàng"** ở góc dưới cùng bên phải để lưu đơn ở trạng thái **Bản Nháp** (draft).

### 2.2. Cách Điều Chỉnh Đơn Bán Hàng (Khi Đang Nháp)
* **Bước 1:** Tìm đơn bán hàng cần sửa đổi đang hiển thị Badge trạng thái màu xám là **"Nháp"** trong danh sách.
* **Bước 2:** Nhấp chọn dòng đơn hàng đó để mở cửa sổ chi tiết (tiêu đề cửa sổ hiển thị: *Chi Tiết Đơn Bán Nháp - {Mã đơn}*).
* **Bước 3:** Thay đổi thông tin khách hàng, hạn thanh toán, thêm bớt sản phẩm hoặc sửa số lượng/đơn giá.
* **Bước 4:** Nhấp nút **"Cập Nhật"** màu xanh ở góc dưới bên phải để hoàn tất lưu lại thay đổi. *Lưu ý: Hệ thống chỉ cho phép chỉnh sửa khi đơn hàng đang ở trạng thái Nháp.*

### 2.3. Cách Phê Duyệt Đơn Bán Hàng (Và Duyệt Tín Dụng Đặc Cách)
* **Bước 1:** Mở chi tiết đơn bán hàng đang ở trạng thái **"Nháp"** cần duyệt.
* **Bước 2:** Nhấp chuột trái vào nút bấm màu xanh dương có dòng chữ **"Duyệt Đơn"** ở góc dưới bên phải.
* **Bước 3:** Hệ thống sẽ tự động đối chiếu thông tin công nợ của khách hàng:
  - *Trường hợp khách hàng bị quá hạn mức nợ hoặc có nợ quá hạn trên 30 ngày:* Đơn hàng sẽ bị tự động khóa và chuyển sang trạng thái màu vàng **"Chờ duyệt tín dụng"** (pending_credit_approval). Đầu cửa sổ hiển thị một Banner cảnh báo đỏ có tiêu đề **"Đơn hàng bị Khóa Tín Dụng"**. Một người quản lý có thẩm quyền phải mở đơn ra, nhấp chọn nút bấm **"Duyệt tín dụng đặc cách"** ở góc dưới cùng bên phải để phê duyệt đơn hàng.
  - *Trường hợp bình thường:* Đơn hàng được phê duyệt thành công. Hệ thống tự động tạo một Phiếu xuất kho bản nháp để chuẩn bị giao hàng và một Hóa đơn bán hàng chưa thanh toán để kế toán theo dõi thu tiền.

### 2.4. Cách Hủy Đơn Bán Hàng
* **Bước 1:** Mở đơn bán hàng cần hủy trong danh sách.
* **Bước 2:** Nhấp chọn nút bấm **"Hủy Đơn"** màu đỏ ở góc dưới bên trái.
* **Bước 3:** Hộp thoại xác nhận có tiêu đề **"Xác nhận hủy"** hiện ra hỏi lại: *Bạn có chắc chắn muốn hủy đơn hàng này?*. Nhấp chọn nút xác nhận để hoàn tất. Trạng thái đơn bán hàng sẽ chuyển thành màu đỏ là **"Đã hủy"** (cancelled).

---

## 3. Quy Trình Quản Lý Đối Tác (Khách Hàng / Nhà Cung Cấp)

Hãy nhìn vào danh mục menu ở cột bên trái màn hình để lựa chọn:
* Nếu muốn quản lý khách hàng: Nhấp chuột trái vào dòng chữ **"Khách Hàng"**.
* Nếu muốn quản lý nhà cung cấp: Nhấp chuột trái vào dòng chữ **"Nhà Cung Cấp"**.

### 3.1. Cách Thêm Mới Đối Tác
* **Bước 1:** Tại góc trên cùng bên phải màn hình, nhấp chuột trái vào nút bấm màu xanh dương có dòng chữ:
  - **"Thêm Khách Hàng"** (nếu ở trang Khách Hàng) -> hộp thoại **"Thêm Khách Hàng Mới"** hiện ra.
  - **"Thêm Nhà Cung Cấp"** (nếu ở trang Nhà Cung Cấp) -> hộp thoại **"Thêm Nhà Cung Cấp Mới"** hiện ra.
* **Bước 2:** Nhập đầy đủ các thông tin của đối tác:
  - Đối với Khách Hàng: Nhập **"Mã Khách Hàng"** (VD: `CUS-001`), chọn **"Nhóm Khách Hàng"** (Doanh Nghiệp / Cá Nhân / Chính Phủ), nhập **"Tên Khách Hàng"**, email, điện thoại, địa chỉ, **"Hạn Mức Tín Dụng (VND)"**, **"Điều Khoản Thanh Toán"** (NET15 / NET30 / NET45 / NET60), tích chọn **"Khóa tín dụng (Chặn tạo đơn hàng mới ngay lập tức)"** nếu cần.
  - Đối với Nhà Cung Cấp: Nhập **"Mã Nhà Cung Cấp"** (VD: `SUP-001`), chọn **"Nhóm Nhà Cung Cấp"** (Nhà Sản Xuất / Nhà Phân Phối / Đơn Vị Dịch Vụ), nhập **"Tên Nhà Cung Cấp"**, email, điện thoại, địa chỉ.
* **Bước 3:** Nhấp chuột trái vào nút bấm **"Lưu Lại"** ở góc dưới bên phải để hoàn tất.

### 3.2. Cách Điều Chỉnh Thông Tin Đối Tác
* **Bước 1:** Tìm đối tác bạn cần chỉnh sửa trong bảng danh sách hiển thị trên màn hình.
* **Bước 2:** Di chuyển chuột đến cuối dòng đó, nhấp chuột trái vào nút bấm có biểu tượng hình chiếc bút chì để mở cửa sổ chỉnh sửa (tiêu đề hiển thị *Chỉnh Sửa Thông Tin Khách Hàng* hoặc *Chỉnh Sửa Thông Tin Nhà Cung Cấp*).
* **Bước 3:** Thay đổi tên, số điện thoại, địa chỉ, nhóm đối tác hoặc điều chỉnh lại hạn mức công nợ của đối tác. *Lưu ý: Mã đối tác được hiển thị cố định và không thể chỉnh sửa.*
* **Bước 4:** Nhấp chuột trái vào nút **"Cập Nhật"** ở góc dưới cùng bên phải cửa sổ.

### 3.3. Cách Xóa Đối Tác Khỏi Hệ Thống
* **Bước 1:** Tìm đối tác bạn muốn xóa trong bảng danh sách hiển thị trên màn hình.
* **Bước 2:** Di chuyển chuột đến cuối dòng đó, nhấp chuột trái vào nút bấm có biểu tượng hình thùng rác màu đỏ.
* **Bước 3:** Hệ thống sẽ tự động rà soát lịch sử giao dịch:
  - *Nếu đối tác đã từng phát sinh đơn hàng, hóa đơn hoặc giao dịch thanh toán:* Hệ thống sẽ tự động hiện thông báo lỗi và chặn thao tác xóa để bảo vệ tính chính xác của dữ liệu.
  - *Nếu đối tác chưa từng phát sinh giao dịch nào:* Một hộp thoại xác nhận có tiêu đề **"Xác nhận xóa khách hàng"** hoặc **"Xác nhận xóa nhà cung cấp"** hiện ra hỏi lại. Nhấp chọn nút **"Xóa"** (hoặc nút Đồng ý) để hoàn tất xóa đối tác khỏi hệ thống.
