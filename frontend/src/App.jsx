import { useState, useEffect, useRef } from 'react';
import {
  Activity, ArrowDownRight, ArrowUpRight, BarChart3, Box,
  Cpu, DollarSign, LineChart, List, Radio, Shield, Terminal,
  TrendingUp, Wallet, Zap, AlertTriangle, Brain, Gauge
} from 'lucide-react';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, BarChart, Bar, Cell
} from 'recharts';
import './App.css';
import { useBotData } from './hooks/useBotData';
import TradingChart from './components/TradingChart';

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: 'rgba(15,17,26,0.95)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, padding: '6px 10px', fontSize: '0.72rem', zIndex: 100 }}>
      <div style={{ color: '#a1a6b8' }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color || '#818cf8', fontWeight: 600 }}>{p.name}: ${p.value?.toFixed(2)}</div>
      ))}
    </div>
  );
};

const ManualTradeTerminal = ({ symbols, executeManualTrade }) => {
  const [symbol, setSymbol] = useState(symbols[0] || 'BTC/USDT');
  const [side, setSide] = useState('buy');
  const [qty, setQty] = useState('');
  const [loading, setLoading] = useState(false);
  const handleTrade = async () => {
    if (!qty || parseFloat(qty) <= 0) return alert('Enter valid quantity');
    setLoading(true);
    try { await executeManualTrade(symbol, side, parseFloat(qty)); setQty(''); }
    catch (e) { alert('Manual trade failed: ' + e.message); }
    setLoading(false);
  };
  return (
    <div className="glass-panel" style={{ marginBottom: '1rem' }}>
      <div className="section-header"><div className="section-title"><Terminal size={16} /> Manual Override</div></div>
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem' }}>
        <select value={symbol} onChange={e => setSymbol(e.target.value)} style={{ flex: 1, background: 'rgba(255,255,255,0.1)', border: 'none', color: '#fff', padding: '4px', borderRadius: 4 }}>
          {symbols.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={side} onChange={e => setSide(e.target.value)} style={{ width: 80, background: 'rgba(255,255,255,0.1)', border: 'none', color: '#fff', padding: '4px', borderRadius: 4 }}>
          <option value="buy">BUY</option><option value="sell">SELL</option>
        </select>
      </div>
      <div style={{ display: 'flex', gap: '0.5rem' }}>
        <input type="number" placeholder="Qty" value={qty} onChange={e => setQty(e.target.value)} style={{ flex: 1, background: 'rgba(255,255,255,0.1)', border: 'none', color: '#fff', padding: '4px', borderRadius: 4 }} />
        <button onClick={handleTrade} disabled={loading} style={{ background: side === 'buy' ? 'var(--success)' : 'var(--danger)', color: '#fff', border: 'none', padding: '4px 12px', borderRadius: 4, cursor: 'pointer', fontWeight: 600 }}>
          {loading ? '...' : 'EXECUTE'}
        </button>
      </div>
    </div>
  );
};

function App() {
  const {
    status, portfolio, trades, isConnected, logs, ticker, health, marketHistory,
    chartMarkers, candleData, strategyState, analytics, riskState, signalStats,
    executeManualTrade, setKillSwitch
  } = useBotData();
  const terminalRef = useRef(null);
  const [portfolioHistory, setPortfolioHistory] = useState([]);

  useEffect(() => {
    if (portfolio.total_value > 0) {
      const now = new Date();
      setPortfolioHistory(prev => {
        const next = [...prev, { time: now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }), value: portfolio.total_value, pnl: portfolio.unrealized_pnl }];
        return next.slice(-60);
      });
    }
  }, [portfolio.total_value]);

  useEffect(() => {
    if (terminalRef.current) terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
  }, [logs]);

  const isRunning = status?.status === 'running';
  const pnlIsPositive = portfolio.unrealized_pnl >= 0;
  const symbols = status?.symbols || [];
  const tickerEntries = Object.entries(ticker);
  const signalChartData = [
    { name: 'BUY', value: signalStats.buys, color: '#10b981' },
    { name: 'SELL', value: signalStats.sells, color: '#ef4444' },
    { name: 'HOLD', value: signalStats.holds, color: '#6366f1' },
  ];
  const strategyEntries = Object.entries(strategyState);

  return (
    <div className="app-container">
      {/* HEADER */}
      <header className="header">
        <div className="header-title">
          <Activity className="text-gradient" size={28} />
          <h1><span className="text-gradient">Autonomy</span> Trading Bot</h1>
        </div>
        <div className="status-bar">
          <div className="flex-center" style={{ gap: '0.5rem' }}>
            <span className={`pulse-dot ${isConnected ? 'active' : 'inactive'}`}></span>
            <span className="text-muted text-sm">{isConnected ? 'WS Connected' : 'Disconnected'}</span>
          </div>
          <button 
            className={`mode-toggle ${status?.mode === 'live' ? 'live' : 'paper'}`}
            onClick={async () => {
              const currentMode = status?.mode || 'paper';
              const newMode = currentMode === 'live' ? 'paper' : 'live';
              if (newMode === 'live' && !window.confirm("WARNING: You are about to switch to LIVE trading. Real funds will be used. Proceed?")) return;
              try {
                const res = await fetch('http://localhost:8000/api/bot/mode', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ mode: newMode })
                });
                const data = await res.json();
                alert(data.message);
                if (data.message.includes("restarting")) {
                  setTimeout(() => window.location.reload(), 3000);
                }
              } catch (e) {
                console.error(e);
                alert("Failed to switch mode. Ensure backend is running.");
              }
            }}
            title="Click to toggle Live/Paper mode"
          >
            {status?.mode === 'live' ? 'LIVE MODE' : 'PAPER MODE'}
          </button>
          <div className={`badge ${isRunning ? 'badge-success' : 'badge-danger'}`}>
            {isRunning ? (status?.state === 'TRANSACTING' ? 'TRANSACTING' : 'ANALYZING') : 'STOPPED'}
          </div>
        </div>
      </header>

      {/* TICKER */}
      <div className="ticker-bar">
        <div className="ticker-content">
          {tickerEntries.length > 0 ? (
            [...tickerEntries, ...tickerEntries].map(([sym, price], i) => (
              <span key={i} className="ticker-item">
                <Radio size={10} style={{ color: 'var(--success)' }} />
                <span className="ticker-symbol">{sym}</span>
                <span className="ticker-price">${typeof price === 'number' ? price.toFixed(2) : price}</span>
              </span>
            ))
          ) : (
            symbols.map((sym, i) => (
              <span key={i} className="ticker-item">
                <Radio size={10} style={{ color: 'var(--text-muted)' }} />
                <span className="ticker-symbol">{sym}</span>
                <span className="ticker-price" style={{ color: 'var(--text-muted)' }}>Waiting...</span>
              </span>
            ))
          )}
        </div>
      </div>

      {/* STAT CARDS */}
      <div className="stats-row">
        <div className="glass-panel stat-card">
          <div className="flex-between"><span className="stat-label">Portfolio Value</span><Wallet size={18} style={{ color: 'var(--accent-primary)' }} /></div>
          <span className="stat-value text-gradient">${portfolio.total_value.toFixed(2)}</span>
          <span className="stat-sub">Cash: ${portfolio.cash.toFixed(2)}</span>
        </div>
        <div className="glass-panel stat-card">
          <div className="flex-between"><span className="stat-label">Unrealized P&L</span>{pnlIsPositive ? <ArrowUpRight size={18} className="text-success" /> : <ArrowDownRight size={18} className="text-danger" />}</div>
          <span className={`stat-value ${pnlIsPositive ? 'text-success' : 'text-danger'}`}>{pnlIsPositive ? '+' : ''}${portfolio.unrealized_pnl.toFixed(2)}</span>
          <span className="stat-sub">{portfolio.total_value > 0 ? ((portfolio.unrealized_pnl / portfolio.total_value) * 100).toFixed(2) : '0.00'}% return</span>
        </div>
        <div className="glass-panel stat-card">
          <div className="flex-between"><span className="stat-label">Signals Generated</span><Zap size={18} style={{ color: '#fbbf24' }} /></div>
          <span className="stat-value">{signalStats.total}</span>
          <span className="stat-sub">{signalStats.buys} buy / {signalStats.sells} sell</span>
        </div>
        <div className="glass-panel stat-card">
          <div className="flex-between"><span className="stat-label">Active Symbols</span><Box size={18} style={{ color: 'var(--accent-secondary)' }} /></div>
          <span className="stat-value">{symbols.length}</span>
          <span className="stat-sub">{symbols.join(', ') || 'None'}</span>
        </div>
      </div>

      {/* MAIN GRID */}
      <div className="main-grid">
        <div className="side-stack">
          {/* Portfolio Performance */}
          <div className="glass-panel panel-portfolio">
            <div className="section-header">
              <div className="section-title"><TrendingUp size={16} /> Portfolio Performance</div>
              <span className="badge badge-neutral">{portfolioHistory.length} snapshots</span>
            </div>
            <div className="chart-wrapper">
              {portfolioHistory.length > 1 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={portfolioHistory}>
                    <defs><linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#818cf8" stopOpacity={0.3} /><stop offset="95%" stopColor="#818cf8" stopOpacity={0} /></linearGradient></defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                    <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#6b7280' }} tickLine={false} axisLine={false} />
                    <YAxis tick={{ fontSize: 10, fill: '#6b7280' }} tickLine={false} axisLine={false} domain={['auto', 'auto']} tickFormatter={v => `$${v}`} />
                    <Tooltip content={<CustomTooltip />} />
                    <Area type="monotone" dataKey="value" stroke="#818cf8" strokeWidth={2} fill="url(#colorValue)" dot={false} />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="empty-state"><TrendingUp size={32} /><br />Collecting portfolio data...</div>
              )}
            </div>
          </div>

          {/* TradingView Candlestick Chart */}
          <div className="panel-chart" style={{ display: 'flex', flexDirection: 'column', gap: '1rem', minHeight: '500px' }}>
            <TradingChart candleData={candleData} chartMarkers={chartMarkers} symbols={symbols.length > 0 ? symbols : ['BTC/USDT', 'ETH/USDT']} />
          </div>

          {/* Open Positions */}
          <div className="glass-panel panel-positions">
            <div className="section-header">
              <div className="section-title"><List size={16} /> Open Positions</div>
              <span className="badge badge-neutral">{Object.keys(portfolio.positions || {}).length} active</span>
            </div>
            <div className="table-container">
              <table>
                <thead><tr><th>Symbol</th><th>Qty</th><th>Entry</th><th>Current</th><th>Value</th><th>P&L</th></tr></thead>
                <tbody>
                  {Object.entries(portfolio.positions || {}).length === 0 ? (
                    <tr><td colSpan="6" className="empty-state">No open positions.</td></tr>
                  ) : (
                    Object.entries(portfolio.positions).map(([symbol, pos]) => (
                      <tr key={symbol}>
                        <td style={{ fontWeight: 600 }}>{symbol}</td>
                        <td>{pos.quantity?.toFixed(4)}</td>
                        <td>${pos.avg_entry_price?.toFixed(2)}</td>
                        <td>${pos.current_price?.toFixed(2)}</td>
                        <td>${pos.market_value?.toFixed(2)}</td>
                        <td className={pos.unrealized_pnl >= 0 ? 'text-success' : 'text-danger'} style={{ fontWeight: 600 }}>
                          {pos.unrealized_pnl >= 0 ? '+' : ''}${pos.unrealized_pnl?.toFixed(2)}
                          <span style={{ fontSize: '0.75em', marginLeft: 4, opacity: 0.7 }}>({(pos.pnl_pct * 100)?.toFixed(2)}%)</span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* RIGHT SIDEBAR */}
        <div className="side-stack">
          <div className="panel-manual">
            <ManualTradeTerminal symbols={symbols.length > 0 ? symbols : ['BTC/USDT', 'ETH/USDT']} executeManualTrade={executeManualTrade} />
          </div>

          {/* Strategy Brain */}
          <div className="glass-panel panel-strategy">
            <div className="section-header">
              <div className="section-title"><Brain size={16} /> Strategy Brain</div>
            </div>
            {strategyEntries.length > 0 ? strategyEntries.map(([name, s]) => (
              <div key={name} style={{ marginBottom: '0.75rem' }}>
                <div className="flex-between" style={{ marginBottom: '0.5rem' }}>
                  <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>{name}</span>
                  <span className="badge badge-neutral">{s.type || 'Strategy'}</span>
                </div>
                <div className="health-grid">
                  {s.rsi !== undefined && (
                    <div className="health-item">
                      <span className="health-label">RSI</span>
                      <span className="health-value" style={{ color: s.zone === 'oversold' ? '#10b981' : s.zone === 'overbought' ? '#ef4444' : '#818cf8' }}>{s.rsi ?? '—'}</span>
                    </div>
                  )}
                  {s.fast_sma !== undefined && (
                    <>
                      <div className="health-item"><span className="health-label">Fast SMA</span><span className="health-value">{s.fast_sma ?? '—'}</span></div>
                      <div className="health-item"><span className="health-label">Slow SMA</span><span className="health-value">{s.slow_sma ?? '—'}</span></div>
                      <div className="health-item">
                        <span className="health-label">Crossover</span>
                        <span className="health-value" style={{ color: s.crossover === 'golden' ? '#10b981' : s.crossover === 'death' ? '#ef4444' : '#6b7280', fontSize: '0.85rem' }}>{(s.crossover || '—').toUpperCase()}</span>
                      </div>
                    </>
                  )}
                  {s.upper_band !== undefined && (
                    <>
                      <div className="health-item"><span className="health-label">Upper Band</span><span className="health-value" style={{ fontSize: '0.85rem' }}>${s.upper_band ?? '—'}</span></div>
                      <div className="health-item"><span className="health-label">Lower Band</span><span className="health-value" style={{ fontSize: '0.85rem' }}>${s.lower_band ?? '—'}</span></div>
                    </>
                  )}
                  <div className="health-item"><span className="health-label">Data Points</span><span className="health-value">{s.data_points ?? 0}</span></div>
                  <div className="health-item"><span className="health-label">Warmed Up</span><span className="health-value" style={{ color: s.warmed_up ? '#10b981' : '#ef4444' }}>{s.warmed_up ? 'YES' : 'NO'}</span></div>
                </div>
              </div>
            )) : (
              <div className="empty-state"><Brain size={24} /><br />Loading strategy state...</div>
            )}
          </div>

          {/* System Health */}
          <div className="glass-panel panel-health">
            <div className="section-header">
              <div className="section-title"><Cpu size={16} /> System Health</div>
              <span className={`badge ${health?.status === 'healthy' ? 'badge-success' : 'badge-danger'}`}>{health?.status || 'INIT'}</span>
            </div>
            <div className="health-grid">
              <div className="health-item"><span className="health-label">Event Throughput</span><span className="health-value">{health?.details?.event_count ?? health?.event_count ?? '—'}</span></div>
              <div className="health-item">
                <span className="health-label">Dead Letters</span>
                <span className="health-value" style={{ color: (health?.details?.dead_letters || health?.dead_letters || 0) > 0 ? 'var(--danger)' : 'var(--success)' }}>{health?.details?.dead_letters ?? health?.dead_letters ?? '—'}</span>
              </div>
              <div className="health-item"><span className="health-label">Strategies</span><span className="health-value">{health?.details?.strategies ?? health?.strategies ?? '—'}</span></div>
              <div className="health-item"><span className="health-label">Data Feeds</span><span className="health-value">{health?.details?.data_feeds ?? health?.data_feeds ?? '—'}</span></div>
            </div>
          </div>

          {/* Signal Analysis */}
          <div className="glass-panel panel-signal">
            <div className="section-header"><div className="section-title"><BarChart3 size={16} /> Signal Analysis</div></div>
            {signalStats.total > 0 ? (
              <>
                <ResponsiveContainer width="100%" height={120}>
                  <BarChart data={signalChartData}>
                    <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#6b7280' }} tickLine={false} axisLine={false} />
                    <YAxis tick={{ fontSize: 10, fill: '#6b7280' }} tickLine={false} axisLine={false} allowDecimals={false} />
                    <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                      {signalChartData.map((entry, i) => <Cell key={i} fill={entry.color} fillOpacity={0.8} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
                <div style={{ marginTop: '0.5rem' }}>
                  <div className="flex-between" style={{ fontSize: '0.75rem' }}>
                    <span className="text-muted">Signal Confidence</span>
                    <span style={{ color: 'var(--success)', fontWeight: 600 }}>{((signalStats.buys + signalStats.sells) / signalStats.total * 100).toFixed(0)}% actionable</span>
                  </div>
                  <div className="accuracy-bar-track"><div className="accuracy-bar-fill" style={{ width: `${(signalStats.buys + signalStats.sells) / signalStats.total * 100}%` }} /></div>
                </div>
              </>
            ) : (
              <div className="empty-state"><Shield size={24} /><br />No signals captured yet.</div>
            )}
          </div>

          {/* Risk Dashboard */}
          {riskState && (
            <div className="glass-panel panel-risk">
              <div className="section-header">
                <div className="section-title"><AlertTriangle size={16} /> Risk Management</div>
                <button
                  onClick={() => setKillSwitch(!riskState.kill_switch)}
                  style={{
                    background: riskState.kill_switch || riskState.circuit_breaker_active ? '#10b981' : '#ef4444',
                    color: '#fff', border: 'none', padding: '4px 12px', borderRadius: 6,
                    cursor: 'pointer', fontWeight: 700, fontSize: '0.7rem', textTransform: 'uppercase'
                  }}
                >
                  {riskState.kill_switch || riskState.circuit_breaker_active ? '▶ RESUME' : '⏸ KILL SWITCH'}
                </button>
              </div>
              <div className="health-grid">
                <div className="health-item"><span className="health-label">Daily P&L</span><span className="health-value" style={{ color: riskState.daily_pnl >= 0 ? '#10b981' : '#ef4444' }}>${riskState.daily_pnl?.toFixed(2)}</span></div>
                <div className="health-item"><span className="health-label">Daily Loss Limit</span><span className="health-value">${riskState.max_daily_loss}</span></div>
                <div className="health-item"><span className="health-label">Open Positions</span><span className="health-value">{riskState.open_positions}/{riskState.max_open_positions}</span></div>
                <div className="health-item"><span className="health-label">Approved/Rejected</span><span className="health-value">{riskState.approved_count}/{riskState.rejected_count}</span></div>
              </div>
              <div style={{ marginTop: '0.5rem' }}>
                <div className="flex-between" style={{ fontSize: '0.72rem' }}>
                  <span className="text-muted">Daily Loss Usage</span>
                  <span style={{ color: riskState.daily_loss_pct > 80 ? '#ef4444' : '#10b981', fontWeight: 600 }}>{riskState.daily_loss_pct?.toFixed(0)}%</span>
                </div>
                <div className="accuracy-bar-track"><div className="accuracy-bar-fill" style={{ width: `${Math.min(riskState.daily_loss_pct || 0, 100)}%`, background: riskState.daily_loss_pct > 80 ? '#ef4444' : 'linear-gradient(90deg, var(--accent-primary), var(--success))' }} /></div>
              </div>
            </div>
          )}

          {/* Analytics */}
          {analytics && analytics.total_trades > 0 && (
            <div className="glass-panel panel-analytics">
              <div className="section-header"><div className="section-title"><Gauge size={16} /> Performance Analytics</div></div>
              <div className="health-grid">
                <div className="health-item"><span className="health-label">Total Return</span><span className="health-value" style={{ color: analytics.total_return_pct >= 0 ? '#10b981' : '#ef4444' }}>{analytics.total_return_pct}%</span></div>
                <div className="health-item"><span className="health-label">Win Rate</span><span className="health-value">{analytics.win_rate}%</span></div>
                <div className="health-item"><span className="health-label">Profit Factor</span><span className="health-value">{analytics.profit_factor}</span></div>
                <div className="health-item"><span className="health-label">Max Drawdown</span><span className="health-value" style={{ color: '#ef4444' }}>{analytics.max_drawdown_pct}%</span></div>
                <div className="health-item"><span className="health-label">Sharpe Ratio</span><span className="health-value">{analytics.sharpe_ratio}</span></div>
                <div className="health-item"><span className="health-label">Sortino Ratio</span><span className="health-value">{analytics.sortino_ratio}</span></div>
              </div>
            </div>
          )}

          {/* Trade Ledger */}
          <div className="glass-panel panel-ledger">
            <div className="section-header">
              <div className="section-title"><DollarSign size={16} /> Trade Ledger</div>
              <span className="badge badge-neutral">{trades.length} total</span>
            </div>
            <div style={{ maxHeight: 280, overflowY: 'auto' }}>
              {trades.length === 0 ? (
                <div className="empty-state"><DollarSign size={24} /><br />No trades executed yet.</div>
              ) : (
                trades.slice(0, 20).map((trade, i) => (
                  <div key={i} className="trade-item" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span className={`trade-side ${trade.side?.toLowerCase() === 'buy' ? 'buy' : 'sell'}`}>{trade.side}</span>
                        <div>
                          <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{trade.symbol}</div>
                          <div className="text-muted" style={{ fontSize: '0.7rem' }}>{trade.strategy_name}</div>
                        </div>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>${trade.price?.toFixed(2)} <span className="text-muted">×{trade.quantity?.toFixed(4)}</span></div>
                        {trade.side?.toLowerCase() === 'sell' && trade.pnl !== undefined && (
                          <div className={trade.pnl >= 0 ? 'text-success' : 'text-danger'} style={{ fontSize: '0.75rem', fontWeight: 600 }}>PNL: {trade.pnl >= 0 ? '+' : ''}${trade.pnl.toFixed(2)}</div>
                        )}
                      </div>
                    </div>
                    {(trade.reason || (trade.metadata && Object.keys(trade.metadata).length > 0)) && (
                      <div style={{ marginTop: '0.5rem', padding: '0.5rem', background: 'rgba(0,0,0,0.2)', borderRadius: 4, fontSize: '0.7rem' }}>
                        {trade.reason && <div style={{ color: '#fbbf24', marginBottom: 2 }}>Analysis: {trade.reason}</div>}
                        {trade.metadata && Object.keys(trade.metadata).length > 0 && (
                          <div style={{ color: '#a1a6b8', whiteSpace: 'pre-wrap' }}>{JSON.stringify(trade.metadata).replace(/["{}]/g, '')}</div>
                        )}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ALGORITHMIC FEED */}
      <div className="glass-panel panel-algo">
        <div className="section-header">
          <div className="section-title"><Terminal size={16} /> Algorithmic Feed</div>
          <span className="badge badge-neutral">{logs.length} events</span>
        </div>
        <div className="terminal" ref={terminalRef}>
          {logs.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', padding: '1rem', textAlign: 'center' }}>⏳ Waiting for signals, orders, and alerts from the engine...</div>
          ) : (
            logs.map(log => (
              <div key={log.id} className="terminal-line">
                <span className="terminal-time">{log.time}</span>
                <span className={`terminal-text ${log.level}`}>{log.text}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
