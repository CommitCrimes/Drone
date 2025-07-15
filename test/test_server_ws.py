import asyncio
import websockets

async def handler(websocket):
    print("Client connecté")
    try:
        async for message in websocket:
            print("Message reçu :")
            print(message)
    except websockets.ConnectionClosed:
        print("Client déconnecté")

async def main():
    print("Serveur WebSocket en écoute sur ws://localhost:3000")
    async with websockets.serve(handler, "0.0.0.0", 3000):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
