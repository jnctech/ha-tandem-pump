# Contributing to Tandem Source / Carelink Integration

Thank you for considering contributing to this Home Assistant integration!

## Development Setup

### Prerequisites
- Python 3.11+
- Home Assistant 2023.1.0+
- Git

### Local Development

1. Clone the repository:
```bash
git clone https://github.com/jnctech/Home-Assistant-Tandem-Source-Carelink.git
cd Home-Assistant-Tandem-Source-Carelink
```

2. Install development dependencies:
```bash
pip install -r requirements.txt
```

3. Run tests:
```bash
pytest tests/
```

## Branch Strategy

We follow a Git Flow inspired workflow:

- `develop` - Main development branch (default)
- `feature/*` - New features
- `bugfix/*` - Bug fixes
- `release/*` - Release preparation

## Making Changes

### 1. Create a Feature Branch

```bash
git checkout develop
git pull origin develop
git checkout -b feature/your-feature-name
```

### 2. Make Your Changes

- Follow Home Assistant coding standards
- Add tests for new functionality
- Update documentation (README.md, docstrings)
- Keep commits atomic and well-described

### 3. Run Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_tandem_api.py

# Run with coverage
pytest --cov=custom_components.carelink tests/
```

### 4. Commit Guidelines

Follow Conventional Commits format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `test`: Adding or updating tests
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `chore`: Changes to build process or auxiliary tools

**Examples**:
```
feat(tandem): Add support for Tandem t:connect app authentication

fix(api): Resolve blocking SSL call in TandemSourceClient
- Move SSL context creation to executor
- Fixes #123

test(coordinator): Add tests for Tandem data coordinator
```

### 5. Submit Pull Request

1. Push your branch to GitHub:
```bash
git push origin feature/your-feature-name
```

2. Create a Pull Request to `develop`
3. Fill out the PR template
4. Wait for review

## Testing Requirements

All PRs must include:
- Unit tests for new functionality
- Integration tests where appropriate
- All existing tests must pass
- No decrease in code coverage

## Code Style

- Follow PEP 8
- Use Black for formatting (line length: 88)
- Use type hints where possible
- Add docstrings to public functions/classes

## Documentation

Update documentation when:
- Adding new sensors or features
- Changing configuration options
- Fixing bugs that affect user behavior
- Adding new dependencies

## Release Process

See [RELEASE_PROCESS.md](RELEASE_PROCESS.md) for details on how releases are made.

## Getting Help

- Open an issue for bugs or feature requests
- Join discussions in existing issues
- Check README.md for setup help

## Code of Conduct

Be respectful, constructive, and professional in all interactions.
