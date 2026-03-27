import asyncio
import json
import httpx

async def test():
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "http://127.0.0.1:8000/invoke",
                json={"app_id": "default_llm", "user_input": "Test token usage!", "model": "gemini-2.5-flash"},
                timeout=10.0
            )
            print(json.dumps(response.json(), indent=2))
        except Exception as e:
            print("Server not running or error:", e)

if __name__ == "__main__":
    asyncio.run(test())
