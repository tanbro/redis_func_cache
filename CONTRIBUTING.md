# Contributing

Thank you for your interest in contributing to redis_func_cache! This document provides guidelines and information to help you contribute effectively to the project.

## Code of Conduct

By participating in this project, you are expected to uphold our Code of Conduct, which promotes a welcoming and inclusive environment for all contributors.

## How to Contribute

### Reporting Bugs

Before reporting a bug, please check the existing issues to see if it has been reported. If not, create a new issue with:

- A clear and descriptive title
- A detailed description of the problem
- Steps to reproduce the issue
- Expected vs. actual behavior
- Your environment information (Python version, Redis version, OS, etc.)

### Suggesting Enhancements

We welcome feature requests and suggestions. To propose an enhancement:

1. Check existing issues to avoid duplicates
2. Create a new issue with a clear title and detailed description
3. Explain why this enhancement would be useful
4. If possible, provide examples of how the feature would be used

### Code Contributions

#### Development Setup

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/your-username/redis_func_cache.git
   cd redis_func_cache
   ```
3. Install [uv](https://docs.astral.sh/uv/) if you haven't already:
   ```bash
   # On macOS and Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # On Windows
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

   # Or using pip
   pip install uv
   ```
4. Create a virtual environment and install dependencies:
   ```bash
   uv venv
   uv sync --all-extras --dev
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

#### Running Tests

Before submitting changes, ensure all tests pass:

```bash
# Run all tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=src

# Run specific test categories
uv run pytest tests/test_basic.py
```

#### Code Style

We use several tools to maintain code quality:

- **Ruff**: For linting and formatting. Check <https://docs.astral.sh/ruff/> for more details.
- **MyPy**: For static type checking. Check <https://mypy.readthedocs.io/en/stable/> for more details.
- **Pre-commit hooks**: To automatically check code before committing. Check <https://pre-commit.com/> for more details.

You should install them before making changes.

To run checks manually:

```bash
# Run all pre-commit checks
uv run pre-commit run --all-files

# Run specific checks
uv run ruff check .
uv run ruff format .
uv run mypy src
```

#### Making Changes

1. Create a new branch for your feature or bugfix:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Make your changes, following the code style guidelines

3. Add tests for new functionality

4. Ensure all tests pass (you shall run redis server on localhost:6379 before running tests):

   ```bash
   uv run pytest
   ```

   If the changes are concerned with Redis cluster, it is recommended to run the tests against a Redis cluster by docker compose:

   ```bash
   cd docker
   docker compose up
   ```

   If you have standalone Redis server(s) running, you can run the tests against it/them by setting the environment variables

   - `REDIS_URL`: url for the single Redis server
   - `REDIS_CLUSTER_NODES`: `":"` split list of Redis cluster nodes

   A `.env` file can be used to set the environment variables.

5. Commit your changes with a clear, descriptive commit message

6. Push to your fork and submit a pull request

### Pull Request Guidelines

When submitting a pull request:

1. Provide a clear title and description
2. Reference any related issues
3. Ensure your code follows the project's style guidelines
4. Include tests for new functionality
5. Update documentation as needed
6. Keep pull requests focused on a single feature or bugfix

### Documentation

Improvements to documentation are always welcome. This includes:

- Updates to README.md
- Docstring improvements
- Examples and tutorials
- Comments in code

## Development Practices

### Lua Scripts

This project uses Redis Lua scripts for atomic operations. When modifying Lua scripts:

1. Ensure scripts remain atomic and efficient
2. Test with various Redis versions
3. Keep scripts readable and well-commented
4. Follow existing patterns in the codebase

### Testing

We maintain high test coverage and follow these practices:

1. Write unit tests for new functionality
2. Test both synchronous and asynchronous code paths
3. Include edge cases and error conditions
4. Test with different cache policies
5. Use appropriate mocking when needed

### Versioning

We follow [Semantic Versioning](https://semver.org/). Changes are categorized as:

- **Major**: Breaking changes
- **Minor**: New features (backward compatible)
- **Patch**: Bug fixes (backward compatible)

## Getting Help

If you need help with your contribution:

1. Check the documentation and existing issues
2. Join our community discussions
3. Contact the maintainers directly

## License

By contributing to redis_func_cache, you agree that your contributions will be licensed under the BSD 3-Clause License.
