# Walkthrough - Project 

### File Moves
| File | New Location |
|------|--------------|
| `Dockerfile.agent` | `docker/Dockerfile.agent` |
| `Dockerfile.mcp` | `docker/Dockerfile.mcp` |
| `Dockerfile.ollama` | `docker/Dockerfile.ollama` |
| `fastmcp_inspect.py` | `scripts/fastmcp_inspect.py` |
| `sig_runner.py` | `scripts/sig_runner.py` |

### `docker-compose.yml`
Updated the build contexts to point to the new Dockerfile locations while keeping the build context at the project root (`.`).

```yaml
   mcp-server:
     build:
       context: .
       dockerfile: docker/Dockerfile.mcp
     # ...

   adk-web:
     build:
       context: .
       dockerfile: docker/Dockerfile.agent
     # ...
```

## Next Steps
To apply these changes, please rebuild your Docker containers:

```bash
docker-compose down
docker-compose up --build
```
