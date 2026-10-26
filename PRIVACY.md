# Privacy Policy — datacore-a2a-mcp

**English** · [Tiếng Việt](#tiếng-việt)

Applies to the `datacore-a2a-mcp` package (MCP server). Updated 2026-10-26.

## What this package is, in data terms

`datacore-a2a-mcp` is a **client that runs on your machine**. It is not a service
we operate, it receives no data on our side, and it has no backend of its own. It
is a local process that translates between your MCP client (Claude Code, Claude
Desktop, VS Code…) and the DataCore endpoint **you** configure.

## What it handles

| Data | From | To |
|---|---|---|
| The `text` you (or the agent) pass to a tool | MCP client | The DataCore endpoint at `DATACORE_A2A_URL`, over HTTPS |
| The skill id being called | The tool name | Same request |
| Mandate token | `DATACORE_MANDATE`, or minted from your credential | `X-AP2-Mandate` header on the same request |
| API key | `DATACORE_API_KEY` | `X-Datacore-Credential` header on `POST /mandate/issue`, to exchange it for a mandate |
| The result | DataCore endpoint | Back to the MCP client |

There is no other destination. The package has **zero dependencies**, so no
third-party library touches your data, and there is no telemetry, no analytics
and no crash reporting.

## What it stores

**Nothing.** No files, no cache, no database, no state between runs. Everything
lives in process memory and is gone when the process stops.

## What it logs

Logs go to **stderr**, where your MCP client decides whether to keep them:

- At startup: version, base URL, which authentication mode is in use, timeout,
  and which skills are enabled
- On discovery: how many tools were found and their skill ids
- When a mandate is renewed: how many seconds the new one is valid for
- When a tool fails: the translated error, with the HTTP status and the server's
  message

**Neither the mandate token nor the API key is ever logged, not even in part** —
both authorise spending, and an MCP server's stderr is often written to a file by
the client. The `text` you send is not logged either.

## What about the data sent to DataCore

Everything above is about the package — the part running on your machine. This
section is about the **service** at the other end of `DATACORE_A2A_URL`. They are
two different things, and the package's promises cannot cover the service, so
this is written separately.

### What the service receives

On every tool call the service receives: the `text` you sent, the skill id, your
mandate (mandate id, client id, allowed skills, spend cap, expiry), and whatever
any HTTP request carries — source IP address and headers.

### Where your `text` goes

The gateway verifies the mandate signature → the orchestrator checks the skill is
in the mandate and the cap is not spent → it hands the call to the worker agent
that owns the skill → the worker calls the corresponding data API: administrative
boundary data, company data, or an embedding model.

Those data APIs are separate systems, not the same system as the gateway. So
**your `text` does leave our perimeter and reaches the data provider** — that is
the only way your query gets an answer. Those providers have policies of their
own.

### What the service stores

| Stored | Contents | Lifetime |
|---|---|---|
| Spend counter | One number per credential per month. No query content | A Redis key named for the month; it expires at the end of that month plus 7 days |
| Billing entry | mandate id, client id, worker, skill id, amount, timestamp. No query content | Written to the orchestrator's application log and buffered in process memory until restart. There is no billing pipeline behind it yet |
| Gateway request log | **The request body — that is, your `text` — the response body, headers, query string, source IP** | Per the platform's log retention policy |

The third row is the one to read twice: the gateway logs at full fidelity, so
**your queries and their results are retained on the service side, not merely
passed through**. If you are thinking of sending sensitive data through this
tool, plan on that being true. The package cannot promise anything on behalf of
this part — it can only promise that it stores and logs nothing itself (above).

### What it is used for

Serving that request, plus operations and billing: reconciling incidents,
counting spend per credential, issuing invoices. It is not sold to anyone, and
your query content is not used to train models.

### Deletion requests, or complaints

`mcp-security@datacore.vn`. Name the mandate id or client id so we can find the
right records — we cannot search by query content.

## Contact

Security or privacy matters: `mcp-security@datacore.vn`

---

# Tiếng Việt

[English](#privacy-policy--datacore-a2a-mcp) · **Tiếng Việt**

Áp dụng cho package `datacore-a2a-mcp` (MCP server). Cập nhật 2026-10-26.

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
| Mandate token | `DATACORE_MANDATE`, hoặc do credential của bạn đổi ra | Header `X-AP2-Mandate` của cùng request trên |
| API key | `DATACORE_API_KEY` | Header `X-Datacore-Credential` của `POST /mandate/issue`, để đổi lấy mandate |
| Kết quả trả về | Endpoint DataCore | Trả lại MCP client |

Không có đích đến nào khác. Package **zero dependency** nên không có thư viện bên
thứ ba nào chạm vào dữ liệu, và không có telemetry, analytics, hay
crash-reporting nào.

## Nó lưu gì

**Không lưu gì cả.** Không file, không cache, không database, không state giữa
các lần chạy. Mọi thứ nằm trong bộ nhớ tiến trình và mất khi tiến trình dừng.

## Nó ghi log gì

Log đi ra **stderr**, nơi MCP client của bạn quyết định giữ hay bỏ:

- Lúc khởi động: version, base URL, đang xác thực bằng cách nào, timeout, danh
  sách skill được bật
- Lúc discovery: số tool tìm được và skill id của chúng
- Lúc gia hạn mandate: mandate mới còn hiệu lực bao nhiêu giây
- Khi tool lỗi: câu lỗi đã được dịch, gồm mã HTTP và message của server

**Mandate token lẫn API key đều không bao giờ được ghi log, kể cả một phần** —
cả hai đều cấp quyền chi tiêu, và stderr của MCP server thường được client ghi ra
file. Nội dung `text` bạn gửi cũng không được ghi log.

## Dữ liệu gửi tới DataCore thì sao

Mục trên nói về package — thứ chạy trên máy bạn. Mục này nói về **dịch vụ** ở đầu
kia `DATACORE_A2A_URL`. Hai thứ khác nhau, và cam kết của package không phủ lên
dịch vụ được, nên phần này viết riêng.

### Dịch vụ nhận gì

Mỗi lần gọi tool, dịch vụ nhận: nội dung `text` bạn gửi, skill id, mandate của
bạn (mandate id, client id, danh sách skill được phép, hạn mức chi tiêu, hạn sử
dụng), cùng những thứ mọi request HTTP đều mang — địa chỉ IP nguồn và header.

### `text` của bạn đi tới đâu

Gateway verify chữ ký mandate → orchestrator kiểm skill có nằm trong mandate
không và hạn mức còn không → chuyển cho worker agent của skill đó → worker gọi
API dữ liệu tương ứng: dữ liệu địa giới hành chính, dữ liệu doanh nghiệp, hoặc mô
hình embedding.

Các API dữ liệu đó là hệ thống riêng, không cùng một hệ thống với gateway. Nên
**nội dung `text` của bạn có rời khỏi phạm vi chúng tôi để tới bên cung cấp dữ
liệu** — đó là cách duy nhất để có câu trả lời cho truy vấn của bạn. Bên cung cấp
dữ liệu có chính sách riêng của họ.

### Dịch vụ lưu gì

| Thứ được lưu | Nội dung | Sống bao lâu |
|---|---|---|
| Bộ đếm chi tiêu | Một con số cho mỗi credential mỗi tháng. Không có nội dung truy vấn | Một key Redis đặt tên theo tháng; hết hạn vào cuối tháng đó cộng 7 ngày |
| Bản ghi tính phí | mandate id, client id, worker, skill id, số tiền, thời điểm. Không có nội dung truy vấn | Ghi vào log ứng dụng của orchestrator và giữ trong bộ nhớ tiến trình tới lúc restart. Phía sau chưa có hệ thống tính phí nào |
| Log request ở gateway | **Body request — tức `text` của bạn — body response, header, query string, IP nguồn** | Theo chính sách log của hệ thống |

Dòng thứ ba là dòng đáng đọc kỹ: gateway ghi log ở mức đầy đủ, nên **truy vấn và
kết quả của bạn được lưu lại ở phía dịch vụ, không chỉ đi ngang qua**. Nếu định
gửi dữ liệu nhạy cảm qua tool này, hãy tính trên giả định đó. Package không hứa
thay cho phần này được — nó chỉ hứa được rằng bản thân nó không lưu và không ghi
gì (mục trên).

### Dùng để làm gì

Phục vụ chính request đó, cộng với vận hành và tính phí: đối soát khi có sự cố,
đếm chi tiêu theo credential, xuất hoá đơn. Không bán cho ai, và không dùng nội
dung truy vấn của bạn để huấn luyện mô hình.

### Yêu cầu xoá, hoặc khiếu nại

`mcp-security@datacore.vn`. Nói rõ mandate id hoặc client id để chúng tôi tìm
đúng bản ghi — chúng tôi không tra được theo nội dung truy vấn.

## Liên hệ

Vấn đề bảo mật hoặc quyền riêng tư: `mcp-security@datacore.vn`
