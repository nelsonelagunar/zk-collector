# Contributing to ZK-Collector

Thanks for your interest! Here's how to get involved.

## Development Setup

```bash
git clone https://github.com/nelsonelagunar/zk-collector.git
cd zk-collector
python3 -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
```

## Running Tests

```bash
# Unit tests only (no device needed)
pytest tests/unit/ -v

# All tests (needs ZKTeco device on LAN)
pytest tests/ -v --device-ip=192.168.1.101
```

## Device Compatibility Reports

**Don't have a ZKTeco device?** Skip this section.

**Do have one?** We need your help! Open an issue using the "Device Compatibility" template with:
1. Device model (e.g., ZKTeco K40)
2. Firmware version (if available)
3. Whether connection succeeds
4. Any errors encountered

## Pull Request Process

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Run tests: `pytest tests/ -v`
5. Run linting: `ruff check src/ tests/`
6. Push and open a PR

## Code Style

- Python 3.12+ features encouraged (type hints, match statements, etc.)
- 100 char line length (ruff enforces this)
- Conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
