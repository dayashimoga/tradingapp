import asyncio
import websockets
import json

async def test_ws():
    try:
        async with websockets.connect("ws://localhost:8000/ws") as ws:
            print("Connected to backend 8000!")
            while True:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    print("Received:", msg[:100])
                except asyncio.TimeoutError:
                    print("Timeout waiting for message...")
                    break
    except Exception as e:
        print("Error:", e)

asyncio.run(test_ws())
