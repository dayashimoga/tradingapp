"""Unit tests for manual trade override."""

import pytest
from fastapi.testclient import TestClient

from tradingbot.api.main import app, engine, load_config, _build_engine
from tradingbot.core.events import EventType

@pytest.fixture
def test_client():
    """Create a test client with a fully wired test engine."""
    import tradingbot.api.main as main_api
    
    # We must construct a real engine for the app to use
    config = load_config()
    test_eng = _build_engine(config)
    main_api.engine = test_eng
    
    client = TestClient(app)
    yield client
    
    # Cleanup
    main_api.engine = None

def test_manual_override_buy(test_client):
    """Test dispatching a manual buy trade."""
    
    import tradingbot.api.main as main_api
    
    events_caught = []
    
    async def catch_signal(event):
        events_caught.append(event)
        
    main_api.engine.event_bus.subscribe(EventType.SIGNAL, catch_signal)
    
    response = test_client.post("/api/trade/manual", json={
        "symbol": "BTC/USDT",
        "side": "buy",
        "quantity": 1.5
    })
    
    assert response.status_code == 200
    assert response.json()["message"] == "Manual trade signal dispatched"
    
    assert len(events_caught) == 1
    sig = events_caught[0]
    assert sig.symbol == "BTC/USDT"
    assert sig.side == "buy"
    assert sig.source == "manual"
    assert sig.reason == "User Override"

def test_manual_override_invalid_side(test_client):
    """Test manual trade with invalid side."""
    response = test_client.post("/api/trade/manual", json={
        "symbol": "BTC/USDT",
        "side": "invalid",
        "quantity": 1.5
    })
    
    assert response.status_code == 400
    assert "Invalid side" in response.json()["detail"]
