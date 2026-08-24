# DataCore A2A — MCP server

<!-- mcp-name: io.github.datacore-vietnam/datacore-a2a-mcp -->

Cho phép một MCP client (Claude Code, Claude Desktop, VS Code, Cursor…) dùng
các skill dữ liệu của DataCore như tool native: chuẩn hoá địa chỉ Việt Nam,
kiểm tra địa chỉ, tra cứu doanh nghiệp, sinh embedding.

```
MCP client (stdio) ──► datacore-mcp ──HTTPS──► DataCore API
```

Zero dependency, Python 3.9+.

## Cài đặt

```bash
pip install datacore-a2a-mcp
```

## Cần có trước

Server này là **client**, không phải dịch vụ. Nó cần một endpoint DataCore và
một mandate token để gọi — liên hệ 3TIT để được cấp. Không có hai thứ đó thì
server khởi động rồi thoát ngay kèm thông báo thiếu biến nào.

## Cấu hình

| Biến | Bắt buộc | Ý nghĩa |
|---|---|---|
| `DATACORE_A2A_URL` | có | Base URL của endpoint DataCore được cấp cho bạn, ví dụ `https://api.example.com` |
| `DATACORE_MANDATE` | có | AP2 mandate token do DataCore cấp — quyết định skill nào được gọi và hạn mức chi tiêu |
| `DATACORE_SKILLS` | không | Danh sách skill id cách nhau bằng phẩy để giới hạn tool, hoặc `*` để lấy hết. Bỏ trống dùng mặc định |
| `DATACORE_TIMEOUT` | không | Timeout mỗi request (giây), mặc định `30` |

Dùng đúng URL DataCore cấp kèm mandate. Một endpoint khác sẽ không nhận mandate
của bạn và trả `401`.

### Claude Code / Claude Desktop

Thêm vào `.mcp.json` (project) hoặc config của Claude Desktop:

```json
{
  "mcpServers": {
    "datacore-a2a": {
      "command": "datacore-mcp",
      "env": {
        "DATACORE_A2A_URL": "https://api.example.com",
        "DATACORE_MANDATE": "<mandate-token>"
      }
    }
  }
}
```

## Tool

Tool list được **sinh từ endpoint**, không hardcode ở đây — nên khi DataCore
thêm skill, restart server là thấy tool mới.

Mặc định expose 4 skill đã nối backend thật:

| Tool | Skill id | Việc nó làm |
|---|---|---|
| `address_normalize` | `address.normalize` | Chuẩn hoá địa chỉ Việt Nam thành tỉnh / huyện / xã |
| `address_validate` | `address.validate` | Kiểm tra một địa chỉ có tồn tại theo dữ liệu hành chính |
| `company_search` | `company.search` | Tra cứu doanh nghiệp theo tên hoặc mã số thuế |
| `company_embeddings` | `company.embeddings` | Sinh vector embedding cho văn bản |

Mọi tool là **read-only** (`readOnlyHint: true`): không ghi, không xoá, không
tạo gì. Gọi lại cùng input cho cùng kết quả.

Ba skill khác của DataCore (`company.graph`, `company.financial-sankey`,
`company.news`) **cố ý không được expose**: chúng đang trả dữ liệu
mock/deterministic. Muốn thấy chúng để thử thì đặt `DATACORE_SKILLS="*"`, và
đừng tin kết quả.

## Ví dụ

Ba prompt dưới đây chạy qua ba tool khác nhau:

1. **Chuẩn hoá địa chỉ** — "Chuẩn hoá địa chỉ này thành tỉnh/huyện/xã: So 1 Ly
   Thai To, Hoan Kiem, Ha Noi"
2. **Tra cứu doanh nghiệp** — "Tìm thông tin doanh nghiệp có mã số thuế
   0100109106 và cho tôi biết trạng thái hoạt động"
3. **Embedding** — "Sinh embedding cho đoạn mô tả ngành nghề này rồi cho biết
   vector có bao nhiêu chiều: bán buôn thiết bị điện tử"

## Mô hình bảo mật

Server này mang mandate token **nguyên dạng** ở header `X-AP2-Mandate` để phía
DataCore verify, và không tự khai bất kỳ header authorization nào khác. Một
client không được là nơi tự cấp quyền cho chính nó — nó chỉ chuyển tiếp thứ nó
được cấp, còn mọi quyết định cho phép hay từ chối đều nằm ở phía DataCore.

Mandate là **bearer credential**: ai giữ nó cũng gọi được đúng những skill trong
đó, tới hết hạn mức, cho tới khi hết hạn. Giữ nó như giữ mật khẩu — đừng commit
`.mcp.json` đã điền token, và nếu client của bạn hỗ trợ, đọc nó từ trình quản lý
secret thay vì để inline.

**Package này** không bao giờ ghi token ra log, kể cả một phần; nội dung `text`
bạn gửi cũng không. Đó là cam kết cho tiến trình chạy trên máy bạn — phía dịch
vụ là chuyện khác, và [PRIVACY.md](PRIVACY.md) nói thẳng nó lưu những gì.

## Xử lý sự cố

Log đi ra **stderr**, prefix `[datacore-mcp]`. stdout là kênh JSON-RPC.

| Triệu chứng | Nguyên nhân thường gặp |
|---|---|
| Server thoát ngay, `THIẾU biến môi trường bắt buộc` | Chưa set `DATACORE_A2A_URL` hoặc `DATACORE_MANDATE` |
| `401` mọi request | Mandate hết hạn, hoặc `DATACORE_A2A_URL` không phải endpoint đã cấp kèm mandate đó |
| `402` | Đã dùng hết spend cap của mandate |
| `403` | Skill nằm ngoài allowlist của mandate — xin mandate có skill đó |
| `502` | Backend của skill đó phía DataCore không phản hồi |
| Không thấy tool nào | `DATACORE_SKILLS` lọc hết, hoặc endpoint chưa đăng ký skill nào |

## Báo lỗi bảo mật

`mcp-security@datacore.vn`. Đừng mở issue công khai cho lỗi bảo mật.

Nghi mandate của mình bị lộ thì **báo ngay** — đừng đợi tới lúc nó hết hạn.
Chúng tôi cần biết để xử lý phía dịch vụ.

## Quyền riêng tư

Xem [PRIVACY.md](PRIVACY.md). Ngắn gọn: package này chạy trên máy bạn, không lưu
gì, không gửi đi đâu ngoài endpoint DataCore bạn tự cấu hình, và không bao giờ
ghi mandate token vào log.

## License

MIT — xem [LICENSE](LICENSE).
