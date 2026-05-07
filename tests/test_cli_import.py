"""CLI smoke tests."""
from pathlib import Path
from click.testing import CliRunner

FIXTURES = Path(__file__).parent / "fixtures"


def test_import_claude(tmp_path):
    from convaix.cli import main
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "import", "claude",
            str(FIXTURES / "claude_sample.json"),
            "--db", f"sqlite://{tmp_path}/test.db",
            "--skip-embeddings",
        ],
    )
    assert result.exit_code == 0, result.output


def test_list(tmp_path):
    from convaix.cli import main
    runner = CliRunner()
    # First import something
    runner.invoke(
        main,
        [
            "import", "claude",
            str(FIXTURES / "claude_sample.json"),
            "--db", f"sqlite://{tmp_path}/test.db",
            "--skip-embeddings",
        ],
    )
    result = runner.invoke(main, ["list", "--db", f"sqlite://{tmp_path}/test.db"])
    assert result.exit_code == 0
    assert len(result.output) > 0
