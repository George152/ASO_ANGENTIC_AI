import os
import uvicorn
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route, Mount

from basic_agent.mcp_file import mcp

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Allow health check without auth
        if request.url.path == "/health":
            return await call_next(request)

        expected_token = os.environ.get("MCP_AUTH_TOKEN")
        if not expected_token:
            # If no token is configured, allow all (or fail safe, but here we warn)
            print("WARNING: MCP_AUTH_TOKEN not set, allowing all requests")
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header:
             return JSONResponse({"error": "Missing Authorization header"}, status_code=401)
        
        # Expect "Bearer <token>"
        try:
            scheme, token = auth_header.split()
            if scheme.lower() != "bearer" or token != expected_token:
                return JSONResponse({"error": "Invalid token"}, status_code=401)
        except ValueError:
            return JSONResponse({"error": "Invalid Authorization header format"}, status_code=401)

        return await call_next(request)

async def health(request):
    return JSONResponse({"status": "ok"})

# Create the SSE application from FastMCP
sse = mcp.sse_app()

# Wrap it in a Starlette app with our auth middleware
middleware = [
    Middleware(AuthMiddleware)
]

app = Starlette(
    routes=[
        Route("/health", health),
        Mount("/", sse),
    ],
    middleware=middleware
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
