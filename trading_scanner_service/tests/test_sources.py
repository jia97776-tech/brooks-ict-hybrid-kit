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


class FakeMexc:
    def __init__(self):
        self.price_symbols = []
        self.bar_requests = []

    def price(self, symbol):
        self.price_symbols.append(symbol)
        return 100.0

    def bars(self, symbol, tf, limit):
        self.bar_requests.append((symbol, tf, limit))
        return [Bar(ts=1, open=99.0, high=101.0, low=98.0, close=100.0, volume=10.0)]


class FakeGateTradFi:
    def __init__(self):
        self.price_symbols = []
        self.bar_requests = []

    def price(self, symbol):
        self.price_symbols.append(symbol)
        return 1.1

    def bars(self, symbol, tf, limit):
        self.bar_requests.append((symbol, tf, limit))
        return [Bar(ts=1, open=1.0, high=1.2, low=0.9, close=1.1, volume=0.0)]


class FakeBitget:
    def __init__(self, fail=False):
        self.fail = fail
        self.price_symbols = []
        self.bar_requests = []

    def price(self, symbol):
        if self.fail:
            raise SourceError("bitget down")
        self.price_symbols.append(symbol)
        return 200.0

    def bars(self, symbol, tf, limit):
        if self.fail:
            raise SourceError("bitget down")
        self.bar_requests.append((symbol, tf, limit))
        return [Bar(ts=1, open=199.0, high=201.0, low=198.0, close=200.0, volume=5.0)]


class FakeBitgetTradFi(FakeBitget):
    def price(self, symbol):
        if self.fail:
            raise SourceError("bitget tradfi down")
        self.price_symbols.append(symbol)
        return 2.2

    def bars(self, symbol, tf, limit):
        if self.fail:
            raise SourceError("bitget tradfi down")
        self.bar_requests.append((symbol, tf, limit))
        return [Bar(ts=1, open=2.0, high=2.3, low=1.9, close=2.2, volume=0.0)]


def make_router(bitget_fail=False, tradfi_fail=False):
    mexc = FakeMexc()
    gate = FakeGateTradFi()
    bitget = FakeBitget(fail=bitget_fail)
    bitget_tradfi = FakeBitgetTradFi(fail=tradfi_fail)
    router = MarketDataRouter(
        mexc=mexc, gate_tradfi=gate, bitget=bitget, bitget_tradfi=bitget_tradfi)
    return router, mexc, gate, bitget, bitget_tradfi


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

    def test_crypto_uses_bitget_mix(self):
        router, mexc, gate, bitget, _ = make_router()

        for symbol in ["BTC", "ETH", "HYPE"]:
            router.price(symbol)

        self.assertEqual(mexc.price_symbols, [])
        self.assertEqual(gate.price_symbols, [])
        self.assertEqual(bitget.price_symbols, ["BTC_USDT", "ETH_USDT", "HYPE_USDT"])

    def test_crypto_falls_back_to_mexc_when_bitget_down(self):
        router, mexc, _, _, _ = make_router(bitget_fail=True)

        self.assertEqual(router.price("BTC"), 100.0)
        self.assertEqual(mexc.price_symbols, ["BTC_USDT"])

    def test_metals_indexes_oil_use_bitget_tradfi(self):
        router, mexc, gate, _, tradfi = make_router()

        for symbol in ["XAUUSD", "XAGUSD", "NAS100", "US500", "US30", "XTIUSD"]:
            router.price(symbol)

        self.assertEqual(mexc.price_symbols, [])
        self.assertEqual(gate.price_symbols, [])
        self.assertEqual(
            tradfi.price_symbols,
            ["XAU_USDT", "SILVER_USDT", "NAS100_USDT", "SPX500_USDT",
             "US30_USDT", "USOIL_USDT"],
        )
        self.assertEqual(normalize_gate_tradfi_symbol("XAU_USDT"), "XAUUSD")
        self.assertEqual(normalize_gate_tradfi_symbol("NAS100_USDT"), "NAS100")
        self.assertEqual(normalize_gate_tradfi_symbol("SPX500_USDT"), "US500")

    def test_fx_uses_bitget_tradfi(self):
        router, mexc, gate, _, tradfi = make_router()

        self.assertEqual(router.price("EURUSD"), 2.2)
        self.assertEqual(router.bars("USDJPY", "M15", 50)[0].close, 2.2)

        self.assertEqual(mexc.price_symbols, [])
        self.assertEqual(gate.price_symbols, [])
        self.assertEqual(tradfi.price_symbols, ["EURUSD"])
        self.assertEqual(tradfi.bar_requests, [("USDJPY", "M15", 50)])

    def test_tradfi_falls_back_to_preswitch_source_when_bitget_down(self):
        # FX + XAU/NAS/US500 lived on Gate before the switch; US30/oil on MEXC
        router, mexc, gate, _, _ = make_router(tradfi_fail=True)

        self.assertEqual(router.price("EURUSD"), 1.1)
        self.assertEqual(router.price("XAUUSD"), 1.1)
        self.assertEqual(router.price("US30"), 100.0)
        self.assertEqual(gate.price_symbols, ["EURUSD", "XAU_USDT"])
        self.assertEqual(mexc.price_symbols, ["US30_USDT"])

    def test_unknown_symbols_fail_explicitly(self):
        self.assertEqual(classify_symbol("BTC"), "bitget_mix")
        self.assertEqual(classify_symbol("EURUSD"), "bitget_tradfi")
        self.assertEqual(classify_symbol("XAUUSD"), "bitget_tradfi")
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
