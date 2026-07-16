from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "brooks-ict-hybrid" / "SKILL.md"
GATES = ROOT / "brooks-ict-hybrid" / "references" / "execution-gates.md"
TEMPLATE = ROOT / "brooks-ict-hybrid" / "references" / "live-desk-template.md"


class LiveChatStyleBalanceTests(unittest.TestCase):
    """Middle path: usable desk voice without Codex format police."""

    @classmethod
    def setUpClass(cls):
        cls.skill = SKILL.read_text(encoding="utf-8")
        cls.gates = GATES.read_text(encoding="utf-8")
        cls.template = TEMPLATE.read_text(encoding="utf-8")

    def test_format_police_stays_gone(self):
        self.assertNotIn("Feishu / Mobile Conversation Contract", self.skill)
        self.assertNotIn("Mobile Delta-First Override", self.template)
        self.assertNotIn("通常 2–5 行", self.skill)
        self.assertNotIn("单品种实时追问禁止表格", self.template)
        self.assertNotIn("这张我不做，所以没有我的入场价", self.skill)

    def test_moderate_live_chat_guidance_exists(self):
        self.assertIn("Live Chat Style（好用优先", self.skill)
        self.assertIn("厚度按需", self.skill)
        self.assertIn("非交易问题", self.skill)
        self.assertIn("好用优先", self.template)
        self.assertIn("推荐", self.template)

    def test_blocked_trigger_policy_and_soft_exit_remain(self):
        self.assertIn("禁止把审计 trigger 报成可执行入场价", self.gates)
        self.assertIn("成交后不得新增软离场", self.gates)
        self.assertIn("pushable=false", self.skill)


if __name__ == "__main__":
    unittest.main()
