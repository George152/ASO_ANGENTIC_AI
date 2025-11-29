# Walkthrough - Project Reorganization

I have cleaned up the project root by moving configuration and script files into dedicated subdirectories.

## Changes

### Directory Structure
- Created `docker/` directory.
- Created `scripts/` directory.

### File Moves
| File | New Location |
|------|--------------|
| `Dockerfile.agent` | `docker/Dockerfile.agent` |
| `Dockerfile.mcp` | `docker/Dockerfile.mcp` |
| `Dockerfile.ollama` | `docker/Dockerfile.ollama` |
| `start_ollama.sh` | `docker/start_ollama.sh` |
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

## Verification Results

### Manual Verification
- Verified that `docker-compose.yml` points to `docker/Dockerfile.*`.
- Confirmed files are moved to their respective directories.

## Next Steps
To apply these changes, please rebuild your Docker containers:

```bash
docker-compose down
docker-compose up --build
```
