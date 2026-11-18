"""Câu lỗi mà Claude đọc khi DataCore trả HTTP lỗi.

Chạy: PYTHONPATH=src python3 -m unittest discover -s tests -v
"""

import unittest

from datacore_mcp.server import A2AError, _tool_error

QUOTA_DETAIL = (
    "QUOTA_EXCEEDED: Used 1000 of 1000 requests in the last 30 days; "
    "next slot at 2026-12-01T00:00:00Z"
)


class ToolErrorTest(unittest.TestCase):
    def test_quota_429_explains_the_quota_and_keeps_the_detail(self):
        msg = _tool_error(A2AError(429, QUOTA_DETAIL))
        self.assertTrue(msg.startswith("request quota is used up"), msg)
        self.assertIn("next slot at 2026-12-01T00:00:00Z", msg)

    def test_rate_limit_429_is_not_called_a_quota(self):
        # /mandate/issue cũng trả 429 khi xin mandate quá dồn dập — khác hẳn hết hạn mức.
        msg = _tool_error(A2AError(429, "Too many issue requests, slow down"))
        self.assertTrue(msg.startswith("too many mandate requests"), msg)

    def test_429_without_detail_does_not_crash(self):
        msg = _tool_error(A2AError(429, None))
        self.assertTrue(msg.startswith("too many mandate requests"), msg)

    def test_402_no_longer_has_a_special_hint(self):
        # Server không còn trả 402; câu "this month's quota" là mô hình cũ.
        msg = _tool_error(A2AError(402, "x"))
        self.assertTrue(msg.startswith("error from DataCore"), msg)


if __name__ == "__main__":
    unittest.main()
