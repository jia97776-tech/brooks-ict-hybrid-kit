import unittest

from scanner_service.newsguard import news_risk, symbol_currencies

NOW = 1_000_000


def ev(currency="USD", impact="High", offset_min=10, title="CPI"):
    return {"title": title, "currency": currency, "impact": impact,
            "epoch": NOW + offset_min * 60}


class NewsGuardTest(unittest.TestCase):
    def test_symbol_currency_mapping(self):
        self.assertEqual(symbol_currencies("EURUSD"), {"EUR", "USD"})
        self.assertEqual(symbol_currencies("USDJPY"), {"USD", "JPY"})
        self.assertEqual(symbol_currencies("US500"), {"USD"})
        self.assertEqual(symbol_currencies("BTC"), {"USD"})
        self.assertEqual(symbol_currencies("XAUUSD"), {"USD"})

    def test_high_impact_usd_event_flags_usd_symbols(self):
        events = [ev()]
        for sym in ("US500", "BTC", "EURUSD", "XAUUSD"):
            hit = news_risk(sym, now=NOW, events=events)
            self.assertIsNotNone(hit, sym)
            self.assertEqual(hit["minutes"], 10)

    def test_eur_event_only_flags_eur_pairs(self):
        events = [ev(currency="EUR", title="ECB Rate")]
        self.assertIsNotNone(news_risk("EURUSD", now=NOW, events=events))
        self.assertIsNone(news_risk("US500", now=NOW, events=events))
        self.assertIsNone(news_risk("USDJPY", now=NOW, events=events))

    def test_medium_impact_and_out_of_window_ignored(self):
        self.assertIsNone(news_risk("US500", now=NOW, events=[ev(impact="Medium")]))
        self.assertIsNone(news_risk("US500", now=NOW, events=[ev(offset_min=45)]))
        self.assertIsNotNone(news_risk("US500", now=NOW, events=[ev(offset_min=-25)]))

    def test_nearest_event_wins(self):
        events = [ev(offset_min=25, title="Far"), ev(offset_min=-5, title="Near")]
        hit = news_risk("US500", now=NOW, events=events)
        self.assertEqual(hit["title"], "Near")


if __name__ == "__main__":
    unittest.main()
