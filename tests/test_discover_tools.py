"""Tool nào hiện ra cho Claude: mặc định là đúng những skill mandate cho phép.

Chạy: PYTHONPATH=src python3 -m unittest discover -s tests -v
"""

import base64
import json
import unittest
from unittest import mock

from datacore_mcp import server

ENDPOINT_SKILLS = [
    {"id": "address.normalize"},
    {"id": "company.search"},
    {"id": "dataset.list"},
    {"id": "dataset.query"},
    {"id": "company.news"},
]


def _b64(obj):
    raw = json.dumps(obj).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def mandate_allowing(*skills):
    """JWS giả: chữ ký không được kiểm, chỉ payload có ý nghĩa ở phía client."""
    return f"{_b64({'alg': 'ES256'})}.{_b64({'allowed_skills': list(skills)})}.sig"


class DiscoverToolsTest(unittest.TestCase):
    def discover(self, skill_filter, mandate):
        with mock.patch.object(server, "SKILL_FILTER", skill_filter), \
                mock.patch.object(server, "http_json", return_value=ENDPOINT_SKILLS), \
                mock.patch.object(server, "current_mandate", return_value=mandate):
            return sorted(server._skill_by_tool_name[t["name"]] for t in server.discover_tools())

    def test_default_lists_every_skill_the_mandate_allows(self):
        # Skill mới bật cho tier ở admin phải hiện ra mà không cần sửa client.
        mandate = mandate_allowing("address.normalize", "company.search",
                                   "dataset.list", "dataset.query")
        self.assertEqual(
            self.discover(server.SCOPE_FROM_MANDATE, mandate),
            ["address.normalize", "company.search", "dataset.list", "dataset.query"],
        )

    def test_default_hides_skills_the_mandate_would_reject(self):
        mandate = mandate_allowing("address.normalize")
        self.assertEqual(self.discover(server.SCOPE_FROM_MANDATE, mandate), ["address.normalize"])

    def test_unreadable_mandate_falls_back_to_everything_the_endpoint_returns(self):
        # Lọc chỉ để hiển thị; gateway vẫn là nơi chặn. Đọc không được thì đừng giấu tool.
        everything = sorted(e["id"] for e in ENDPOINT_SKILLS)
        self.assertEqual(self.discover(server.SCOPE_FROM_MANDATE, "not-a-jws"), everything)
        no_claim = f"{_b64({'alg': 'ES256'})}.{_b64({'sub': 'x'})}.sig"
        self.assertEqual(self.discover(server.SCOPE_FROM_MANDATE, no_claim), everything)

    def test_star_lists_everything_regardless_of_mandate(self):
        self.assertEqual(
            self.discover(None, mandate_allowing("address.normalize")),
            sorted(e["id"] for e in ENDPOINT_SKILLS),
        )

    def test_explicit_list_narrows_to_exactly_those_skills(self):
        self.assertEqual(
            self.discover(("company.search", "dataset.list"), mandate_allowing("company.search")),
            ["company.search", "dataset.list"],
        )


class LoadConfigTest(unittest.TestCase):
    def skills_for(self, raw):
        env = {"DATACORE_A2A_URL": "https://example.test", "DATACORE_API_KEY": "k",
               "DATACORE_SKILLS": raw}
        with mock.patch.dict("os.environ", env, clear=True):
            return server.load_config()[3]

    def test_empty_means_scope_from_mandate(self):
        self.assertEqual(self.skills_for(""), server.SCOPE_FROM_MANDATE)

    def test_star_means_no_filter(self):
        self.assertIsNone(self.skills_for("*"))

    def test_list_is_parsed(self):
        self.assertEqual(self.skills_for(" a.b , c.d ,"), ("a.b", "c.d"))


if __name__ == "__main__":
    unittest.main()
