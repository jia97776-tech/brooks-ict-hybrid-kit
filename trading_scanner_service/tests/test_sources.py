import unittest

from scanner_service.sources import (
    Bar,
    GATE_INTERVAL,
    MEXC_INTERVAL,
    MarketDataRouter,
    SourceError,
    classify_symbol,
    normalize_gate_tradfi_symbol,
    normalize_symbol,
    normalize_timeframe,
)


class FakeGateTradFi:
    def __init__(self, fail=False):
        self.fail = fail
        self.price_symbols = []
        self.bar_requests = []

    def price(self, symbol):
        if self.fail:
            raise SourceError("gate tradfi down")
        self.price_symbols.append(symbol)
        return 1.1

    def bars(self, symbol, tf, limit):
        if self.fail:
            raise SourceError("gate tradfi down")
        self.bar_requests.append((symbol, tf, limit))
        return [Bar(ts=1, open=1.0, high=1.2, low=0.9, close=1.1, volume=0.0)]


class FakeGateCrypto(FakeGateTradFi):
    pass


def make_router(gate_fail=False, gate_crypto_fail=False):
    gate = FakeGateTradFi(fail=gate_fail)
    gate_crypto = FakeGateCrypto(fail=gate_crypto_fail)
    router = MarketDataRouter(gate_tradfi=gate, gate_crypto=gate_crypto)
    return router, gate, gate_crypto


class SourceRoutingTest(unittest.TestCase):
    def test_normalizes_common_aliases(self):
        self.assertEqual(normalize_symbol("btc"), "BTC_USDT")
        self.assertEqual(normalize_symbol("ethusdt"), "ETH_USDT")
        self.assertEqual(normalize_symbol("xau"), "XAU_USDT")
        self.assertEqual(normalize_symbol("XAU_USDT"), "XAU_USDT")
        self.assertEqual(normalize_symbol("xag"), "SILVER_USDT")
        self.assertEqual(normalize_symbol("nas100"), "NAS100_USDT")
        self.assertEqual(normalize_symbol("us500"), "SPX500_USDT")
        self.assertEqual(normalize_symbol("xtiusd"), "USOIL_USDT")
        self.assertEqual(normalize_symbol("eurusd"), "EURUSD")

    def test_crypto_uses_gate_futures(self):
        router, gate, gate_crypto = make_router()

        for symbol in ["BTC", "ETH", "HYPE"]:
            router.price(symbol)

        self.assertEqual(gate.price_symbols, [])
        self.assertEqual(gate_crypto.price_symbols, ["BTC_USDT", "ETH_USDT", "HYPE_USDT"])

    def test_crypto_raises_when_gate_futures_down_no_fallback(self):
        router, _, _ = make_router(gate_crypto_fail=True)

        with self.assertRaises(SourceError):
            router.price("BTC")

    def test_metals_indexes_oil_and_stock_perps_use_gate_tradfi(self):
        router, gate, gate_crypto = make_router()

        for symbol in ["XAUUSD", "XAGUSD", "NAS100", "US500", "US30", "XTIUSD",
                       "TSLA", "NVDA", "MSTR", "CRCL"]:
            router.price(symbol)

        self.assertEqual(gate_crypto.price_symbols, [])
        self.assertEqual(
            gate.price_symbols,
            ["XAU_USDT", "SILVER_USDT", "NAS100_USDT", "SPX500_USDT", "US30_USDT",
             "USOIL_USDT", "TSLA_USDT", "NVDA_USDT", "MSTR_USDT", "CRCL_USDT"],
        )
        self.assertEqual(normalize_gate_tradfi_symbol("XAU_USDT"), "XAUUSD")
        self.assertEqual(normalize_gate_tradfi_symbol("NAS100_USDT"), "NAS100")
        self.assertEqual(normalize_gate_tradfi_symbol("SPX500_USDT"), "US500")
        self.assertEqual(normalize_gate_tradfi_symbol("SILVER_USDT"), "XAGUSD")
        self.assertEqual(normalize_gate_tradfi_symbol("US30_USDT"), "US30")
        self.assertEqual(normalize_gate_tradfi_symbol("USOIL_USDT"), "XTIUSD")
        self.assertEqual(normalize_gate_tradfi_symbol("TSLA_USDT"), "TSLA")
        self.assertEqual(normalize_gate_tradfi_symbol("CRCL_USDT"), "CRCL")

    def test_fx_uses_gate_tradfi(self):
        router, gate, _ = make_router()

        self.assertEqual(router.price("EURUSD"), 1.1)
        self.assertEqual(router.bars("USDJPY", "M15", 50)[0].close, 1.1)

        self.assertEqual(gate.price_symbols, ["EURUSD"])
        self.assertEqual(gate.bar_requests, [("USDJPY", "M15", 50)])

    def test_fx_raises_when_gate_tradfi_down_no_fallback(self):
        router, _, _ = make_router(gate_fail=True)

        with self.assertRaises(SourceError):
            router.price("EURUSD")

    def test_unknown_symbols_fail_explicitly(self):
        self.assertEqual(classify_symbol("BTC"), "gate_crypto")
        self.assertEqual(classify_symbol("EURUSD"), "gate_tradfi")
        self.assertEqual(classify_symbol("XAUUSD"), "gate_tradfi")
        self.assertEqual(classify_symbol("TSLA"), "gate_tradfi")
        self.assertEqual(classify_symbol("DXY"), "gate_tradfi")
        self.assertEqual(normalize_symbol("USIDX"), "DXY")
        self.assertEqual(normalize_gate_tradfi_symbol("DXY"), "USIDX")
        with self.assertRaises(SourceError):
            classify_symbol("UNKNOWN")

    def test_accepts_required_timeframes(self):
        cases = {
            "1m": "M1",
            "5m": "M5",
            "15m": "M15",
            "1h": "H1",
            "4h": "H4",
            "1d": "D1",
            "1w": "W1",
            "M1": "M1",
            "H4": "H4",
            "D1": "D1",
            "W1": "W1",
        }
        for raw, expected in cases.items():
            self.assertEqual(normalize_timeframe(raw), expected)

    def test_data_source_interval_maps_cover_required_timeframes(self):
        for tf in ["M1", "M5", "M15", "H1", "H4", "D1", "W1"]:
            self.assertIn(tf, MEXC_INTERVAL)
            self.assertIn(tf, GATE_INTERVAL)
        self.assertEqual(GATE_INTERVAL["W1"], "7d")


if __name__ == "__main__":
    unittest.main()
