# DataCore A2A — MCP server

<!-- mcp-name: vn.datacore/datacore-a2a -->
<!-- Fallback marker: the registry looks for a substring, so both lines can
     coexist. Keeps a way back if domain verification does not land, without
     publishing a new version just to fix a comment line.
     mcp-name: io.github.nambn3tit/datacore-a2a-mcp -->

**English** · [Tiếng Việt](#tiếng-việt)

Lets an MCP client (Claude Code, Claude Desktop, VS Code, Cursor…) use DataCore's
data skills as native tools: normalise Vietnamese addresses, validate an address,
look up a company, generate embeddings.

```
MCP client (stdio) ──► datacore-mcp ──HTTPS──► DataCore gateway
```

Zero dependencies, Python 3.9+.

## Quick start

This server is a **client**, not a service. It needs a DataCore endpoint and a
credential to call it with. Missing either one, it starts, says which variable is
absent, and exits.

You need an account on [datacore.vn](https://datacore.vn) first.

### 1. Install

```bash
pip install git+https://github.com/DataCore-VietNam/datacore-a2a-mcp.git
```

> **Do not use `pip install datacore-a2a-mcp` yet.** That name resolves on PyPI,
> but to version `0.1.0` — a build that predates credentials and only accepts
> `DATACORE_MANDATE`. It will ignore `DATACORE_API_KEY` entirely and fail the
> steps below. This line changes the moment `0.2.1` is published; until then,
> install from GitHub.

### 2. Get a session token

```bash
curl -s -X POST https://gateway.datacore.vn/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"<user>","password":"<pass>"}' | jq -r '.data.token'
```

An opaque string (64 characters in the deployments we have checked). The response
also carries `.data.jwt` — **do not use that one**. The gateway rejects any
request that arrives with a client-supplied `Authorization` header, so a JWT you
send yourself never reaches the service; `token` is the header it does accept.

### 3. Create a credential

```bash
curl -s -X POST https://gateway.datacore.vn/mcp/credentials \
  -H "token: <64-character token>" \
  -H 'Content-Type: application/json' \
  -d '{"name":"claude-code"}' | jq .
```

`201` with the credential, including `api_key`, `key_prefix`, `allowed_skills`,
`spend_cap_vnd` and `quota_period`.

Copy `api_key` straight away — it is returned **once**. Only a hash is stored, so
there is no way to read it back. Lose it and you create a new one.

A `409` here means you are already holding the maximum of 3 active credentials.
Revoke one first (see [Quotas and limits](#quotas-and-limits)).

### 4. Declare it in your client — see [Configuration](#configuration)

There is no web UI for steps 2–3 yet; `curl` is the way. When a management page
exists, these commands keep working.

## Quotas and limits

| | |
|---|---|
| Free tier | 500,000 VND of spend **per credential per month** |
| Price per call | 500 VND by default, so roughly 1,000 calls |
| Reset | 1st of the month, `Asia/Ho_Chi_Minh` |
| Credentials | at most 3 active per account |
| Credential lifetime | 90 days |
| Mandate issuance | at most 10 exchanges per minute per credential |

The cap is counted per credential, not per account — three credentials give an
account three separate caps. The service meters in VND rather than in calls so
that per-skill prices can be introduced later without rewriting stored caps.

Check what a credential has spent, and revoke it:

```bash
curl -s https://gateway.datacore.vn/mcp/credentials/<id>/usage -H "token: <token>" | jq .
curl -s https://gateway.datacore.vn/mcp/credentials -H "token: <token>" | jq .
curl -X DELETE https://gateway.datacore.vn/mcp/credentials/<id> -H "token: <token>"
```

`/usage` reports `spent_vnd`, `spend_cap_vnd`, `quota_period` and `resets_at`.
Revocation returns `204`, and `404` if the id is not yours — the two cases are
deliberately indistinguishable.

## Configuration

| Variable | Required | Meaning |
|---|---|---|
| `DATACORE_A2A_URL` | yes | Base URL of the DataCore gateway — `https://gateway.datacore.vn`, unless you were given your own endpoint |
| `DATACORE_API_KEY` | yes¹ | Long-lived credential, shaped `dck_<prefix>_<secret>`. The server exchanges it for short-lived mandates and refreshes them itself |
| `DATACORE_MANDATE` | yes¹ | A hand-issued AP2 mandate. Only for callers set up the old way — see below |
| `DATACORE_SKILLS` | no | Comma-separated skill ids to narrow the tool list, or `*` for everything the endpoint returns. Empty uses the default four |
| `DATACORE_TIMEOUT` | no | Per-request timeout in seconds, default `30` |

¹ **One of the two** is required. If both are set, `DATACORE_MANDATE` wins.

Use the URL DataCore gave you. A different endpoint will not recognise your
credential and answers `401`.

### Why `DATACORE_API_KEY` is the one to use

A mandate lives 15 minutes. With `DATACORE_API_KEY`, the server requests a fresh
one a minute before the current one expires, so **you never edit a config file
because a token ran out**. The mandate stays in process memory and is never
written anywhere. If a call still comes back `401`, the server forces one refresh
and retries exactly once before reporting the failure.

`DATACORE_MANDATE` still works and is never refreshed — it is there for anyone
configured before credentials existed. When it expires you replace it by hand and
restart the MCP server.

### Claude Code / Claude Desktop

Add this to `.mcp.json` (project scope) or to your Claude Desktop config:

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

## Tools

The tool list is **generated from the endpoint**, not hardcoded here — so when
DataCore adds a skill, restarting the server is enough to see a new tool.

Four skills are exposed by default, the ones wired to a real backend:

| Tool | Skill id | What it does |
|---|---|---|
| `address_normalize` | `address.normalize` | Normalises a Vietnamese address into province / district / ward |
| `address_validate` | `address.validate` | Checks an address against administrative data |
| `company_search` | `company.search` | Looks a company up by name or tax code |
| `company_embeddings` | `company.embeddings` | Generates an embedding vector for a piece of text |

Every tool takes one required argument, `text`, a free-text string; no other
properties are accepted. Every tool is **read-only** (`readOnlyHint: true`):
nothing is written, deleted or created, and the same input gives the same result.

DataCore's three other skills (`company.graph`, `company.financial-sankey`,
`company.news`) are **deliberately not exposed**: they currently return
mock/deterministic data. Setting `DATACORE_SKILLS="*"` lists them as tools, but a
free-tier credential cannot call them — its allowlist holds only the four skills
above, so every call returns `403`. Asking for extra skills when creating a
credential is not an error either; the request is silently narrowed to the four.

## Examples

Three prompts that go through three different tools:

1. **Normalise an address** — "Normalise this address into province/district/ward:
   So 1 Ly Thai To, Hoan Kiem, Ha Noi"
2. **Company lookup** — "Find the company with tax code 0100109106 and tell me
   whether it is still operating"
3. **Embedding** — "Generate an embedding for this line of business and tell me
   how many dimensions the vector has: wholesale of electronic equipment"

## Security model

This server carries the mandate **verbatim** in the `X-AP2-Mandate` header for
DataCore to verify, and declares no authorization header of its own. A client has
no business authorizing itself — it forwards what it was given, and every allow
or deny decision stays on the DataCore side.

The API key travels in `X-Datacore-Credential` when exchanged for a mandate,
**not** in `Authorization`. DataCore's gateway keeps `Authorization` for itself —
it signs and injects that header after authenticating the caller — so any request
that arrives carrying one is rejected with `409` and an empty body. If you call
`/mandate/issue` by hand and get a `409` with no message, that is why.

**The API key** is a bearer credential: whoever holds it can exchange it for a
mandate and call the skills it allows until the cap runs out. Treat it like a
password — do not commit a filled-in `.mcp.json`, and if your client supports it,
read the key from a secret manager instead of inlining it. If it leaks, **revoke
it immediately** with `DELETE /mcp/credentials/<id>` (see
[Quotas and limits](#quotas-and-limits)); mandates already issued from it keep
working for the rest of their 15 minutes — there is no instant revocation list.

The mandate is the opposite: 15 minutes of life, process memory only. It is not
written to disk, never logged, and you should never need to look at it.

Issuance is rate-limited to 10 exchanges per minute per credential, so the
endpoint cannot be used to walk the key space. Every rejection — unknown key,
revoked key, expired key, wrong secret — returns the same `401` message for the
same reason.

**This package** never logs a token, not even partially, and never logs the
`text` you send. That is a promise about the process running on your machine —
the service side is a separate matter, and [PRIVACY.md](PRIVACY.md) says plainly
what it stores.

## Troubleshooting

Logs go to **stderr**, prefixed `[datacore-mcp]`. stdout is the JSON-RPC channel.

| Symptom | Usual cause |
|---|---|
| Exits at once, `MISSING required environment variable` | `DATACORE_A2A_URL` is not set |
| Exits at once, `MISSING authentication` | Neither `DATACORE_API_KEY` nor `DATACORE_MANDATE` is set |
| `DATACORE_API_KEY` appears to be ignored | You are running `0.1.0` from PyPI, which has no such variable. Install from GitHub — see [Install](#1-install) |
| `401` on everything | The credential was revoked, or is **past 90 days**, or `DATACORE_A2A_URL` is not the endpoint that issued it. On `DATACORE_MANDATE`: the mandate expired and **is not refreshed**. One message covers all of them on purpose, so the endpoint cannot be used to probe for valid keys. To tell them apart, call `GET /mcp/credentials` and see whether yours is still `ACTIVE` |
| `409` calling `/mandate/issue` by hand | You put the key in `Authorization`. It belongs in `X-Datacore-Credential` — see [Security model](#security-model). The package gets this right; you only hit it calling by hand |
| `409` creating a credential | You already hold 3 active ones. Revoke one first |
| `429` | More than 10 mandate exchanges in a minute for one credential. The package refreshes about four times an hour, so this means something is looping |
| `402` | This month's cap for that credential is spent. It resets on the 1st |
| `403` | The skill is outside the credential's allowlist — the free tier covers only the four skills above, and that set cannot be widened |
| `400` | Malformed request, or the skill id is not registered at the endpoint |
| `404` | No such route — check `DATACORE_A2A_URL` |
| `502` / `503` | The backend behind that skill is not answering |
| No tools at all | `DATACORE_SKILLS` filtered everything out, or the endpoint has no skills registered |

## Reporting a security issue

`mcp-security@datacore.vn`. Please do not open a public issue for a security bug.

If you think your credential has leaked, **report it now** — do not wait for it to
expire. We need to know so we can act on the service side.

## Privacy

See [PRIVACY.md](PRIVACY.md). In short: this package runs on your machine, stores
nothing, sends nothing anywhere except the DataCore endpoint you configured, and
never writes a mandate token to a log.

## License

MIT — see [LICENSE](LICENSE).

---

# Tiếng Việt

[English](#datacore-a2a--mcp-server) · **Tiếng Việt**

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
pip install git+https://github.com/DataCore-VietNam/datacore-a2a-mcp.git
```

> **Chưa dùng `pip install datacore-a2a-mcp`.** Tên đó có thật trên PyPI, nhưng
> bản mới nhất ở đó là `0.1.0` — bản ra đời trước cơ chế credential và chỉ nhận
> `DATACORE_MANDATE`. Nó bỏ qua hoàn toàn `DATACORE_API_KEY` và làm hỏng các
> bước bên dưới. Dòng này sẽ đổi ngay khi `0.2.1` lên PyPI; tới lúc đó thì cài từ
> GitHub.

### 2. Lấy token

```bash
curl -s -X POST https://gateway.datacore.vn/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"<user>","password":"<pass>"}' | jq -r '.data.token'
```

Một chuỗi mờ (64 ký tự ở các môi trường đã kiểm). Phản hồi còn có `.data.jwt` —
**không dùng cái đó**. Gateway từ chối mọi request tự mang sẵn header
`Authorization`, nên JWT bạn tự gửi không bao giờ tới được dịch vụ; `token` mới
là header nó nhận.

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
| Gói miễn phí | 500.000 VND chi tiêu **mỗi credential mỗi tháng** |
| Giá mỗi lượt gọi | mặc định 500 VND, tức khoảng 1.000 lượt |
| Thời điểm reset | ngày 1 hàng tháng, giờ `Asia/Ho_Chi_Minh` |
| Số credential | tối đa 3 cái còn hiệu lực mỗi tài khoản |
| Hạn credential | 90 ngày |
| Tần suất đổi mandate | tối đa 10 lần mỗi phút cho mỗi credential |

Hạn mức tính **theo credential**, không theo tài khoản — ba credential là ba hạn
mức riêng. Dịch vụ đếm bằng VND thay vì bằng số lượt để sau này đặt giá riêng cho
từng skill mà không phải viết lại mọi hạn mức đã lưu.

Xem một credential đã dùng bao nhiêu, và thu hồi:

```bash
curl -s https://gateway.datacore.vn/mcp/credentials/<id>/usage -H "token: <token>" | jq .
curl -s https://gateway.datacore.vn/mcp/credentials -H "token: <token>" | jq .
curl -X DELETE https://gateway.datacore.vn/mcp/credentials/<id> -H "token: <token>"
```

`/usage` trả về `spent_vnd`, `spend_cap_vnd`, `quota_period` và `resets_at`. Thu
hồi trả `204`, và `404` nếu id không phải của bạn — hai trường hợp cố ý không
phân biệt được.

## Cấu hình

| Biến | Bắt buộc | Ý nghĩa |
|---|---|---|
| `DATACORE_A2A_URL` | có | Base URL gateway DataCore — `https://gateway.datacore.vn`, trừ khi bạn được cấp endpoint riêng |
| `DATACORE_API_KEY` | có¹ | Credential dài hạn dạng `dck_<prefix>_<secret>`. Server tự đổi nó lấy mandate ngắn hạn và tự gia hạn |
| `DATACORE_MANDATE` | có¹ | Mandate AP2 phát tay. Chỉ dùng nếu bạn được cấp theo cách cũ — xem ghi chú bên dưới |
| `DATACORE_SKILLS` | không | Danh sách skill id cách nhau bằng phẩy để thu hẹp tool, hoặc `*` để lấy hết những gì endpoint trả về. Bỏ trống dùng bốn skill mặc định |
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

### Claude Code / Claude Desktop — ví dụ cấu hình

Thêm vào `.mcp.json` (phạm vi project) hoặc config của Claude Desktop:

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

Tool list được **sinh từ endpoint**, không hardcode ở đây — nên khi DataCore thêm
skill, restart server là thấy tool mới.

Mặc định expose bốn skill đã nối backend thật:

| Tool | Skill id | Việc nó làm |
|---|---|---|
| `address_normalize` | `address.normalize` | Chuẩn hoá địa chỉ Việt Nam thành tỉnh / huyện / xã |
| `address_validate` | `address.validate` | Kiểm tra một địa chỉ theo dữ liệu hành chính |
| `company_search` | `company.search` | Tra cứu doanh nghiệp theo tên hoặc mã số thuế |
| `company_embeddings` | `company.embeddings` | Sinh vector embedding cho một đoạn văn bản |

Mọi tool nhận đúng một tham số bắt buộc là `text`, dạng chuỗi tự do; không nhận
thêm thuộc tính nào khác. Mọi tool là **read-only** (`readOnlyHint: true`): không
ghi, không xoá, không tạo gì, và gọi lại cùng input cho cùng kết quả.

Ba skill còn lại của DataCore (`company.graph`, `company.financial-sankey`,
`company.news`) **cố ý không được expose**: chúng đang trả dữ liệu
mock/deterministic. Đặt `DATACORE_SKILLS="*"` thì chúng hiện ra thành tool, nhưng
credential gói miễn phí không gọi được — allowlist của nó chỉ có bốn skill trên,
nên mọi lời gọi đều trả `403`. Xin thêm skill lúc tạo credential cũng không phải
lỗi; yêu cầu bị thu hẹp lặng lẽ về đúng bốn skill đó.

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

Log đi ra **stderr**, prefix `[datacore-mcp]`. stdout là kênh JSON-RPC.

| Triệu chứng | Nguyên nhân thường gặp |
|---|---|
| Server thoát ngay, `MISSING required environment variable` | Chưa set `DATACORE_A2A_URL` |
| Server thoát ngay, `MISSING authentication` | Chưa set `DATACORE_API_KEY` lẫn `DATACORE_MANDATE` |
| `DATACORE_API_KEY` như không có tác dụng | Bạn đang chạy bản `0.1.0` lấy từ PyPI, bản đó không có biến này. Cài từ GitHub — xem [Cài](#1-cài) |
| `401` ở mọi request | Credential bị thu hồi, hoặc **đã quá 90 ngày**, hoặc `DATACORE_A2A_URL` không phải endpoint đã cấp credential đó. Nếu dùng `DATACORE_MANDATE`: mandate hết hạn và **không tự gia hạn**. Một thông báo duy nhất cho tất cả — cố ý, để endpoint không thành công cụ dò key. Cách phân biệt: gọi `GET /mcp/credentials` xem credential còn `ACTIVE` không |
| `409` khi tự gọi `/mandate/issue` | Bạn gửi key trong `Authorization`. Phải là `X-Datacore-Credential` — xem [Mô hình bảo mật](#mô-hình-bảo-mật). Package tự làm đúng; lỗi này chỉ gặp khi gọi tay |
| `409` khi tạo credential | Bạn đang giữ đủ 3 credential còn hiệu lực. Thu hồi bớt một cái |
| `429` | Quá 10 lần đổi mandate trong một phút cho cùng một credential. Package chỉ xin khoảng bốn lần mỗi giờ, nên gặp mã này nghĩa là có cái gì đó đang lặp |
| `402` | Credential đó đã dùng hết hạn mức tháng này. Hạn mức reset vào ngày 1 |
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
