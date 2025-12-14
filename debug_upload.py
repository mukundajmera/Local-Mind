
import asyncio
import httpx
from pathlib import Path

async def simulate_upload():
    print("Simulating upload of AGENTS.md...")
    async with httpx.AsyncClient() as client:
        file_path = Path("AGENTS.md")
        if not file_path.exists():
            print("Error: AGENTS.md not found.")
            return

        with open(file_path, "rb") as f:
            files = {"file": ("AGENTS.md", f, "text/markdown")}
            try:
                # 1. Upload
                response = await client.post("http://localhost:8000/api/v1/sources/upload", files=files, timeout=60.0)
                if response.status_code == 200:
                    print(f"Upload Success: {response.json()}")
                else:
                    print(f"Upload Failed: {response.status_code} - {response.text}")
                    return

                # 2. Check Graph
                print("Checking graph data...")
                graph_response = await client.get("http://localhost:8000/api/v1/graph", timeout=10.0)
                if graph_response.status_code == 200:
                    data = graph_response.json()
                    nodes = data.get("nodes", [])
                    print(f"Graph Data: {len(nodes)} nodes found.")
                    for node in nodes[:5]: # Show top 5
                        print(f" - {node['name']} ({node['type']})")
                else:
                    print(f"Graph Fetch Failed: {graph_response.status_code}")

            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(simulate_upload())
