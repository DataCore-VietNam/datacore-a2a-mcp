# Privacy Policy — datacore-a2a-mcp

Áp dụng cho package `datacore-a2a-mcp` (MCP server). Cập nhật 2026-08-24.

## Package này là gì, về mặt dữ liệu

`datacore-a2a-mcp` là một **client chạy trên máy bạn**. Nó không phải dịch vụ do
chúng tôi vận hành, không nhận dữ liệu về phía chúng tôi, và không có backend
riêng. Nó là một tiến trình cục bộ dịch giữa MCP client của bạn (Claude Code,
Claude Desktop, VS Code…) và endpoint DataCore mà **bạn** cấu hình.

## Dữ liệu nó xử lý

| Dữ liệu | Từ đâu | Đi đâu |
|---|---|---|
| Nội dung `text` bạn (hoặc agent) đưa vào tool | MCP client | Gửi tới endpoint DataCore ở `DATACORE_A2A_URL` qua HTTPS |
| Skill id được gọi | Tên tool | Cùng request trên |
| Mandate token | `DATACORE_MANDATE` | Header `X-AP2-Mandate` của cùng request trên |
| Kết quả trả về | Endpoint DataCore | Trả lại MCP client |

Không có đích đến nào khác. Package **zero dependency** nên không có thư viện
bên thứ ba nào chạm vào dữ liệu, và không có telemetry, analytics, hay
crash-reporting nào.

## Nó lưu gì

**Không lưu gì cả.** Không file, không cache, không database, không state giữa
các lần chạy. Mọi thứ nằm trong bộ nhớ tiến trình và mất khi tiến trình dừng.

## Nó ghi log gì

Log đi ra **stderr**, nơi MCP client của bạn quyết định giữ hay bỏ:

- Lúc khởi động: base URL, timeout, danh sách skill được bật
- Lúc discovery: số tool tìm được và skill id của chúng
- Khi tool lỗi: câu lỗi đã được dịch, gồm mã HTTP và message của server

**Mandate token không bao giờ được ghi log, kể cả một phần của nó** — đây là
token cấp quyền chi tiêu, và stderr của MCP server thường được client ghi ra
file. Nội dung `text` bạn gửi cũng không được ghi log.

## Dữ liệu gửi tới DataCore thì sao

Mục trên nói về package — thứ chạy trên máy bạn. Mục này nói về **dịch vụ** ở
đầu kia `DATACORE_A2A_URL`. Hai thứ khác nhau, và cam kết của package không phủ
lên dịch vụ được, nên phần này viết riêng.

### Dịch vụ nhận gì

Mỗi lần gọi tool, dịch vụ nhận: nội dung `text` bạn gửi, skill id, mandate của
bạn (mandate id, client id, danh sách skill được phép, hạn mức chi tiêu, hạn sử
dụng), cùng những thứ mọi request HTTP đều mang — địa chỉ IP nguồn và header.

### `text` của bạn đi tới đâu

Gateway verify chữ ký mandate → orchestrator kiểm skill có nằm trong mandate
không và hạn mức còn không → chuyển cho worker agent của skill đó → worker gọi
API dữ liệu tương ứng: dữ liệu địa giới hành chính, dữ liệu doanh nghiệp, hoặc
mô hình embedding.

Các API dữ liệu đó là hệ thống riêng, không cùng một hệ thống với gateway. Nên
**nội dung `text` của bạn có rời khỏi phạm vi chúng tôi để tới bên cung cấp dữ
liệu** — đó là cách duy nhất để có câu trả lời cho truy vấn của bạn. Bên cung
cấp dữ liệu có chính sách riêng của họ.

### Dịch vụ lưu gì

| Thứ được lưu | Nội dung | Sống bao lâu |
|---|---|---|
| Bộ đếm chi tiêu | Một con số cho mỗi mandate. Không có nội dung truy vấn | Tự xoá đúng lúc mandate hết hạn |
| Bản ghi tính phí | mandate id, client id, worker, skill id, số tiền, thời điểm. Không có nội dung truy vấn | Theo hệ thống tính phí |
| Log request ở gateway | **Body request — tức `text` của bạn — body response, header, query string, IP nguồn** | Theo chính sách log của hệ thống |

Dòng thứ ba là dòng đáng đọc kỹ: gateway ghi log ở mức đầy đủ, nên **truy vấn
và kết quả của bạn được lưu lại ở phía dịch vụ, không chỉ đi ngang qua**. Nếu
định gửi dữ liệu nhạy cảm qua tool này, hãy tính trên giả định đó. Package
không hứa thay cho phần này được — nó chỉ hứa được rằng bản thân nó không lưu
và không ghi gì (mục trên).

### Dùng để làm gì

Phục vụ chính request đó, cộng với vận hành và tính phí: đối soát khi có sự cố,
đếm chi tiêu theo mandate, xuất hoá đơn. Không bán cho ai, và không dùng nội
dung truy vấn của bạn để huấn luyện mô hình.

### Yêu cầu xoá, hoặc khiếu nại

`mcp-security@datacore.vn`. Nói rõ mandate id hoặc client id để chúng tôi tìm
đúng bản ghi — chúng tôi không tra được theo nội dung truy vấn.

## Liên hệ

Vấn đề bảo mật hoặc quyền riêng tư: `mcp-security@datacore.vn`