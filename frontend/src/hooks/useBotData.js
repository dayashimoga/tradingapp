import { useState, useEffect } from 'react';

const API_URL = 'http://127.0.0.1:8000/api';
const WS_URL = 'ws://127.0.0.1:8000/ws';

export function useBotData() {
  const [status, setStatus] = useState(null);
  const [portfolio, setPortfolio] = useState({ cash: 0, total_value: 0, unrealized_pnl: 0, positions: {} });
  const [trades, setTrades] = useState([]);
  const [isConnected, setIsConnected] = useState(false);

  // Fetch initial data
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
            setTrades(data.trades);
        }
      } catch (err) {
        console.error("Failed to fetch initial data", err);
      }
    };
    fetchData();
    
    // Refresh loop every 5s as fallback
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  // Setup WebSocket for live updates
  useEffect(() => {
    let ws;
    let reconnectTimeout;
    
    const connect = () => {
      ws = new WebSocket(WS_URL);
      
      ws.onopen = () => setIsConnected(true);
      
      ws.onclose = () => {
        setIsConnected(false);
        // Auto reconnect
        reconnectTimeout = setTimeout(connect, 3000);
      };
      
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'portfolio' || msg.type === 'fill' || msg.type === 'signal') {
            // Re-fetch everything on critical events
            fetch(`${API_URL}/portfolio`).then(res => res.json()).then(data => setPortfolio(data));
            fetch(`${API_URL}/trades`).then(res => res.json()).then(data => setTrades(data.trades));
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

  return { status, portfolio, trades, isConnected };
}
