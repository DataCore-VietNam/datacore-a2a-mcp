# DataCore A2A — MCP server

[English](README.md) · **Tiếng Việt**

> Bản tiếng Việt. Tài liệu chính thức là [README.md](README.md) — đó cũng là nội
> dung hiển thị trên PyPI. Sửa một bên thì sửa cả hai.

Cho phép một MCP client (Claude Code, Claude Desktop, VS Code, Cursor…) dùng các
skill dữ liệu của DataCore như tool native: chuẩn hoá địa chỉ Việt Nam, kiểm tra
địa chỉ, tra cứu doanh nghiệp, sinh embedding.

```
MCP client (stdio) ──► datacore-mcp ──HTTPS──► DataCore gateway
```

Zero dependency, Python 3.9+.

## Bắt đầu

Server này là **client**, không phải dịch vụ. Nó cần một endpoint DataCore và một
credential để gọi. Thiếu một trong hai thì nó khởi động, báo thiếu biến nào, rồi
thoát ngay.

Cần một tài khoản trên [datacore.vn](https://datacore.vn) trước.

### 1. Cài

```bash
pip install datacore-a2a-mcp
```

> Nếu trước đây bạn đã cài từ GitHub lúc package chưa phát hành, `--upgrade` sẽ
> không tự chuyển sang bản PyPI — gỡ ra rồi cài lại.

### 2. Lấy token

Đăng nhập [datacore.vn](https://datacore.vn), rồi chép header `token` của một
request bất kỳ tới `gateway.datacore.vn` (DevTools → Network). Hex 64 ký tự.

Không có bản `curl`: `POST /auth/login` giải mã RSA password, và không endpoint
nào phát khoá công khai — chỉ web app đăng nhập được. Trang quản lý credential
sẽ bỏ bước này.

Bỏ qua `jwt` cùng lần đăng nhập — gateway trả `409` cho `Authorization` do
client gửi; `token` mới là header nó nhận.

### 3. Tạo credential

```bash
curl -s -X POST https://gateway.datacore.vn/mcp/credentials \
  -H "token: <token 64 ky tu>" \
  -H 'Content-Type: application/json' \
  -d '{"name":"claude-code"}' | jq .
```

`201` kèm credential, gồm `api_key`, `key_prefix`, `allowed_skills`,
`spend_cap_vnd` và `quota_period`.

Chép lại `api_key` ngay — nó chỉ hiện **đúng một lần**. Dịch vụ chỉ lưu bản băm,
không có cách nào đọc lại. Mất thì tạo cái mới.

Gặp `409` ở bước này nghĩa là bạn đang giữ đủ 3 credential còn hiệu lực. Thu hồi
bớt một cái trước — xem [Hạn mức](#hạn-mức).

### 4. Khai báo ở client — xem [Cấu hình](#cấu-hình)

Chưa có giao diện web cho bước 2–3; làm bằng `curl` như trên. Khi có trang quản
lý, các lệnh này vẫn chạy.

## Hạn mức

| | |
|---|---|
| Số request | 1.000 mỗi tài khoản trong cửa sổ trượt 30 ngày |
| Thế nào là một lượt | mỗi lần gọi tới được skill và nhận được câu trả lời |
| Số credential | tối đa 3 cái còn hiệu lực mỗi tài khoản |
| Hạn credential | 90 ngày |
| Tần suất đổi mandate | tối đa 10 lần mỗi phút cho mỗi credential |

Hạn mức thuộc về **tài khoản**, không thuộc credential: mọi key bạn giữ và Claude
Connect dùng chung 1.000 lượt đó. Thu hồi key hay tạo key mới đều không làm mới
hạn mức. Cửa sổ trượt nên không có ngày reset — một lượt được trả lại đúng 30
ngày sau lúc gọi.

Gọi mà không tìm thấy gì (không có công ty khớp chẳng hạn) vẫn tính một lượt: việc
đã được làm. Gọi hỏng vì DataCore không tới được hệ thống phía sau thì không tính,
và gọi bị từ chối trước khi chạy (skill không được phép, mandate sai, đã hết hạn
mức) cũng không tính.

Quá hạn mức, lượt gọi nhận `429` với
`QUOTA_EXCEEDED: Used 1000 of 1000 requests in the last 30 days; next slot at <thời điểm>`
và header `Retry-After` tính bằng giây.

Credential không gắn với máy hay IP, nên cùng một key dùng được từ máy khác — và
thu hồi một lần là chết cả hai.

Xem đã dùng bao nhiêu, liệt kê key, và thu hồi:

```bash
curl -s https://gateway.datacore.vn/mcp/credentials/usage -H "token: <token>" | jq .
curl -s https://gateway.datacore.vn/mcp/credentials -H "token: <token>" | jq .
curl -X DELETE https://gateway.datacore.vn/mcp/credentials/<id> -H "token: <token>"
```

`/mcp/credentials/usage` trả về `used`, `limit`, `remaining`, `window_days`,
`oldest_counted_at` và `next_slot_at` — lúc lượt kế tiếp được trả lại. Danh sách
key có `requests_30d` cho từng key. Thu hồi trả `204`, và `404` nếu id không phải
của bạn — hai trường hợp cố ý không phân biệt được.

## Cấu hình

| Biến | Bắt buộc | Ý nghĩa |
|---|---|---|
| `DATACORE_A2A_URL` | có | Base URL gateway DataCore — `https://gateway.datacore.vn`, trừ khi bạn được cấp endpoint riêng |
| `DATACORE_API_KEY` | có¹ | Credential dài hạn dạng `dck_<prefix>_<secret>`. Server tự đổi nó lấy mandate ngắn hạn và tự gia hạn |
| `DATACORE_MANDATE` | có¹ | Mandate AP2 phát tay. Chỉ dùng nếu bạn được cấp theo cách cũ — xem ghi chú bên dưới |
| `DATACORE_SKILLS` | không | Danh sách skill id cách nhau bằng phẩy để thu hẹp tool, hoặc `*` để lấy hết những gì endpoint trả về. Bỏ trống thì liệt kê mọi skill credential của bạn được phép gọi |
| `DATACORE_TIMEOUT` | không | Timeout mỗi request (giây), mặc định `30` |

¹ Cần **một trong hai**. Có cả hai thì `DATACORE_MANDATE` được ưu tiên.

Dùng đúng URL DataCore cấp. Một endpoint khác sẽ không nhận credential của bạn và
trả `401`.

### Vì sao nên dùng `DATACORE_API_KEY`

Mandate sống 15 phút. Với `DATACORE_API_KEY`, server tự xin mandate mới trước khi
cái đang giữ hết hạn một phút, nên bạn **không bao giờ phải sửa file cấu hình vì
token hết hạn**. Mandate chỉ nằm trong bộ nhớ tiến trình và không được ghi ra đâu
cả. Nếu một lời gọi vẫn trả `401`, server ép làm mới mandate rồi thử lại đúng một
lần trước khi báo lỗi.

`DATACORE_MANDATE` vẫn dùng được và không bao giờ được gia hạn — giữ lại cho
những ai đã cấu hình từ trước khi có credential. Hết hạn là phải tự thay rồi khởi
động lại MCP server.

### Claude Code

```bash
claude mcp add datacore-a2a -s user \
  -e DATACORE_A2A_URL=https://gateway.datacore.vn \
  -e DATACORE_API_KEY=<API_KEY_CUA_BAN> \
  -- datacore-mcp
```

Thay `<API_KEY_CUA_BAN>` bằng `api_key` lấy ở bước 3 — dạng
`dck_<8 ký tự hex>_<secret>`.

`-s user` đăng ký cho mọi project. Nên dùng cách này thay vì `.mcp.json` phạm vi
project: file đó hay bị commit, mà key là bearer credential sống 90 ngày.

### Claude Desktop

Merge khối dưới vào config — đừng ghi đè cả file, trong đó còn preferences của
app.

| OS | Đường dẫn config |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

```json
{
  "mcpServers": {
    "datacore-a2a": {
      "command": "<DUONG_DAN_TOI_DATACORE_MCP>",
      "env": {
        "DATACORE_A2A_URL": "https://gateway.datacore.vn",
        "DATACORE_API_KEY": "<API_KEY_CUA_BAN>"
      }
    }
  }
}
```

Hai giá trị `<...>` là của bạn, phải tự điền — JSON không có comment nên trong
file sẽ không còn gì nhắc:

| Chỗ phải thay | Lấy ở đâu |
|---|---|
| `<DUONG_DAN_TOI_DATACORE_MCP>` | `which datacore-mcp` (macOS/Linux) hoặc `where datacore-mcp` (Windows). Kiểu như `/home/ban/.local/bin/datacore-mcp` hay `C:\Users\ban\AppData\Roaming\Python\Scripts\datacore-mcp.exe` |
| `<API_KEY_CUA_BAN>` | `api_key` lấy ở bước 3, dạng `dck_<8 ký tự hex>_<secret>` |

Bắt buộc là **đường dẫn tuyệt đối**: app desktop không kế thừa `PATH` của shell,
nên để tên lệnh trần thường không khởi động được. `python -m
datacore_mcp.server` cũng chạy. Xong thì thoát hẳn app — đóng cửa sổ không đủ.

Log đi ra stderr, app giữ trong thư mục `logs/` cạnh chính file config đó.

## Tool

Tool list được **sinh từ endpoint**, không hardcode ở đây — nên khi DataCore thêm
skill, restart server là thấy tool mới.

Mặc định expose năm skill đã nối backend thật:

| Tool | Skill id | Việc nó làm |
|---|---|---|
| `address_normalize` | `address.normalize` | Chuẩn hoá địa chỉ Việt Nam thành tỉnh / huyện / xã |
| `address_validate` | `address.validate` | Kiểm tra một địa chỉ theo dữ liệu hành chính |
| `company_search` | `company.search` | Tra cứu doanh nghiệp theo tên hoặc mã số thuế |
| `company_graph` | `company.graph` | Trả về quan hệ của doanh nghiệp — người đại diện, tỉnh, ngành, và mọi thứ khác có trong đồ thị |
| `company_embeddings` | `company.embeddings` | Sinh vector embedding cho một đoạn văn bản |

Mọi tool nhận đúng một tham số bắt buộc là `text`, dạng chuỗi tự do; không nhận
thêm thuộc tính nào khác. Mọi tool là **read-only** (`readOnlyHint: true`): không
ghi, không xoá, không tạo gì, và gọi lại cùng input cho cùng kết quả.

Bảng trên không phải toàn bộ. Server liệt kê **mọi skill credential của bạn
được phép gọi** — tức `allowed_skills` trong mandate nó đang giữ — nên khi
DataCore bật thêm skill cho tier của bạn (ví dụ `dataset.list`, `dataset.query`,
`company.financial-sankey`), skill đó hiện ra sau khi restart server, bạn không
phải sửa gì. Skill endpoint có nhưng credential không được gọi thì bị bỏ ra, vì
gọi lúc nào cũng nhận `403`; đặt `DATACORE_SKILLS="*"` nếu vẫn muốn thấy chúng.

Danh sách skill được đọc lúc phát mỗi mandate, không phải lúc tạo credential,
nên credential đang dùng sẽ nhận skill mới bật trong vòng một vòng đời mandate
(tối đa 15 phút).

## Ví dụ

Ba prompt dưới đây chạy qua ba tool khác nhau:

1. **Chuẩn hoá địa chỉ** — "Chuẩn hoá địa chỉ này thành tỉnh/huyện/xã: So 1 Ly
   Thai To, Hoan Kiem, Ha Noi"
2. **Tra cứu doanh nghiệp** — "Tìm thông tin doanh nghiệp có mã số thuế
   0100109106 và cho tôi biết trạng thái hoạt động"
3. **Embedding** — "Sinh embedding cho đoạn mô tả ngành nghề này rồi cho biết
   vector có bao nhiêu chiều: bán buôn thiết bị điện tử"

## Mô hình bảo mật

Server này mang mandate **nguyên dạng** ở header `X-AP2-Mandate` để phía DataCore
verify, và không tự khai bất kỳ header authorization nào khác. Một client không
được là nơi tự cấp quyền cho chính nó — nó chỉ chuyển tiếp thứ nó được cấp, còn
mọi quyết định cho phép hay từ chối đều nằm ở phía DataCore.

API key đi trong `X-Datacore-Credential` khi đổi lấy mandate, **không phải**
`Authorization`. Gateway của DataCore dành riêng `Authorization` cho chính nó —
nó tự ký và tự chèn header đó sau khi xác thực người gọi — nên request nào gửi
sẵn `Authorization` bị trả `409` với body rỗng. Nếu bạn gọi `/mandate/issue` bằng
tay và nhận `409` không có thông báo gì, đó là lý do.

**API key** là bearer credential: ai giữ nó cũng đổi được ra mandate, và từ đó
gọi được đúng những skill trong đó tới hết hạn mức. Giữ nó như giữ mật khẩu —
đừng commit `.mcp.json` đã điền key, và nếu client của bạn hỗ trợ, đọc nó từ
trình quản lý secret thay vì để inline. Lỡ lộ thì **thu hồi ngay** bằng
`DELETE /mcp/credentials/<id>` (xem [Hạn mức](#hạn-mức)); mandate đã phát ra từ
nó vẫn chạy nốt 15 phút còn lại rồi chết — không có danh sách thu hồi tức thì.

Mandate thì ngược lại: chỉ sống 15 phút và chỉ nằm trong bộ nhớ tiến trình. Nó
không được ghi ra đĩa, không vào log, và bạn không cần nhìn thấy nó bao giờ.

Việc phát mandate bị giới hạn 10 lần mỗi phút cho mỗi credential, để endpoint
không thành công cụ dò key. Mọi kiểu từ chối — key không tồn tại, bị thu hồi, hết
hạn, hay sai phần bí mật — đều trả về cùng một thông báo `401`, cũng vì lý do đó.

**Package này** không bao giờ ghi token ra log, kể cả một phần; nội dung `text`
bạn gửi cũng không. Đó là cam kết cho tiến trình chạy trên máy bạn — phía dịch vụ
là chuyện khác, và [PRIVACY.md](PRIVACY.md) nói thẳng nó lưu những gì.

## Xử lý sự cố

Log đi ra **stderr**, prefix `[datacore-mcp]`. stdout là kênh JSON-RPC. Mọi thông
báo lúc chạy đều bằng tiếng Anh.

| Triệu chứng | Nguyên nhân thường gặp |
|---|---|
| Server thoát ngay, `MISSING required environment variable` | Chưa set `DATACORE_A2A_URL` |
| Server thoát ngay, `MISSING authentication` | Chưa set `DATACORE_API_KEY` lẫn `DATACORE_MANDATE` |
| `DATACORE_API_KEY` như không có tác dụng | Bạn đang ở bản `0.1.0`, bản ra đời trước cơ chế credential và chỉ đọc `DATACORE_MANDATE`. Nâng cấp: `pip install -U datacore-a2a-mcp` |
| `401` ở mọi request | Credential bị thu hồi, hoặc **đã quá 90 ngày**, hoặc `DATACORE_A2A_URL` không phải endpoint đã cấp credential đó. Nếu dùng `DATACORE_MANDATE`: mandate hết hạn và **không tự gia hạn**. Một thông báo duy nhất cho tất cả — cố ý, để endpoint không thành công cụ dò key. Cách phân biệt: gọi `GET /mcp/credentials` xem credential còn `ACTIVE` không |
| `409` khi tự gọi `/mandate/issue` | Bạn gửi key trong `Authorization`. Phải là `X-Datacore-Credential` — xem [Mô hình bảo mật](#mô-hình-bảo-mật). Package tự làm đúng; lỗi này chỉ gặp khi gọi tay |
| `409` khi tạo credential | Bạn đang giữ đủ 3 credential còn hiệu lực. Thu hồi bớt một cái |
| `429` (khi xin mandate) | Quá 10 lần đổi mandate trong một phút cho cùng một credential. Package chỉ xin khoảng bốn lần mỗi giờ, nên gặp mã này nghĩa là có cái gì đó đang lặp |
| `429` `QUOTA_EXCEEDED` | Tài khoản đã dùng hết 1.000 request trong 30 ngày qua — tính chung mọi key và Claude Connect. Thông báo lỗi ghi lúc nào có lượt mới; `Retry-After` cho số giây |
| `403` | Skill nằm ngoài allowlist của credential — gói miễn phí chỉ có bốn skill ở trên, và tập đó không mở rộng được |
| `400` | Request không hợp lệ, hoặc skill id chưa được đăng ký ở endpoint |
| `404` | Không có route đó — kiểm tra lại `DATACORE_A2A_URL` |
| `502` / `503` | Backend của skill đó phía DataCore không phản hồi |
| Không thấy tool nào | `DATACORE_SKILLS` lọc hết, hoặc endpoint chưa đăng ký skill nào |

## Báo lỗi bảo mật

`mcp-security@datacore.vn`. Đừng mở issue công khai cho lỗi bảo mật.

Nghi credential của mình bị lộ thì **báo ngay** — đừng đợi tới lúc nó hết hạn.
Chúng tôi cần biết để xử lý phía dịch vụ.

## Quyền riêng tư

Xem [PRIVACY.md](PRIVACY.md). Ngắn gọn: package này chạy trên máy bạn, không lưu
gì, không gửi đi đâu ngoài endpoint DataCore bạn tự cấu hình, và không bao giờ
ghi mandate token vào log.

## Giấy phép

MIT — xem [LICENSE](LICENSE).
