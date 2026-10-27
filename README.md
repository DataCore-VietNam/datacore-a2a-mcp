# DataCore A2A — MCP server

<!-- mcp-name: vn.datacore/datacore-a2a -->
<!-- Fallback marker: the registry looks for a substring, so both lines can
     coexist. Keeps a way back if domain verification does not land, without
     publishing a new version just to fix a comment line.
     mcp-name: io.github.nambn3tit/datacore-a2a-mcp -->

<!-- Links in this file are absolute on purpose. This file is the long
     description on PyPI, and PyPI rewrites heading ids to `user-content-*`
     without rewriting the links that point at them — so a relative link or a
     bare `#anchor` renders as a dead link there. README.vi.md is only ever read
     on GitHub, so it keeps the short forms. -->

**English** · [Tiếng Việt](https://github.com/DataCore-VietNam/datacore-a2a-mcp/blob/master/README.vi.md)

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
pip install datacore-a2a-mcp
```

> If you installed from GitHub while this was unreleased, `--upgrade` will not
> move you to the PyPI build — uninstall first, then install again.

### 2. Get a session token

Sign in at [datacore.vn](https://datacore.vn), then copy the `token` request
header from any call to `gateway.datacore.vn` (DevTools → Network). 64 hex chars.

No `curl` equivalent: `POST /auth/login` RSA-decrypts the password and no
endpoint publishes the public key, so only the web app can complete a login. A
credential page will remove this step.

Ignore the `jwt` from the same login — the gateway rejects client-supplied
`Authorization` with `409`; `token` is the header it accepts.

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
Revoke one first (see
[Quotas and limits](https://github.com/DataCore-VietNam/datacore-a2a-mcp/blob/master/README.md#quotas-and-limits)).

### 4. Declare it in your client

See
[Configuration](https://github.com/DataCore-VietNam/datacore-a2a-mcp/blob/master/README.md#configuration)
below.

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
[Quotas and limits](https://github.com/DataCore-VietNam/datacore-a2a-mcp/blob/master/README.md#quotas-and-limits));
mandates already issued from it keep working for the rest of their 15 minutes —
there is no instant revocation list.

The mandate is the opposite: 15 minutes of life, process memory only. It is not
written to disk, never logged, and you should never need to look at it.

Issuance is rate-limited to 10 exchanges per minute per credential, so the
endpoint cannot be used to walk the key space. Every rejection — unknown key,
revoked key, expired key, wrong secret — returns the same `401` message for the
same reason.

**This package** never logs a token, not even partially, and never logs the
`text` you send. That is a promise about the process running on your machine —
the service side is a separate matter, and
[PRIVACY.md](https://github.com/DataCore-VietNam/datacore-a2a-mcp/blob/master/PRIVACY.md)
says plainly what it stores.

## Troubleshooting

Logs go to **stderr**, prefixed `[datacore-mcp]`. stdout is the JSON-RPC channel.

| Symptom | Usual cause |
|---|---|
| Exits at once, `MISSING required environment variable` | `DATACORE_A2A_URL` is not set |
| Exits at once, `MISSING authentication` | Neither `DATACORE_API_KEY` nor `DATACORE_MANDATE` is set |
| `DATACORE_API_KEY` appears to be ignored | You are on `0.1.0`, which predates credentials and reads only `DATACORE_MANDATE`. Upgrade: `pip install -U datacore-a2a-mcp` |
| `401` on everything | The credential was revoked, or is **past 90 days**, or `DATACORE_A2A_URL` is not the endpoint that issued it. On `DATACORE_MANDATE`: the mandate expired and **is not refreshed**. One message covers all of them on purpose, so the endpoint cannot be used to probe for valid keys. To tell them apart, call `GET /mcp/credentials` and see whether yours is still `ACTIVE` |
| `409` calling `/mandate/issue` by hand | You put the key in `Authorization`. It belongs in `X-Datacore-Credential`. The package gets this right; you only hit it calling by hand |
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

See
[PRIVACY.md](https://github.com/DataCore-VietNam/datacore-a2a-mcp/blob/master/PRIVACY.md).
In short: this package runs on your machine, stores nothing, sends nothing
anywhere except the DataCore endpoint you configured, and never writes a mandate
token to a log.

## License

MIT — see
[LICENSE](https://github.com/DataCore-VietNam/datacore-a2a-mcp/blob/master/LICENSE).
