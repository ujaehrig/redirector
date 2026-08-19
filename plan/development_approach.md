# Development Approach

## Methodology

Test-Driven Development (TDD). All tests are written before
implementation code. When tests fail, the code is fixed — not the tests.

## Phases

### Phase 1: Core Redirector (Current)

Build the complete local redirector application:

1. Project initialization and configuration
2. Repository layer (protocol + SQLite)
3. HTTP layer (FastAPI routes)
4. CLI management tool
5. Integration and polish

### Phase 2: AWS Deployment (Deferred)

Add Lambda compatibility and DynamoDB:

1. DynamoDB repository implementation
2. Mangum adapter integration
3. Infrastructure as Code (CDK/SAM/Terraform)
4. CI/CD pipeline

### Phase 3: Enhancements (Deferred)

Optional improvements:

1. Structured JSON logging
2. Caching layer with TTL
3. Metrics and monitoring
4. Admin API with authentication

## Definition of Done

- 100% code coverage with pytest
- Code formatted with `ruff format`
- No linting errors from `ruff check`
- No type errors from `pyright`
- All tests pass with no errors or warnings
