# Twitter Client Project Architecture

## Overview
Twitter API client library redesign using tweepy v4.16+ and pydantic v2.8+ for type-safe Twitter/X API interactions.

## Key Design Decisions
- **Core Library**: tweepy for Twitter API v2 interactions
- **Type Safety**: pydantic v2 for request/response validation
- **Architecture**: Service layer pattern with protocol-based dependency injection
- **Authentication**: OAuth 1.0a with ConfigManager/OAuthManager separation
- **Media Handling**: Chunked upload with async processing state monitoring
- **Exception Hierarchy**: Custom domain exceptions extending TwitterClientError base

## Module Structure
- `config.py`: Credential management (env vars + file-based)
- `auth.py`: OAuth 1.0a flow orchestration
- `clients/`: Adapter layer (TweepyClient wrapper)
- `services/`: Business logic (TweetService, MediaService)
- `models.py`: Pydantic response models
- `exceptions.py`: Custom exception hierarchy
- `rate_limit.py`: Rate limiting utilities (placeholder)

## Quality Metrics (as of 2025-10-12)
- Total Python LOC: ~850 (excluding tests)
- Test Coverage: 22 unit tests, all passing
- Code Organization: Well-structured with clear separation of concerns
- No TODO/FIXME comments in production code
- Minimal technical debt

## Future Roadmap
Phase 1 (Current): Core tweet/media operations
Phase 2: UserService, search enhancements
Phase 3: MCP adapter implementation
Phase 4: Documentation, CI/CD automation