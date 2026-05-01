import { useState, useEffect, useCallback, useRef } from 'react';

// Use environment variables for production, fallback to localhost for dev
const BASE_URL = import.meta.env.VITE_API_URL || '';
const API_URL = BASE_URL ? `${BASE_URL}/api` : '/api';

const getWsUrl = () => {
  if (BASE_URL) return BASE_URL.replace(/^http/, 'ws') + '/ws';
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}/ws`;
};

export function useBotData() {
  const [status, setStatus] = useState(null);
  const [portfolio, setPortfolio] = useState({ cash: 0, total_value: 0, unrealized_pnl: 0, realized_pnl: 0, positions: {} });
  const [trades, setTrades] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  
  // State Streams for Dashboard
  const [logs, setLogs] = useState([]);
  const [ticker, setTicker] = useState({});
  const [health, setHealth] = useState(null);
  const [error, setError] = useState(null);
  
  // Visual Analysis State
  const [marketHistory, setMarketHistory] = useState({});
  const [chartMarkers, setChartMarkers] = useState([]);
  
  // New: OHLCV candlestick data
  const [candleData, setCandleData] = useState({});
  
  // New: Strategy state, analytics, risk
  const [strategyState, setStrategyState] = useState({});
  const [analytics, setAnalytics] = useState(null);
  const [riskState, setRiskState] = useState(null);
  
  // Signal stats computed from WS events directly
  const [signalStats, setSignalStats] = useState({ total: 0, buys: 0, sells: 0, holds: 0 });
  
  const wsRef = useRef(null);

  const executeManualTrade = async (symbol, side, quantity) => {
    try {
      const res = await fetch(`${API_URL}/trade/manual`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol, side, quantity })
      });
      if (!res.ok) throw new Error('Manual trade failed');
      return await res.json();
    } catch (err) {
      console.error(err);
      throw err;
    }
  };

  const setKillSwitch = async (active) => {
    try {
      const res = await fetch(`${API_URL}/risk/kill`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ active })
      });
      if (!res.ok) throw new Error('Kill switch failed');
      return await res.json();
    } catch (err) {
      console.error(err);
      throw err;
    }
  };

  // Fetch initial data + periodic refresh
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statusRes, portRes, tradesRes] = await Promise.all([
          fetch(`${API_URL}/status`),
          fetch(`${API_URL}/portfolio`),
          fetch(`${API_URL}/trades`),
        ]);
        
        if (statusRes.ok) setStatus(await statusRes.json());
        if (portRes.ok) setPortfolio(await portRes.json());
        if (tradesRes.ok) {
            const data = await tradesRes.json();
            setTrades(data.trades || []);
        }
      } catch (err) {
        console.error("Failed to fetch initial data", err);
      }
    };

    const fetchExtras = async () => {
      try {
        const [stratRes, analyticsRes, riskRes, healthRes] = await Promise.all([
          fetch(`${API_URL}/strategies/state`).catch(() => null),
          fetch(`${API_URL}/analytics`).catch(() => null),
          fetch(`${API_URL}/risk/state`).catch(() => null),
          fetch(`${API_URL}/health`).catch(() => null),
        ]);
        if (stratRes?.ok) setStrategyState((await stratRes.json()).states || {});
        if (analyticsRes?.ok) setAnalytics((await analyticsRes.json()).metrics || {});
        if (riskRes?.ok) setRiskState(await riskRes.json());
        if (healthRes?.ok) {
          const h = await healthRes.json();
          // Only set if WS hasn't provided health yet
          setHealth(prev => prev || { status: h.status, details: h });
        }
      } catch (err) {
        console.error("Failed to fetch extras", err);
      }
    };

    // Fetch candle data for each symbol
    const fetchCandles = async () => {
      try {
        const statusRes = await fetch(`${API_URL}/status`);
        if (!statusRes.ok) return;
        const statusData = await statusRes.json();
        const symbols = statusData.symbols || [];
        for (const sym of symbols) {
          const encoded = encodeURIComponent(sym);
          const res = await fetch(`${API_URL}/candles/${encoded}`);
          if (res.ok) {
            const data = await res.json();
            if (data.candles?.length > 0) {
              setCandleData(prev => ({ ...prev, [sym]: data.candles }));
            }
          }
        }
      } catch (err) {
        console.error("Failed to fetch candles", err);
      }
    };

    fetchData();
    fetchExtras();
    fetchCandles();
    
    // Refresh loop every 5s as fallback
    const interval = setInterval(() => {
      fetchData();
      fetchExtras();
    }, 5000);
    // Candles less frequently
    const candleInterval = setInterval(fetchCandles, 10000);
    return () => { clearInterval(interval); clearInterval(candleInterval); };
  }, []);

  // Setup WebSocket for live updates
  useEffect(() => {
    let ws;
    let reconnectTimeout;
    
    const connect = () => {
      const url = getWsUrl();
      ws = new WebSocket(url);
      wsRef.current = ws;
      
      ws.onopen = () => {
        setIsConnected(true);
        console.log('WebSocket connected to', url);
      };
      
      ws.onclose = () => {
        setIsConnected(false);
        // Auto reconnect
        reconnectTimeout = setTimeout(connect, 3000);
      };
      
      ws.onerror = (err) => {
        console.error('WebSocket error:', err);
      };
      
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          const t = msg.type;
          const d = msg.data;

          // Standard refresh on portfolio-changing events
          if (t === 'portfolio' || t === 'fill') {
            fetch(`${API_URL}/portfolio`).then(res => res.json()).then(data => setPortfolio(data)).catch(() => {});
            fetch(`${API_URL}/trades`).then(res => res.json()).then(data => setTrades(data.trades || [])).catch(() => {});
          }

          // 1. Ticker updates and Market History + Candle Data
          if (t === 'market_data') {
            setTicker(prev => ({ ...prev, [d.symbol]: d.close }));
            const timestamp = new Date(d.timestamp).toLocaleTimeString([], { hour12: false });
            
            // Simple line chart history
            setMarketHistory(prev => {
              const symHist = prev[d.symbol] || [];
              const updated = [...symHist, { time: timestamp, price: d.close }].slice(-120);
              return { ...prev, [d.symbol]: updated };
            });
            
            // OHLCV candle data for TradingView chart
            const candleTime = Math.floor(new Date(d.timestamp).getTime() / 1000);
            setCandleData(prev => {
              const symCandles = prev[d.symbol] || [];
              const newCandle = {
                time: candleTime,
                open: d.open,
                high: d.high,
                low: d.low,
                close: d.close,
              };
              // Deduplicate by time
              const existing = symCandles.findIndex(c => c.time === candleTime);
              let updated;
              if (existing >= 0) {
                updated = [...symCandles];
                updated[existing] = newCandle;
              } else {
                updated = [...symCandles, newCandle].slice(-500);
              }
              return { ...prev, [d.symbol]: updated };
            });
          }

          // 2. Health Heartbeat
          if (t === 'heartbeat') {
            setHealth(d);
          }

          // 3. Algorithmic Log Terminal & Markers — each type in its own try/catch
          if (t === 'signal') {
            try {
              const side = (d.side || '').toUpperCase();
              const text = `[SIGNAL] ${side} ${d.symbol} — ${d.reason || d.strategy_name} (strength: ${(d.strength * 100).toFixed(0)}%)`;
              const timestamp = new Date().toLocaleTimeString([], { hour12: false });
              setLogs(prev => [...prev.slice(-99), { id: Date.now() + Math.random(), time: timestamp, text, level: 'info' }]);
              setChartMarkers(prev => [...prev.slice(-99), { time: timestamp, action: 'SIGNAL_' + side, symbol: d.symbol }]);
              // Update signal stats
              setSignalStats(prev => ({
                total: prev.total + 1,
                buys: prev.buys + (side === 'BUY' ? 1 : 0),
                sells: prev.sells + (side === 'SELL' ? 1 : 0),
                holds: prev.holds + (side === 'HOLD' ? 1 : 0),
              }));
            } catch (e) { console.error('Signal parse error:', e); }
          }

          if (t === 'order') {
            try {
              const text = `[ORDER] ${(d.side || '').toUpperCase()} ${d.symbol} qty=${d.quantity} ${d.order_type}`;
              const timestamp = new Date().toLocaleTimeString([], { hour12: false });
              setLogs(prev => [...prev.slice(-99), { id: Date.now() + Math.random(), time: timestamp, text, level: 'warning' }]);
            } catch (e) { console.error('Order parse error:', e); }
          }

          if (t === 'fill') {
            try {
              const price = d.fill_price || d.price || 0;
              const text = `[FILL] ${(d.side || '').toUpperCase()} ${d.symbol} @ $${Number(price).toFixed(2)}`;
              const timestamp = new Date().toLocaleTimeString([], { hour12: false });
              setLogs(prev => [...prev.slice(-99), { id: Date.now() + Math.random(), time: timestamp, text, level: 'success' }]);
              setChartMarkers(prev => [...prev.slice(-99), { time: timestamp, action: 'FILL_' + (d.side || '').toUpperCase(), symbol: d.symbol, price }]);
            } catch (e) { console.error('Fill parse error:', e); }
          }

          if (t === 'alert') {
            try {
              const text = `[ALERT] ${d.title}: ${d.message}`;
              const level = d.level === 'critical' ? 'error' : 'warning';
              const timestamp = new Date().toLocaleTimeString([], { hour12: false });
              setLogs(prev => [...prev.slice(-99), { id: Date.now() + Math.random(), time: timestamp, text, level }]);
            } catch (e) { console.error('Alert parse error:', e); }
          }

          if (t === 'error') {
            try {
              const text = `[ERROR] ${d.error_type}: ${d.message}`;
              const timestamp = new Date().toLocaleTimeString([], { hour12: false });
              setLogs(prev => [...prev.slice(-99), { id: Date.now() + Math.random(), time: timestamp, text, level: 'error' }]);
            } catch (e) { console.error('Error parse error:', e); }
          }

        } catch (err) {
          console.error("Error parsing websocket message", err);
        }
      };
    };
    
    connect();

    return () => {
      clearTimeout(reconnectTimeout);
      if (ws) ws.close();
    };
  }, []);

  return {
    status, portfolio, trades, isConnected, logs, ticker, health, error,
    marketHistory, chartMarkers, candleData, strategyState, analytics, riskState,
    signalStats, executeManualTrade, setKillSwitch,
  };
}
