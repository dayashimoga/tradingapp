import { Activity, ArrowDownRight, ArrowUpRight, Box, LineChart, Wallet } from 'lucide-react';
import './App.css';
import { useBotData } from './hooks/useBotData';

function App() {
  const { status, portfolio, trades, isConnected } = useBotData();

  const isRunning = status?.status === 'running';
  const pnlIsPositive = portfolio.unrealized_pnl >= 0;

  return (
    <div className="app-container">
      {/* Header */}
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
          <div className="badge badge-neutral">
            {status?.mode || 'Loading...'} Mode
          </div>
          <div className={`badge ${isRunning ? 'badge-success' : 'badge-danger'}`}>
            {isRunning ? 'RUNNING' : 'STOPPED'}
          </div>
        </div>
      </header>

      {/* Main Stats Grid */}
      <div className="dashboard-grid">
        <div className="glass-panel stat-card">
          <div className="flex-between">
            <span className="stat-label">Total Portfolio Value</span>
            <Wallet className="text-secondary" size={20} />
          </div>
          <span className="stat-value text-gradient">
            ${portfolio.total_value.toFixed(2)}
          </span>
          <span className="text-sm text-muted">Cash Available: ${portfolio.cash.toFixed(2)}</span>
        </div>

        <div className="glass-panel stat-card">
          <div className="flex-between">
            <span className="stat-label">Unrealized P&L</span>
            <LineChart className="text-secondary" size={20} />
          </div>
          <div className="flex-between">
            <span className={`stat-value ${pnlIsPositive ? 'text-success' : 'text-danger'}`}>
              {pnlIsPositive ? '+' : ''}${portfolio.unrealized_pnl.toFixed(2)}
            </span>
            {pnlIsPositive ? <ArrowUpRight className="text-success" /> : <ArrowDownRight className="text-danger" />}
          </div>
        </div>

        <div className="glass-panel stat-card">
          <div className="flex-between">
            <span className="stat-label">Active Symbols</span>
            <Box className="text-secondary" size={20} />
          </div>
          <span className="stat-value">{status?.symbols?.length || 0}</span>
          <span className="text-sm text-muted">Monitoring pairs</span>
        </div>
      </div>

      {/* Two Column Layout for Tables */}
      <div className="dashboard-grid" style={{ gridTemplateColumns: '2fr 1fr' }}>
        
        {/* Open Positions */}
        <div className="glass-panel">
          <h2 style={{ marginBottom: '1.5rem', fontSize: '1.25rem' }}>Open Positions</h2>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Quantity</th>
                  <th>Entry Price</th>
                  <th>Current Price</th>
                  <th>Unrealized P&L</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(portfolio.positions || {}).length === 0 ? (
                  <tr>
                    <td colSpan="5" className="text-center text-muted" style={{ padding: '2rem' }}>
                      No open positions currently.
                    </td>
                  </tr>
                ) : (
                  Object.entries(portfolio.positions).map(([symbol, pos]) => (
                    <tr key={symbol}>
                      <td style={{ fontWeight: '600' }}>{symbol}</td>
                      <td>{pos.quantity.toFixed(4)}</td>
                      <td>${pos.avg_entry_price.toFixed(2)}</td>
                      <td>${pos.current_price.toFixed(2)}</td>
                      <td className={pos.unrealized_pnl >= 0 ? 'text-success' : 'text-danger'} style={{ fontWeight: '500' }}>
                        {pos.unrealized_pnl >= 0 ? '+' : ''}${pos.unrealized_pnl.toFixed(2)} 
                        <span style={{ fontSize: '0.8em', marginLeft: '4px' }}>
                          ({(pos.pnl_pct * 100).toFixed(2)}%)
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Trade Ledger */}
        <div className="glass-panel">
          <h2 style={{ marginBottom: '1.5rem', fontSize: '1.25rem' }}>Recent Fills</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {trades.length === 0 ? (
              <div className="text-center text-muted" style={{ padding: '2rem' }}>
                No recent trades.
              </div>
            ) : (
              trades.slice(0, 8).map((trade, i) => (
                <div key={i} className="flex-between" style={{ paddingBottom: '0.75rem', borderBottom: '1px solid var(--border-color)' }}>
                  <div>
                    <div style={{ fontWeight: '600', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span className={trade.side.toUpperCase() === 'BUY' ? 'text-success' : 'text-danger'}>
                        {trade.side.toUpperCase()}
                      </span>
                      {trade.symbol}
                    </div>
                    <div className="text-xs text-muted" style={{ marginTop: '0.25rem' }}>
                      {trade.strategy_name}
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div>${trade.price.toFixed(2)}</div>
                    <div className="text-xs text-muted">Vol: {trade.quantity.toFixed(4)}</div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

      </div>
    </div>
  );
}

export default App;
