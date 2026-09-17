from pathlib import Path


def test_ci_build_step_handles_non_package_repositories():
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert 'if [[ -f pyproject.toml || -f setup.py ]]; then' in workflow
    assert "python -m build" in workflow
    assert "skipping package build" in workflow
