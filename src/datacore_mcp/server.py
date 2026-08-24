#!/usr/bin/env python3
"""
MCP server cho DataCore: mỗi skill dữ liệu thành một MCP tool.

    MCP client (stdio) ──► server này ──HTTPS──► DataCore API

Mandate token được mang **nguyên dạng** ở header ``X-AP2-Mandate`` để phía
DataCore verify. Server này không bao giờ tự khai bất kỳ header authorization
nào khác: một client không được là nơi tự cấp quyền cho chính nó, nên nó chỉ
chuyển tiếp thứ nó được cấp.

Tool list sinh **từ endpoint** chứ không hardcode ở đây, nên DataCore thêm
skill là client thấy tool mới sau khi restart server này.

Zero dependency, Python 3.9+. MCP stdio chỉ là JSON-RPC 2.0 phân cách bằng
newline nên không cần SDK — và quan trọng hơn, người cài không phải kéo theo
cây dependency nào.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
import uuid

try:
    from . import __version__
except ImportError:  # chạy trực tiếp file này, ngoài package
    __version__ = "0.0.0+local"


# ------------------------------------------------------------------ cấu hình

#: Skill được expose ra tool. Cố ý là danh sách trắng tường minh chứ không
#: phải "mọi thứ endpoint trả về": ``company.graph``,
#: ``company.financial-sankey`` và ``company.news`` hiện trả dữ liệu
#: demo/deterministic, nên đưa chúng ra ngoài là mô tả dữ liệu giả như dữ liệu
#: thật — lý do bị registry từ chối phổ biến nhất. Chuyển sang đây khi từng
#: skill có dữ liệu thật.
DEFAULT_SKILLS = (
    "address.normalize",
    "address.validate",
    "company.search",
    "company.embeddings",
)

PROTOCOL_FALLBACK = "2025-06-18"

# Tên tool MCP không nhận dấu chấm, mà skill id thì có ("address.normalize").
# Đổi sang '_' và giữ map ngược lại — cái gửi lên phải là id thật.
_TOOL_NAME_SAFE = re.compile(r"[^a-zA-Z0-9_-]")

_skill_by_tool_name = {}


def log(msg):
    """stderr, không phải stdout — stdout là kênh JSON-RPC, ghi gì vào đó là hỏng protocol."""
    print(f"[datacore-mcp] {msg}", file=sys.stderr, flush=True)


def _require(name, what, example):
    """
    Env bắt buộc, không có default. Bản trước default ``A2A_BASE_URL`` về một
    IP LAN của người viết; ai cài cũng gặp timeout mà không hiểu vì sao. Thiếu
    cấu hình là lỗi không tự phục hồi được, nên fail ngay và nói rõ thiếu gì.
    """
    value = os.environ.get(name, "").strip()
    if not value:
        log(f"THIẾU biến môi trường bắt buộc {name} ({what}).")
        log(f"  ví dụ: {name}={example}")
        log("  xem README để biết cách lấy mandate và URL endpoint.")
        sys.exit(2)
    return value


def load_config():
    base_url = _require(
        "DATACORE_A2A_URL",
        "base URL của endpoint DataCore",
        "https://api.example.com",
    ).rstrip("/")
    mandate = _require(
        "DATACORE_MANDATE",
        "AP2 mandate token do DataCore cấp",
        "<jws-token>",
    )

    raw_skills = os.environ.get("DATACORE_SKILLS", "").strip()
    if raw_skills == "*":
        skills = None  # None = không lọc, lấy hết những gì endpoint trả về
    elif raw_skills:
        skills = tuple(s.strip() for s in raw_skills.split(",") if s.strip())
    else:
        skills = DEFAULT_SKILLS

    timeout = float(os.environ.get("DATACORE_TIMEOUT", "30"))
    return base_url, mandate, skills, timeout


BASE_URL, MANDATE, SKILL_FILTER, TIMEOUT = "", "", DEFAULT_SKILLS, 30.0


# ------------------------------------------------------------------ HTTP


class A2AError(Exception):
    """DataCore trả về HTTP lỗi. ``status`` là mã, ``detail`` là body."""

    def __init__(self, status, detail):
        super().__init__(f"HTTP {status}: {detail}")
        self.status = status
        self.detail = detail


#: Mã status DataCore trả về, dịch sang câu người đọc hiểu được thay vì để
#: client tự đoán ý nghĩa của một con số như 402.
_STATUS_HINT = {
    400: "request không hợp lệ, hoặc skill chưa được đăng ký",
    401: (
        "mandate thiếu hoặc không hợp lệ. Kiểm tra DATACORE_MANDATE còn hạn, và "
        "kiểm tra DATACORE_A2A_URL đúng là endpoint DataCore đã được cấp"
    ),
    402: "vượt spend cap của mandate — cần mandate mới hoặc cap cao hơn",
    403: "skill nằm ngoài allowlist của mandate",
    404: "không tìm thấy route — kiểm tra lại DATACORE_A2A_URL",
    502: "backend của skill này không phản hồi",
    503: "dịch vụ tạm thời không khả dụng",
}


def _error_detail(exc):
    """
    Lấy field ``error`` trong body lỗi. Body có thể không phải JSON (một proxy
    chen vào và trả HTML chẳng hạn), nên phải chịu được cả trường hợp đó thay
    vì ném tiếp một lỗi parse che mất lỗi gốc.
    """
    try:
        body = exc.read().decode("utf-8", "replace")
    except Exception:
        return exc.reason or "không có chi tiết"
    try:
        parsed = json.loads(body)
    except ValueError:
        return (body[:300] or exc.reason or "không có chi tiết").strip()
    if isinstance(parsed, dict):
        return parsed.get("error") or parsed.get("message") or json.dumps(parsed)[:300]
    return body[:300]


def http_json(path, payload=None):
    """
    Một chỗ duy nhất gắn ``X-AP2-Mandate``. Token đi cả trên discovery lẫn
    invoke, vì cả hai đều là request được authorize — discovery không mang
    mandate cũng bị từ chối 401.
    """
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Accept": "application/json", "X-AP2-Mandate": MANDATE}
    if data is not None:
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers=headers,
        method="POST" if data is not None else "GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise A2AError(e.code, _error_detail(e)) from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"không kết nối được tới {BASE_URL}: {e.reason}") from None


# ------------------------------------------------------------------ discovery


def tool_name_for(skill_id):
    return _TOOL_NAME_SAFE.sub("_", skill_id)


def discover_tools():
    """
    Sinh tool list từ endpoint discovery.

    Endpoint trả kèm vài field mô tả hạ tầng phía DataCore; chúng bị bỏ đi có
    chủ ý. Địa chỉ nội bộ và thông điệp lỗi hạ tầng không có việc gì phải đi
    tới máy người dùng, và càng không thuộc về một tool description mà model
    sẽ đọc.
    """
    entries = http_json("/orchestrate/skills")
    if not isinstance(entries, list):
        raise RuntimeError(f"/orchestrate/skills trả về {type(entries).__name__}, cần một list")

    _skill_by_tool_name.clear()
    tools = []
    skipped = []

    for entry in entries:
        skill_id = (entry or {}).get("id")
        if not skill_id:
            continue
        if SKILL_FILTER is not None and skill_id not in SKILL_FILTER:
            skipped.append(skill_id)
            continue

        name = tool_name_for(skill_id)
        _skill_by_tool_name[name] = skill_id

        # `name` của endpoint là mô tả ngắn của chính skill; nó là title hiển
        # thị tốt hơn skill id. Rơi về id khi endpoint không trả được mô tả.
        title = entry.get("name") or skill_id
        description = entry.get("description") or f"DataCore skill {skill_id}"
        examples = entry.get("examples") or []
        if examples:
            description += "\n\nVí dụ input: " + "; ".join(str(e) for e in examples[:3])
        if entry.get("available") is False:
            description += (
                "\n\n(Agent giữ skill này đang không phản hồi. Skill id vẫn đúng "
                "và gọi được khi agent trở lại.)"
            )

        tools.append({
            "name": name,
            "title": title,
            "description": description,
            # Bốn hint đều là sự thật về skill, không phải khai cho đủ: mọi
            # skill hiện tại là tra cứu thuần, không ghi gì, gọi lại cùng input
            # cho cùng kết quả, và dữ liệu đến từ backend ngoài process này.
            "annotations": {
                "title": title,
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            },
            "inputSchema": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Input dạng free-text gửi cho skill.",
                    }
                },
                "required": ["text"],
                "additionalProperties": False,
            },
        })

    log(f"{len(tools)} tool từ {BASE_URL}: {sorted(_skill_by_tool_name.values())}")
    if skipped:
        log(f"bỏ qua {len(skipped)} skill ngoài DATACORE_SKILLS: {sorted(skipped)}")
    return tools


def call_skill(skill_id, text):
    """Gọi một skill và trả về payload thô mà DataCore trả lại."""
    body = http_json("/orchestrate", {"skill": skill_id, "text": text})

    payload = (body or {}).get("payload")
    state = (body or {}).get("state")
    if not payload:
        raise RuntimeError(f"DataCore trả state={state} nhưng không có payload")
    return payload


# ------------------------------------------------------------------ MCP


def _tool_error(exc):
    """Câu lỗi cho Claude đọc: mã status → nguyên nhân, kèm chi tiết của server."""
    if isinstance(exc, A2AError):
        hint = _STATUS_HINT.get(exc.status, "lỗi từ DataCore")
        return f"{hint} (HTTP {exc.status}): {exc.detail}"
    return str(exc)


def handle(method, params):
    """
    Trả về ``(result, error)``. Chỉ implement những method client thực sự gọi
    — initialize / tools/list / tools/call — cộng ping. Method khác trả -32601.
    """
    if method == "initialize":
        requested = params.get("protocolVersion")
        return {
            # Echo lại version client xin nếu là string: server không dùng gì
            # đặc thù theo version, nên khớp client là lựa chọn an toàn nhất.
            "protocolVersion": requested if isinstance(requested, str) else PROTOCOL_FALLBACK,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "datacore-a2a", "version": __version__},
        }, None

    if method == "ping":
        return {}, None

    if method == "tools/list":
        try:
            return {"tools": discover_tools()}, None
        except Exception as e:
            # Không với tới endpoint được là lỗi cấu hình, không phải lỗi
            # protocol — trả error để client hiện lý do thật.
            return None, {"code": -32603, "message": f"Discovery thất bại: {_tool_error(e)}"}

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        text = args.get("text")

        if not _skill_by_tool_name:
            try:
                discover_tools()
            except Exception as e:
                return None, {"code": -32603, "message": f"Discovery thất bại: {_tool_error(e)}"}

        skill_id = _skill_by_tool_name.get(name)
        if not skill_id:
            return None, {"code": -32602, "message": f"Tool không tồn tại: {name}"}
        if not isinstance(text, str) or not text.strip():
            return None, {"code": -32602, "message": "Thiếu tham số 'text'"}

        try:
            return {"content": [{"type": "text", "text": call_skill(skill_id, text)}]}, None
        except Exception as e:
            # isError=true để Claude thấy tool thất bại và tự điều chỉnh, thay
            # vì tưởng chuỗi lỗi là kết quả hợp lệ.
            message = _tool_error(e)
            log(f"tool {name} lỗi: {message}")
            return {"content": [{"type": "text", "text": message}], "isError": True}, None

    return None, {"code": -32601, "message": f"Method không hỗ trợ: {method}"}


def serve():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as e:
            log(f"bỏ qua dòng không phải JSON: {e}")
            continue

        req_id = request.get("id")
        method = request.get("method")

        # Notification (không có id) — theo spec KHÔNG được trả lời.
        # notifications/initialized rơi vào đây.
        if req_id is None:
            log(f"notification: {method}")
            continue

        try:
            result, error = handle(method, request.get("params") or {})
        except Exception as e:
            result, error = None, {"code": -32603, "message": f"Lỗi nội bộ: {e}"}

        response = {"jsonrpc": "2.0", "id": req_id}
        if error:
            response["error"] = error
        else:
            response["result"] = result

        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


def main():
    global BASE_URL, MANDATE, SKILL_FILTER, TIMEOUT
    BASE_URL, MANDATE, SKILL_FILTER, TIMEOUT = load_config()

    # Không log MANDATE, kể cả một phần của nó: đây là token cấp quyền chi
    # tiêu, và stderr của MCP server thường được client ghi ra file log.
    scope = "tất cả skill của endpoint" if SKILL_FILTER is None else ", ".join(SKILL_FILTER)
    log(f"start v{__version__} | base={BASE_URL} | timeout={TIMEOUT}s | skill={scope}")

    try:
        serve()
    except (KeyboardInterrupt, BrokenPipeError):
        pass


if __name__ == "__main__":
    main()