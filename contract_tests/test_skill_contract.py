from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "brooks-ict-hybrid" / "SKILL.md"
GATES = ROOT / "brooks-ict-hybrid" / "references" / "execution-gates.md"
LADDER = ROOT / "brooks-ict-hybrid" / "references" / "entry-ladder.md"
TEMPLATE = ROOT / "brooks-ict-hybrid" / "references" / "live-desk-template.md"
CHANGELOG = ROOT / "brooks-ict-hybrid" / "CHANGELOG.md"


class StopContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = SKILL.read_text(encoding="utf-8")
        cls.gates = GATES.read_text(encoding="utf-8")
        cls.ladder = LADDER.read_text(encoding="utf-8")
        cls.template = TEMPLATE.read_text(encoding="utf-8")
        cls.changelog = CHANGELOG.read_text(encoding="utf-8")

    def test_version_and_stop_scope_are_binding(self):
        self.assertIn("2026-07-15c", self.skill)
        self.assertIn("止损级别", self.skill)
        for scope in ("M1/M5 触发损", "M15 结构损", "H4 POI 整层损"):
            self.assertIn(scope, self.skill)

    def test_pretrade_contract_enumerates_relevant_anchor_candidates(self):
        for text in (self.skill, self.gates, self.ladder, self.template):
            self.assertIn("候选锚", text)
        self.assertIn("背景 confluence", self.gates)
        self.assertIn("重新计算 entry / size / management / RR", self.gates)
        self.assertNotIn(
            "空单硬损公式固定为 `max(序列高点, 止损侧旧高/等高/POI上沿)",
            self.skill,
        )
        self.assertNotIn(
            "multi-TF confluence may set stop beyond outermost HTF array edge",
            self.gates,
        )
        self.assertNotIn(
            "anchor=max(本次序列最高点, 止损侧未完成等高/旧高/POI上沿)",
            self.ladder,
        )

    def test_postfill_stop_cannot_widen(self):
        self.assertIn("成交后禁止扩损", self.skill)
        self.assertIn("initial hard stop", self.gates)
        self.assertIn("新票据", self.gates)
        self.assertNotIn(
            "restore structural stop while cutting size",
            self.gates,
        )
        self.assertIn("66.45 - 0.04 = 66.41", self.changelog)
        self.assertIn("66.31", self.changelog)

    def test_pending_templates_lock_scope_candidates_and_arithmetic(self):
        self.assertIn(
            "pending 计划必须给全 **TF、事件类型、冻结价、触发价、止损级别、候选锚、anchor、buffer、硬损、有效根数、撤单价**",
            self.ladder,
        )
        for marker in (
            "For an unconfirmed new opportunity:",
            "For a conditional order plan:",
        ):
            block = self.template.split(marker, 1)[1].split("```", 2)[1]
            for required in ("止损级别", "候选锚", "anchor", "buffer", "硬损"):
                self.assertIn(required, block)
        hype_pending = self.template.split(
            "Worked pending scope example:", 1
        )[1].split("```", 2)[1]
        for required in ("M15 结构损", "66.57", "0.0325", "66.53", "有效 6 根"):
            self.assertIn(required, hype_pending)

    def test_skill_file_operations_do_not_mutate_position_state(self):
        self.assertIn("文件操作 ≠ 仓位操作", self.skill)
        self.assertIn("明确点名品种", self.skill)
        self.assertIn("不得改变当前仓位", self.gates)

    def test_chase_and_gate_only_stack_are_documented(self):
        stack = (ROOT / "brooks-ict-hybrid" / "references" / "local-stack.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("`chase`", stack)
        self.assertIn("`ltf_status=chase`", stack)
        self.assertIn("Gate-only", stack)
        self.assertIn("`GET /openapi.json`", stack)
        self.assertIn("`GET /signals?limit=N`", stack)
        self.assertNotIn("Bitget USDT-M futures", stack)
        self.assertNotIn("故障回落 MEXC", stack)


if __name__ == "__main__":
    unittest.main()
