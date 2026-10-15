# Contributing

- Questions, bugs, proposals: open a GitHub Issue on this repository.
- Pull requests: branch from `master`, keep changes small, include tests.
- Run the tests: `PYTHONPATH=../runtime-contracts python -m pytest tests/ -q` (needs a sibling `runtime-contracts` checkout; CI runs `pytest -q` after `pip install -e ".[dev]"`).
- Release line: `v0.1.x`. Version bumps must keep `pyproject.toml` and `discovery_runtime.__version__` in agreement (enforced by `tests/test_release_line.py`). Never delete or move published tags.
- Domain-specific behaviour belongs in consumers, not here; changes to the shared `learn` contract are made here and released as a new tag.
- Licensing terms for contributions: contact to be confirmed. See [LICENSE.md](LICENSE.md).
- General contact: redevops@redevops.io (organisation email listed on the GitHub org profile).
