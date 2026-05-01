import { useEffect, useRef, useState } from 'react';
import { createChart, ColorType } from 'lightweight-charts';
import { LineChart } from 'lucide-react';

const TradingChart = ({ candleData, chartMarkers, symbols }) => {
  const chartRef = useRef(null);
  const containerRef = useRef(null);
  const seriesRef = useRef(null);
  const markerSeriesRef = useRef({});
  const [activeSymbol, setActiveSymbol] = useState(symbols[0] || 'BTC/USDT');

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#6b7280',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: 'rgba(255,255,255,0.03)' },
        horzLines: { color: 'rgba(255,255,255,0.03)' },
      },
      crosshair: {
        mode: 0,
        vertLine: { color: 'rgba(99,102,241,0.3)', width: 1, style: 2 },
        horzLine: { color: 'rgba(99,102,241,0.3)', width: 1, style: 2 },
      },
      timeScale: {
        borderColor: 'rgba(255,255,255,0.08)',
        timeVisible: true,
        secondsVisible: false,
      },
      rightPriceScale: {
        borderColor: 'rgba(255,255,255,0.08)',
      },
      handleScroll: { vertTouchDrag: false },
    });

    chartRef.current = chart;

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#10b981',
      downColor: '#ef4444',
      borderUpColor: '#10b981',
      borderDownColor: '#ef4444',
      wickUpColor: '#10b981',
      wickDownColor: '#ef4444',
    });
    seriesRef.current = candleSeries;

    // Resize observer
    const resizeObserver = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    });
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  // Update candle data when it changes
  useEffect(() => {
    if (!seriesRef.current) return;
    const data = candleData[activeSymbol];
    if (data && data.length > 0) {
      // Sort by time, deduplicate
      const sorted = [...data].sort((a, b) => a.time - b.time);
      const deduped = [];
      const seen = new Set();
      for (const c of sorted) {
        if (!seen.has(c.time)) {
          seen.add(c.time);
          deduped.push(c);
        }
      }
      try {
        seriesRef.current.setData(deduped);
      } catch (e) {
        // On incremental update errors, just log
        console.debug('Chart data update:', e.message);
      }
    }
  }, [candleData, activeSymbol]);

  // Add trade markers
  useEffect(() => {
    if (!seriesRef.current) return;
    const symbolMarkers = chartMarkers
      .filter(m => m.symbol === activeSymbol && m.price)
      .map(m => ({
        time: Math.floor(new Date().getTime() / 1000), // approximate
        position: m.action.includes('BUY') ? 'belowBar' : 'aboveBar',
        color: m.action.includes('BUY') ? '#10b981' : '#ef4444',
        shape: m.action.includes('BUY') ? 'arrowUp' : 'arrowDown',
        text: m.action.includes('FILL') ? (m.action.includes('BUY') ? 'BUY' : 'SELL') : '',
      }));
    
    if (symbolMarkers.length > 0) {
      try {
        seriesRef.current.setMarkers(symbolMarkers);
      } catch (e) {
        // Markers might fail if times don't match candles
      }
    }
  }, [chartMarkers, activeSymbol]);

  const hasData = candleData[activeSymbol]?.length > 0;

  return (
    <div className="glass-panel">
      <div className="section-header">
        <div className="section-title"><LineChart size={16} /> Trading Chart</div>
        <select
          value={activeSymbol}
          onChange={e => setActiveSymbol(e.target.value)}
          style={{
            background: 'rgba(255,255,255,0.1)', border: 'none',
            color: '#fff', padding: '4px 10px', borderRadius: 6, fontSize: '0.75rem'
          }}
        >
          {symbols.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>
      <div style={{ position: 'relative' }}>
        <div ref={containerRef} style={{ width: '100%', height: 340 }} />
        {!hasData && (
          <div style={{
            position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'var(--text-muted)', fontSize: '0.85rem', flexDirection: 'column', gap: '0.5rem'
          }}>
            <LineChart size={32} style={{ opacity: 0.3 }} />
            Loading candlestick data...
          </div>
        )}
      </div>
    </div>
  );
};

export default TradingChart;
