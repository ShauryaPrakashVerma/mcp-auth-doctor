import json

import pytest

from mcp_auth_doctor import __version__
from mcp_auth_doctor.cli import main
from tests.conftest import MCP, mount


def test_plain_http_is_refused(capsys):
    assert main(["http://mcp.example.com/mcp"]) == 3
    assert "https" in capsys.readouterr().err


def test_localhost_http_is_allowed(router, capsys):
    url = "http://127.0.0.1:3000/mcp"
    mount(
        router,
        mcp_url=url,
        resource=url,
        header_url="http://127.0.0.1:3000/.well-known/oauth-protected-resource/mcp",
        prm_urls=("http://127.0.0.1:3000/.well-known/oauth-protected-resource/mcp",),
    )
    assert main([url]) == 0
    out = capsys.readouterr().out
    assert "unauth-401" in out and "Verdict: PASS (exit 0)" in out


def test_missing_argument_and_bad_spec_exit_3():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 3
    with pytest.raises(SystemExit) as exc:
        main(["https://mcp.example.com/mcp", "--spec", "1999-01-01"])
    assert exc.value.code == 3


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_json_output_and_exit_code_on_failure(router, capsys):
    mount(router, resource=MCP + "/")
    assert main([MCP, "--json"]) == 1
    doc = json.loads(capsys.readouterr().out)
    assert doc["url"] == MCP
    assert doc["summary"]["exit_code"] == 1
    failed = [c for c in doc["checks"] if c["status"] == "fail"]
    assert [c["id"] for c in failed] == ["prm-resource"]


def test_table_shows_evidence_for_failures_and_verbose(router, capsys):
    mount(router, resource=MCP + "/")
    main([MCP])
    out = capsys.readouterr().out
    assert "prm-resource" in out and "FAIL" in out
    assert "trailing_slash_only: True" in out
    main([MCP, "--verbose"])
    out = capsys.readouterr().out
    assert "tried https://mcp.example.com/.well-known/oauth-protected-resource/mcp -> 200" in out


def test_inconclusive_exit_code(router):
    mount(router, unauth_status=200, prm_urls=())
    assert main([MCP, "--spec", "2025-11-25"]) == 2


def test_callback_port_validation():
    with pytest.raises(SystemExit) as exc:
        main(["https://mcp.example.com/mcp", "--callback-port", "70000"])
    assert exc.value.code == 3


def test_markdown_output_row_count(router, capsys):
    mount(router)

    assert main([MCP, "--format", "markdown"]) == 0
    markdown = capsys.readouterr().out

    # Count table rows, excluding the header and separator.
    table_rows = [
        line
        for line in markdown.splitlines()
        if line.startswith("|") and not line.startswith("|---")
    ]
    data_rows = table_rows[1:]

    # Get the expected number of checks from the JSON report.
    assert main([MCP, "--format", "json"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert len(data_rows) == len(report["checks"])


def test_markdown_preserves_failure_reason(router, capsys):
    mount(router, resource=MCP + "/")

    # Generate the Markdown report for a failing check.
    assert main([MCP, "--format", "markdown"]) == 1
    markdown = capsys.readouterr().out

    # Get the original failure reason from the JSON report.
    assert main([MCP, "--format", "json"]) == 1
    report = json.loads(capsys.readouterr().out)

    failed_checks = [
        check for check in report["checks"]
        if check["status"] == "fail"
    ]
    assert failed_checks

    for check in failed_checks:
        assert check["reason"] in markdown
