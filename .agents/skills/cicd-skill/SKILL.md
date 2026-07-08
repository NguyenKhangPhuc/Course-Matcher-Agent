---
name: cicd-skill
description: This skill empowers the agent to design, generate, and optimize continuous integration and continuous deployment (CI/CD) pipelines. The agent must architect pipelines that maximize performance through parallelism, guarantee safety via sequential dependencies, enforce automated versioning upon successful deployment, and document every single job using descriptive English docstrings.
---
# Agent Skill: CI/CD Pipeline Architecture & Automation Specialist

## Purpose
This skill empowers the agent to design, generate, and optimize continuous integration and continuous deployment (CI/CD) pipelines. The agent must architect pipelines that maximize performance through parallelism, guarantee safety via sequential dependencies, enforce automated versioning upon successful deployment, and document every single job using descriptive English docstrings.

---

## 1. Pipeline Architecture Principles

The agent must structure the pipeline using an optimal blend of parallel and sequential execution based on these stages:

[Parallel Verification]          [Build Stage]        [Deployment Stage]      [Release Stage]
├── Linting (Job 1)     ──────┐
├── Unit Tests (Job 2)  ──────┼─> Build (Job 4) ───> Deploy (Job 5) ────────> Tag & Release (Job 6)
└── E2E Tests (Job 3)   ──────┘

1.  **Stage 1: Verification (Parallel Execution)**
    * Jobs like `linting`, `unit-testing`, and `e2e-testing` must run **simultaneously** on separate runners to reduce overall execution time (Fast Feedback Loop).
2.  **Stage 2: Artifact Creation (Sequential Dependency)**
    * The `build` job must wait and depend on the successful completion of **all** verification jobs. If any test or lint script fails, the build phase must be skipped entirely.
3.  **Stage 3: Deployment (Sequential Dependency)**
    * The `deploy` job must run **only** after the `build` job completes successfully.
4.  **Stage 4: Post-Deployment Versioning (Sequential Dependency)**
    * Once the application is successfully deployed, a dedicated job must automatically handle version tagging (e.g., generating a Git tag/release) to ensure traceability.

---

## 2. Code & Documentation Standards

To maintain excellent maintainability, the agent must adhere to the following rules when generating CI/CD files (e.g., GitHub Actions or GitLab CI):

* **Language:** All pipeline configurations, job names, step names, comments, and docstrings must be written exclusively in **English**.
* **Mandatory Inline Job Docstrings:** Since YAML does not natively support standard docstrings, the agent must embed a structured comment block at the top of *every job declaration* containing:
    1.  **Purpose:** What the job does.
    2.  **Rationale:** Why this job is necessary at this specific point in the lifecycle.
    3.  **Dependencies:** What prerequisites (if any) this job relies on.

---

## 3. Reference Implementation: GitHub Actions

When generating a GitHub Actions workflow, the agent must use this structural pattern:

```yaml
name: Production CI/CD Pipeline

on:
  push:
    branches: [ main ]

jobs:
  # ==========================================
  # STAGE 1: PARALLEL VERIFICATION
  # ==========================================

  lint:
    # Purpose: Validates code formatting and syntax standards.
    # Rationale: Prevents poorly formatted or syntactically incorrect code from consuming build resources.
    # Dependencies: None. Runs immediately in parallel with other verification jobs.
    name: Code Quality & Linting
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
      - name: Install Dependencies
        run: npm ci
      - name: Execute Linter
        run: npm run lint

  unit-test:
    # Purpose: Executes low-level isolated function tests.
    # Rationale: Ensures that the core business logic remains unbroken by recent changes.
    # Dependencies: None. Runs immediately in parallel with other verification jobs.
    name: Unit Testing
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
      - name: Install Dependencies
        run: npm ci
      - name: Execute Unit Tests
        run: npm test

  e2e-test:
    # Purpose: Simulates real user interactions via end-to-end integration tests.
    # Rationale: Catches regression issues resulting from the interplay of multiple modules before building production assets.
    # Dependencies: None. Runs immediately in parallel with other verification jobs.
    name: End-to-End Testing
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
      - name: Install Dependencies
        run: npm ci
      - name: Execute E2E Tests
        run: npm run test:e2e

  # ==========================================
  # STAGE 2: SEQUENTIAL ARTIFACT CREATION
  # ==========================================

  build:
    # Purpose: Compiles source code and aggregates production assets.
    # Rationale: Ensures that compile-time checks pass, and packages the app only after code is proven clean and functional.
    # Dependencies: Requires successful execution of lint, unit-test, and e2e-test jobs.
    name: Production Build
    runs-on: ubuntu-latest
    needs: [lint, unit-test, e2e-test]
    steps:
      - uses: actions/checkout@v4
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
      - name: Install Dependencies
        run: npm ci
      - name: Compile Code
        run: npm run build

  # ==========================================
  # STAGE 3: DEPLOYMENT
  # ==========================================

  deploy:
    # Purpose: Transfers built production artifacts into the hosting environment.
    # Rationale: Ships the verified code to the target server safely once it passes the build phase.
    # Dependencies: Requires successful execution of the build job.
    name: Deploy to Production
    runs-on: ubuntu-latest
    needs: build
    steps:
      - uses: actions/checkout@v4
      - name: Deploy Step
        run: echo "Deploying artifacts to production environment..."

  # ==========================================
  # STAGE 4: VERSIONING & RELEASE
  # ==========================================

  create-version:
    # Purpose: Automatically generates a semantic Git tag and publishes a release.
    # Rationale: Creates a permanent, traceable historical marker matching the code currently running in production.
    # Dependencies: Requires successful execution of the deploy job.
    name: Auto-Versioning & Release
    runs-on: ubuntu-latest
    needs: deploy
    steps:
      - uses: actions/checkout@v4
      - name: Bump Version and Push Git Tag
        run: |
          echo "Generating new semantic version tag..."
          # Real implementation would compute next semver version and run:
          # git tag v1.X.X && git push origin v1.X.X