import json

import pytest
from typer.testing import CliRunner


@pytest.fixture
def runner():
    return CliRunner()


def parse_json(result):
    assert result.exit_code == 0, result.output
    return json.loads(result.output)
