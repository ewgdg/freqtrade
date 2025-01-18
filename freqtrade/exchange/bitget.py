import logging
import types
from typing import Any, Optional, override

import ccxt
from ccxt import ROUND_DOWN, ROUND_UP
from ccxt.base.exchange import Exchange

from freqtrade.enums.candletype import CandleType
from freqtrade.enums.marginmode import MarginMode
from freqtrade.enums.tradingmode import TradingMode
from freqtrade.exchange import Exchange
from freqtrade.exchange.exchange_types import FtHas
from freqtrade.exchange.exchange_utils_timeframe import timeframe_to_seconds


logger = logging.getLogger(__name__)


class Bitget(Exchange):
    _ft_has: FtHas = {
        "ohlcv_candle_limit": 180,
    }
    _ft_has_futures: FtHas = {
        "mark_ohlcv_timeframe": "4h",
        "funding_fee_timeframe": "8h",
    }

    _supported_trading_mode_margin_pairs: list[tuple[TradingMode, MarginMode]] = [
        # TradingMode.SPOT always supported and not required in this list
        # (TradingMode.MARGIN, MarginMode.CROSS),
        (TradingMode.FUTURES, MarginMode.CROSS),
        (TradingMode.FUTURES, MarginMode.ISOLATED),
    ]

    @override
    def _init_ccxt(
        self, exchange_config: dict[str, Any], sync: bool, ccxt_kwargs: dict[str, Any]
    ) -> ccxt.Exchange:
        api = super()._init_ccxt(exchange_config, sync, ccxt_kwargs)
        fetch_ohlcv_unpatched = api.fetch_ohlcv

        def fetch_ohlcv_patched(
            self,
            symbol: str,
            timeframe="1m",
            since: int | None = None,
            limit: int | None = None,
            params: dict = {},
        ):
            since_adapted = since
            # to ensure proper alignment, we need to fetch more data to cover the requested time range
            if since is not None:
                ms = ccxt.Exchange.parse_timeframe(timeframe) * 1000
                since_adapted = since - ms

            raw = fetch_ohlcv_unpatched(symbol, timeframe, since_adapted, limit + 2, params=params)
            start_i = 0
            for i in range(len(raw)):
                if raw[i][0] >= since:
                    start_i = i
                    break
            end_i = start_i + limit

            if start_i > 0 or end_i < len(raw):
                raw = raw[start_i:end_i]
            return raw

        api.fetch_ohlcv = types.MethodType(fetch_ohlcv_patched, api)
        return api

    @override
    def ohlcv_candle_limit(
        self, timeframe: str, candle_type: CandleType, since_ms: int | None = None
    ) -> int:
        limit = super().ohlcv_candle_limit(timeframe, candle_type, since_ms)
        if candle_type in [
            CandleType.MARK,
            CandleType.FUTURES,
            CandleType.FUNDING_RATE,
        ]:
            futures_time_range_limit = 90 * 24 * 60 * 60  # 90 days in seconds
            limit = min(limit, futures_time_range_limit // timeframe_to_seconds(timeframe))
        return limit
