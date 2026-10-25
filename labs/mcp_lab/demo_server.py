from mcp.server.fastmcp import FastMCP

mcp = FastMCP("demo-server")

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

@mcp.resource("config://server")
def server_config() -> str:
    return "name=demo-server version=1.0"

@mcp.prompt()
def review_code(code: str) -> str:
    return "Please review this code: " + code

if __name__ == "__main__":
    mcp.run()
