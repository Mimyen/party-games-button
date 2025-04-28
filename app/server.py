from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json

app = FastAPI()

latest_presses: list[str] = []
press_history: list[list[str]] = []

connected_websockets: set[WebSocket] = set()
user_connections: dict[WebSocket, str] = {}

@app.get("/")
def read_root():
    return {"message": "FastAPI is running!"}

@app.websocket("/{user_name}")
async def websocket_endpoint(websocket: WebSocket, user_name: str):
    await websocket.accept()
    connected_websockets.add(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            json_data = json.loads(data)
            action = json_data.get("action")

            if action == "on_connect":
                # Register user connection
                user_connections[websocket] = json_data["payload"]["name"]
                print(f"{json_data['payload']['name']} connected")
                await broadcast_connected_users()
            elif action == "button_press":
                latest_presses.append(json_data['user'])
                await broadcast_latest_presses()
            else:
                print(f"Unknown action: {action}")
    except WebSocketDisconnect:
        print(f"WebSocket from {user_name} disconnected.")
        connected_websockets.remove(websocket)
        user_connections.pop(websocket, None)
        await broadcast_connected_users()

async def broadcast_latest_presses():
    message = json.dumps({
        "type": "update",
        "latest_presses": latest_presses
    })
    await broadcast_to_all(message)

async def broadcast_connected_users():
    users = list(user_connections.values())
    message = json.dumps({
        "type": "users",
        "connected_users": users
    })
    await broadcast_to_all(message)

async def broadcast_to_all(message):
    disconnected = set()
    for ws in connected_websockets:
        try:
            await ws.send_text(message)
        except Exception as e:
            print(f"Error sending to websocket: {e}")
            disconnected.add(ws)
    connected_websockets.difference_update(disconnected)
    for ws in disconnected:
        user_connections.pop(ws, None)

@app.post("/save_to_history")
async def save_to_history():
    if latest_presses:
        press_history.append(latest_presses.copy())
        latest_presses.clear()
        await broadcast_latest_presses()
        return {"message": "Saved to history"}
    return {"message": "Nothing to save"}