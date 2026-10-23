# DataCore A2A — MCP server

<!-- mcp-name: vn.datacore/datacore-a2a -->
<!-- Marker dự phòng: registry tìm chuỗi con, nên hai dòng cùng tồn tại được.
     Giữ đường lùi nếu xác minh tên miền không xong, khỏi phải phát hành
     một version mới chỉ để sửa một dòng comment.
     mcp-name: io.github.nambn3tit/datacore-a2a-mcp -->

Cho phép một MCP client (Claude Code, Claude Desktop, VS Code, Cursor…) dùng
các skill dữ liệu của DataCore như tool native: chuẩn hoá địa chỉ Việt Nam,
kiểm tra địa chỉ, tra cứu doanh nghiệp, sinh embedding.

```
MCP client (stdio) ──► datacore-mcp ──HTTPS──► DataCore API
```

Zero dependency, Python 3.9+.

## Bắt đầu

Server này là **client**, không phải dịch vụ. Nó cần một endpoint DataCore và
một API key để gọi. Thiếu một trong hai thì nó khởi động rồi thoát ngay, kèm
thông báo thiếu biến nào.

Cần một tài khoản trên [datacore.vn](https://datacore.vn) trước.

### 1. Cài

```bash
pip install git+https://github.com/DataCore-VietNam/datacore-a2a-mcp.git
```

> Bản PyPI đang trên đường. Khi có, lệnh sẽ là `pip install datacore-a2a-mcp`.
> Ai cài từ GitHub thì lúc đó cần gỡ rồi cài lại — `--upgrade` không tự chuyển
> nguồn.

### 2. Lấy token

```bash
curl -s -X POST https://gateway.datacore.vn/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"<user>","password":"<pass>"}' | jq -r '.data.token'
```

Chuỗi 64 ký tự. Phản hồi còn có `.data.jwt` — **không dùng cái đó**.

### 3. Tạo credential

```bash
curl -s -X POST https://gateway.datacore.vn/mcp/credentials \
  -H "token: <token 64 ky tu>" \
  -H 'Content-Type: application/json' \
  -d '{"name":"claude-code"}' | jq .
```

Chép lại `api_key` ngay — nó **chỉ hiện đúng một lần**. Dịch vụ chỉ lưu bản băm,
không có cách nào đọc lại. Mất thì tạo cái mới.

### 4. Khai báo — xem [Cấu hình](#cấu-hình) bên dưới

Chưa có giao diện web cho bước 2–3; làm bằng `curl` như trên. Khi có trang quản
lý, các lệnh này vẫn chạy.

## Hạn mức

| | |
|---|---|
| Gói miễn phí | ~1.000 lượt gọi mỗi tháng, reset đầu tháng (giờ Việt Nam) |
| Số credential | tối đa 3 mỗi tài khoản |
| Hạn credential | 90 ngày |

Xem đã dùng bao nhiêu, và thu hồi:

```bash
curl -s  https://gateway.datacore.vn/mcp/credentials/<id>/usage -H "token: <token>" | jq .
curl -X DELETE https://gateway.datacore.vn/mcp/credentials/<id> -H "token: <token>"
```

## Cấu hình

| Biến | Bắt buộc | Ý nghĩa |
|---|---|---|
| `DATACORE_A2A_URL` | có | Base URL gateway DataCore — `https://gateway.datacore.vn`, trừ khi bạn được cấp endpoint riêng |
| `DATACORE_API_KEY` | có¹ | Credential dài hạn dạng `dck_...`. Server tự đổi nó lấy mandate ngắn hạn và tự gia hạn |
| `DATACORE_MANDATE` | có¹ | Mandate AP2 phát tay. Chỉ dùng nếu bạn được cấp theo cách cũ — xem ghi chú bên dưới |
| `DATACORE_SKILLS` | không | Danh sách skill id cách nhau bằng phẩy để giới hạn tool, hoặc `*` để lấy hết. Bỏ trống dùng mặc định |
| `DATACORE_TIMEOUT` | không | Timeout mỗi request (giây), mặc định `30` |

¹ Cần **một trong hai**. Có cả hai thì `DATACORE_MANDATE` được ưu tiên.

Dùng đúng URL DataCore cấp. Một endpoint khác sẽ không nhận credential của bạn
và trả `401`.

### Vì sao nên dùng `DATACORE_API_KEY`

Mandate chỉ sống vài phút. Với `DATACORE_API_KEY`, server tự xin mandate mới
trước khi cái đang giữ hết hạn, nên bạn **không bao giờ phải sửa file cấu hình
vì token hết hạn**. Mandate chỉ nằm trong bộ nhớ tiến trình và không bao giờ
được ghi ra đâu cả.

`DATACORE_MANDATE` vẫn dùng được và không bị tự gia hạn — giữ lại cho những ai
đã cấu hình theo cách cũ. Hết hạn là phải tự thay rồi khởi động lại MCP server.

### Claude Code / Claude Desktop

Thêm vào `.mcp.json` (project) hoặc config của Claude Desktop:

```json
{
  "mcpServers": {
    "datacore-a2a": {
      "command": "datacore-mcp",
      "env": {
        "DATACORE_A2A_URL": "https://gateway.datacore.vn",
        "DATACORE_API_KEY": "dck_<prefix>_<secret>"
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

Server này mang mandate **nguyên dạng** ở header `X-AP2-Mandate` để phía
DataCore verify, và không tự khai bất kỳ header authorization nào khác. Một
client không được là nơi tự cấp quyền cho chính nó — nó chỉ chuyển tiếp thứ nó
được cấp, còn mọi quyết định cho phép hay từ chối đều nằm ở phía DataCore.

API key đi trong `X-Datacore-Credential` khi đổi lấy mandate, **không phải**
`Authorization`. Gateway của DataCore dành riêng `Authorization` cho chính nó —
nó tự ký và tự chèn header đó sau khi xác thực người gọi — nên request nào gửi
sẵn `Authorization` bị trả 409 với body rỗng. Nếu bạn gọi `/mandate/issue`
bằng tay và nhận 409 không có thông báo gì, đó là lý do.

**API key** là bearer credential: ai giữ nó cũng đổi được ra mandate, và từ đó
gọi được đúng những skill trong đó tới hết hạn mức. Giữ nó như giữ mật khẩu —
đừng commit `.mcp.json` đã điền key, và nếu client của bạn hỗ trợ, đọc nó từ
trình quản lý secret thay vì để inline. Lỡ lộ thì **thu hồi ngay** bằng
`DELETE /mcp/credentials/<id>` (xem [Hạn mức](#hạn-mức)); mandate đã phát ra từ
nó vẫn chạy nốt vài phút còn lại rồi chết — không có danh sách thu hồi tức thì.

Mandate thì ngược lại: nó chỉ sống vài phút và chỉ nằm trong bộ nhớ tiến trình.
Nó không được ghi ra đĩa, không vào log, và bạn không cần nhìn thấy nó bao giờ.

**Package này** không bao giờ ghi token ra log, kể cả một phần; nội dung `text`
bạn gửi cũng không. Đó là cam kết cho tiến trình chạy trên máy bạn — phía dịch
vụ là chuyện khác, và [PRIVACY.md](PRIVACY.md) nói thẳng nó lưu những gì.

## Xử lý sự cố

Log đi ra **stderr**, prefix `[datacore-mcp]`. stdout là kênh JSON-RPC.

| Triệu chứng | Nguyên nhân thường gặp |
|---|---|
| Server thoát ngay, `THIẾU biến môi trường bắt buộc` | Chưa set `DATACORE_A2A_URL` |
| Server thoát ngay, `THIẾU xác thực` | Chưa set `DATACORE_API_KEY` (hoặc `DATACORE_MANDATE`) |
| `401` mọi request | Credential bị thu hồi, hoặc **đã quá 90 ngày**, hoặc `DATACORE_A2A_URL` không phải endpoint đã cấp credential đó. Dùng `DATACORE_MANDATE`: mandate hết hạn và nó **không tự gia hạn**. Một thông báo duy nhất cho cả ba — cố ý, để endpoint không thành công cụ dò key. Cách phân biệt: gọi `GET /mcp/credentials` xem credential còn `ACTIVE` không |
| `409` khi tự gọi `/mandate/issue` | Bạn gửi key trong `Authorization`. Phải là `X-Datacore-Credential` — xem [Mô hình bảo mật](#mô-hình-bảo-mật). Package tự làm đúng; lỗi này chỉ gặp khi gọi tay |
| `402` | Đã dùng hết hạn mức của tháng này. Hạn mức tự reset đầu tháng sau |
| `403` | Skill nằm ngoài allowlist của credential — tạo credential mới có skill đó |
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
