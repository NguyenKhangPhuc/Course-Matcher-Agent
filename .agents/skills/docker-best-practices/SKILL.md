---
name: docker-best-practices
description: Use this skill whenever the user asks to create, write, review, or optimize a Dockerfile, docker-compose.yml, or containerize a project/application. Trigger on mentions of "Dockerfile", "docker-compose", "containerize", multi-stage build, image size optimization, or setting up local dev environments with Docker. Also use when reviewing an existing Dockerfile/compose file for security, size, or best-practice issues, even if the user doesn't explicitly say "best practice".
---

# Docker & Docker Compose Best Practices

"""
Why this skill exists:
Dockerfiles and docker-compose files that "just work" often hide problems that only
surface in production: bloated images, root-user containers, leaked secrets baked into
image layers, broken cache usage that makes every build slow, or services that start
in the wrong order and crash-loop. This skill encodes the accumulated best practices so
that every Dockerfile/compose file produced or reviewed is small, secure, reproducible,
and production-ready by default instead of by accident.
"""

## Workflow

"""
Why a workflow instead of jumping straight to code:
Docker best practices differ meaningfully by language/framework (a Go binary needs
none of the runtime a Python app needs) and by target environment (dev needs
hot-reload and bind mounts, production needs immutability and resource limits).
Skipping this step produces generic, subtly wrong output.
"""

1. **Identify the language/framework** of the project (Node, Python, Go, Java, PHP, static frontend, etc.) — optimization strategy differs per stack.
2. **Identify the target environment**: dev, production, or both? This affects whether hot-reload, mounted source code, or multi-stage builds are needed.
3. If unclear, ask one short clarifying question instead of guessing. If the user already gave enough context (e.g. "write a Dockerfile for a production Node.js Express app"), proceed directly.
4. Write the Dockerfile + docker-compose.yml applying the principles below.
5. Briefly explain the key decisions made (why multi-stage, why non-root user, etc.) — only the ones relevant to this specific case, not the entire checklist.

## Core Dockerfile Principles

### 1. Always use multi-stage builds for compiled/build-step languages

"""
Why: A build stage typically needs a compiler, dev dependencies, and full source code —
none of which should exist in the final runtime image. Without multi-stage builds, the
final image ships all of that dead weight, increasing size and attack surface for no
benefit at runtime.
"""

```dockerfile
# Build stage
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Runtime stage
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY package*.json ./
USER node
EXPOSE 3000
CMD ["node", "dist/main.js"]
```

### 2. Use a specific, small, pinned base image

"""
Why: `latest` is a moving target — the same Dockerfile can produce a different image
tomorrow, breaking reproducibility and making bugs hard to bisect. Full-size base
images (e.g. plain `node:20`) carry a full OS userland that inflates image size and
increases the number of packages that could have vulnerabilities. Alpine/slim variants
and pinned versions solve both problems.
"""

- Prefer `-alpine` or `-slim` over full images (`node:20` → `node:20-alpine`).
- Never use `latest` — pin a specific version (`node:20.11-alpine` or at minimum `node:20-alpine`) for reproducible builds.
- Consider distroless images (`gcr.io/distroless/...`) for production when maximum security hardening is needed.

### 3. Order COPY instructions to maximize layer cache reuse

"""
Why: Docker caches each layer and invalidates it (and every layer after it) the moment
its inputs change. If source code is copied before dependency installation, every code
edit invalidates the dependency-install layer too, forcing a full reinstall on every
build. Copying dependency manifests first isolates that cache from unrelated code
changes.
"""

```dockerfile
# CORRECT - cache is reused across builds
COPY package*.json ./
RUN npm ci
COPY . .

# WRONG - every code change forces a full dependency reinstall
COPY . .
RUN npm ci
```

### 4. Never run the container as root

"""
Why: If an attacker achieves code execution inside a root container, they inherit root
privileges within that container's namespace, which meaningfully raises the blast
radius of any container-escape or misconfiguration vulnerability. Running as an
unprivileged user is a free, high-value defense-in-depth measure.
"""

```dockerfile
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser
```

### 5. Use a .dockerignore file

"""
Why: Without it, the entire build context (including .git history, node_modules,
local .env files, and logs) is sent to the Docker daemon and can end up copied into
image layers. This slows down builds and can leak secrets or credentials that were
only ever meant to stay on the developer's machine.
"""

```
node_modules
.git
.env
*.log
Dockerfile
docker-compose.yml
dist
.vscode
```

### 6. Never hardcode secrets in a Dockerfile

"""
Why: Anything set via ENV or ARG in a Dockerfile is permanently recorded in the image's
layer history and can be extracted with `docker history` or by anyone who pulls the
image, even after the value is "removed" in a later layer. Secrets must be injected at
runtime, not baked in at build time.
"""

- Don't use `ENV API_KEY=xxx` or an `ARG` carrying a secret value.
- Use runtime env vars via `docker-compose.yml` (`environment:` or `env_file:`), Docker secrets, or BuildKit secret mounts (`RUN --mount=type=secret`) for build-time secrets.

### 7. Combine RUN commands sensibly to reduce layers and clean up in the same layer

"""
Why: Each RUN instruction creates a new layer. If a package cache is populated in one
RUN and deleted in a later RUN, the cache still bloats the final image because earlier
layers are immutable — deleting a file in a later layer doesn't shrink the layers below
it. Cleanup only reduces image size if it happens in the same layer as the install.
"""

```dockerfile
# GOOD
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*
```

Always clean the package manager cache (`apt-get clean`, `rm -rf /var/lib/apt/lists/*`, `pip --no-cache-dir`) within the same RUN layer as the install.

### 8. Use HEALTHCHECK

"""
Why: Without a HEALTHCHECK, Docker (and orchestrators reading container status) only
knows whether the process is running, not whether it's actually serving traffic
correctly. A hung or deadlocked-but-still-running process looks "healthy" without one.
"""

```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --spider -q http://localhost:3000/health || exit 1
```

### 9. Use EXPOSE to document ports, and exec-form CMD

"""
Why: Exec-form CMD (`["node", "server.js"]`) runs the process as PID 1 directly, so it
receives signals like SIGTERM correctly for graceful shutdown. Shell-form CMD
(`node server.js`) runs the process as a child of a shell, which can swallow or delay
signals, causing containers to hang on stop/restart until they're force-killed.
"""

```dockerfile
EXPOSE 3000
CMD ["node", "server.js"]     # CORRECT - exec form, forwards signals properly
# CMD node server.js          # WRONG - shell form, poor signal handling, harder graceful shutdown
```

## docker-compose.yml Principles

### 1. Split configuration by environment

"""
Why: Dev and production have conflicting needs (bind-mounted source code and verbose
logging in dev vs. immutable images and resource limits in production). Compose's
multi-file override mechanism lets a single base file stay authoritative while
environment-specific concerns are layered on top, instead of duplicating the whole file
or hand-editing it before every deploy.
"""

- `docker-compose.yml` — shared/base configuration
- `docker-compose.override.yml` — local dev overrides (automatically merged by compose)
- `docker-compose.prod.yml` — production overrides, run with `docker compose -f docker-compose.yml -f docker-compose.prod.yml up`

### 2. Always use named volumes for data that must persist

"""
Why: Bind mounts tie storage to a specific host path and are prone to permission
mismatches between host and container UIDs. Named volumes are managed by Docker, are
portable across hosts, and are the correct default for anything stateful, like a
database's data directory.
"""

```yaml
volumes:
  db_data:
    driver: local

services:
  db:
    image: postgres:16-alpine
    volumes:
      - db_data:/var/lib/postgresql/data
```

### 3. Use dedicated networks and avoid exposing ports that don't need it

"""
Why: Every port mapped to the host is a port reachable from outside the machine. A
database, cache, or internal API has no reason to be reachable from the public
internet — it only needs to be reachable from other containers on the same Docker
network. Segmenting networks limits what an external attacker can even see.
"""

```yaml
networks:
  backend:
  frontend:

services:
  db:
    networks:
      - backend        # only the backend network can see db; no host port mapping
  api:
    networks:
      - backend
      - frontend
  web:
    networks:
      - frontend
    ports:
      - "80:80"         # only the service that truly needs external access maps a port
```

### 4. Always set an appropriate restart policy

"""
Why: Without a restart policy, a container that crashes (OOM kill, unhandled exception,
host reboot) simply stays down until someone notices and restarts it manually. In
production this directly translates to avoidable downtime.
"""

```yaml
restart: unless-stopped   # for production services
# restart: "no"           # default for dev/one-off jobs
```

### 5. Use healthcheck + depends_on: condition to guarantee correct startup order

"""
Why: Plain `depends_on` only waits for the dependency's container to start, not for the
service inside it to be ready to accept connections (e.g. Postgres accepting a
container start well before it's actually ready for queries). Without a healthcheck
condition, dependents can crash-loop on startup racing against a not-yet-ready
dependency.
"""

```yaml
services:
  db:
    image: postgres:16-alpine
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  api:
    build: ./api
    depends_on:
      db:
        condition: service_healthy
```

### 6. Manage environment variables via .env + env_file

"""
Why: Hardcoding environment-specific values directly into docker-compose.yml couples
configuration to code and risks committing secrets to version control. A `.env` file
(git-ignored, with a committed `.env.example` template) keeps secrets and per-environment
config out of the repository while still being easy for developers to set up.
"""

```yaml
services:
  api:
    env_file:
      - .env
    environment:
      - NODE_ENV=production
```

### 7. Set resource limits for production

"""
Why: Without limits, a single misbehaving container (memory leak, runaway CPU loop) can
starve every other container on the same host, turning a contained bug into a
full-host outage.
"""

```yaml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 512M
        reservations:
          memory: 256M
```

### 8. Give services meaningful container_name and image names (optional but recommended)

"""
Why: Auto-generated container/image names (project-directory-based, hash-suffixed) are
hard to reference in logs, monitoring dashboards, or ad-hoc `docker` commands.
Explicit names make operational work faster and less error-prone.
"""

```yaml
services:
  api:
    build:
      context: ./api
      dockerfile: Dockerfile
    image: myapp-api:1.0
    container_name: myapp-api
```

## Quick Review Checklist

"""
Why a checklist: when reviewing an existing Dockerfile/compose file rather than writing
one from scratch, working through a fixed list catches the same class of issues
consistently, rather than relying on whatever happens to stand out on a first read.
"""

- [ ] Multi-stage build used (if the language has a build step)?
- [ ] Base image pinned to a specific version, using alpine/slim?
- [ ] COPY order maximizes cache reuse?
- [ ] Container runs as a non-root user?
- [ ] `.dockerignore` present — no `.git`/`.env`/secrets leaking into the image?
- [ ] No secrets baked into ENV/ARG?
- [ ] HEALTHCHECK present?
- [ ] CMD uses exec form?
- [ ] compose doesn't expose ports unnecessarily?
- [ ] Important data (DB) uses a named volume?
- [ ] Appropriate restart policy set?
- [ ] depends_on uses `condition: service_healthy` where startup order matters?

## Stack-Specific Notes

"""
Why: The multi-stage template above is generic; each language has a canonical way to
shrink the runtime stage further. These notes exist so the general template doesn't get
applied blindly to a stack where a much smaller, more idiomatic runtime image is
available.
"""

- **Python (FastAPI/Django)**: use `python:3.12-slim`, `pip install --no-cache-dir -r requirements.txt`; consider `gunicorn`/`uvicorn` as CMD; build a virtualenv in the build stage and copy just the `venv` into the runtime stage.
- **Go**: build stage uses `golang:1.22-alpine` to compile a static binary (`CGO_ENABLED=0 go build`); runtime stage uses `scratch` or `alpine` containing only the binary — final image can be just a few MB.
- **Java (Spring Boot)**: build stage uses `maven:3.9-eclipse-temurin-21` to build the jar; runtime stage uses `eclipse-temurin:21-jre-alpine` and copies only the jar over.
- **Static frontend (React/Vue built to static files)**: build stage uses `node:20-alpine` to run `npm run build`; runtime stage uses `nginx:1.27-alpine` and copies the `dist`/`build` folder into `/usr/share/nginx/html`.

If the user also needs a reverse proxy with automatic SSL (Caddy/Nginx+Certbot) added to the compose file, ask whether they have a domain or only an IP before writing the config, since Let's Encrypt cannot issue certificates for a bare IP address.
