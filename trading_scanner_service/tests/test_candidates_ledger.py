"""candidates_ledger (scanner v2 §8.3) unit tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scanner_service import candidates_ledger as cl


class CandidatesLedgerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "candidates.db"
        self.patcher = mock.patch.object(cl, "DB_PATH", self.db)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_record_and_hint(self):
        cands = [
            {
                "symbol": "BTC",
                "tf": "H4",
                "direction": "SHORT",
                "state": "READY",
                "pushable": False,
                "not_pushable_reason": "map_tf_not_entry",
                "ltf_status": "awaiting_ltf_confirm",
                "mss": True,
                "cisd": True,
            },
            {
                "symbol": "ETH",
                "tf": "M15",
                "direction": "SHORT",
                "state": "READY",
                "pushable": False,
                "not_pushable_reason": "cisd_only",
                "cisd": True,
                "mss": False,
            },
            {
                "symbol": "PEPE",
                "tf": "H4",
                "direction": "LONG",
                "state": "CONDITIONAL_READY",
                "pushable": False,
            },
        ]
        n = cl.record_scan_candidates(cands, scan_id="test-scan-1", now=1_700_000_000)
        self.assertEqual(n, 3)
        summary = cl.stats_summary()
        self.assertEqual(summary["n_rows"], 3)
        self.assertEqual(summary["n_scans"], 1)
        # cisd_only / c_tier get machine hints
        self.assertIn("vetoed", summary["by_verdict"])

    def test_update_verdict_and_outcome(self):
        cl.record_scan_candidates(
            [{"symbol": "XAUUSD", "tf": "H4", "direction": "SHORT", "state": "READY"}],
            scan_id="s2",
            now=1,
            apply_machine_hint=False,
        )
        import sqlite3

        conn = sqlite3.connect(str(self.db))
        row_id = conn.execute("SELECT id FROM candidates LIMIT 1").fetchone()[0]
        conn.close()
        cl.update_desk_verdict(row_id, "trade")
        cl.update_outcome(row_id, 1.5, "sim")
        summary = cl.stats_summary()
        self.assertEqual(summary["by_verdict"].get("trade"), 1)

    def test_track_and_anomaly_fields(self):
        cands = [
            {
                "symbol": "BTC",
                "tf": "H4",
                "direction": "SHORT",
                "state": "READY",
                "setup_type": "drilldown_chain",
                "pushable": False,
            },
            {
                "symbol": "ETH",
                "tf": "M15",
                "direction": "LONG",
                "state": "CONDITIONAL_READY",
                "pushable": False,
                "not_pushable_reason": "map_tf_not_entry",
            },
            {
                "symbol": "SOL",
                "tf": "M15",
                "direction": "SHORT",
                "state": "READY",
                "setup_type": "confluence_retest",
                "confluence_zone": {"layer_count": 3},
            },
        ]
        n = cl.record_scan_candidates(cands, scan_id="track-1", now=2, model="scanner")
        self.assertEqual(n, 3)
        self.assertEqual(cands[0]["track"], "asymmetric")
        self.assertEqual(cands[1]["track"], "cashflow")
        self.assertEqual(cands[2]["track"], "asymmetric")
        import sqlite3

        conn = sqlite3.connect(str(self.db))
        rows = conn.execute(
            "SELECT symbol, track, model, anomaly FROM candidates WHERE scan_id=?",
            ("track-1",),
        ).fetchall()
        conn.close()
        by_sym = {r[0]: r for r in rows}
        self.assertEqual(by_sym["BTC"][1], "asymmetric")
        self.assertEqual(by_sym["ETH"][1], "cashflow")
        self.assertEqual(by_sym["BTC"][2], "scanner")
        self.assertEqual(by_sym["ETH"][3], "none")
        summary = cl.stats_summary()
        self.assertIn("by_track", summary)
        self.assertGreaterEqual(summary["by_track"].get("asymmetric", 0), 2)

    def test_reverse_direction_dol_is_data_inconsistent(self):
        long_bad = {
            "symbol": "BTC",
            "direction": "LONG",
            "price": 100.0,
            "dol": 95.0,
        }
        short_bad = {
            "symbol": "ETH",
            "direction": "SHORT",
            "entry_ref": 100.0,
            "dol": 105.0,
        }

        self.assertEqual(cl.normalize_anomaly(long_bad), "data_inconsistent")
        self.assertEqual(cl.normalize_anomaly(short_bad), "data_inconsistent")

    def test_explicit_none_does_not_bypass_reverse_dol_check(self):
        candidate = {
            "symbol": "BTC",
            "direction": "LONG",
            "price": 100.0,
            "dol": 95.0,
            "anomaly": "none",
        }

        cl.attach_protocol_fields([candidate])

        self.assertEqual(candidate["anomaly"], "data_inconsistent")

    def test_chase_maps_to_do_not_chase_hint(self):
        verdict, veto = cl.machine_hint_verdict(
            {
                "symbol": "BTC",
                "direction": "SHORT",
                "pushable": False,
                "not_pushable_reason": "chase",
            }
        )

        self.assertEqual(verdict, "do_not_chase")
        self.assertEqual(veto, "chase")

    def test_chase_hint_takes_precedence_over_counter_htf(self):
        verdict, veto = cl.machine_hint_verdict(
            {
                "symbol": "BTC",
                "direction": "SHORT",
                "pushable": False,
                "not_pushable_reason": "chase",
                "counter_htf": True,
            }
        )

        self.assertEqual(verdict, "do_not_chase")
        self.assertEqual(veto, "chase")


if __name__ == "__main__":
    unittest.main()
