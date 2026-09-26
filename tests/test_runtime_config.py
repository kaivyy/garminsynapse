import os
import subprocess
from pathlib import Path


def test_run_sh_exists_and_executable():
    run_sh = Path("/root/garminsynapse/run.sh")
    assert run_sh.exists(), "run.sh must exist"
    assert os.access(run_sh, os.X_OK), "run.sh must be executable"
    
    content = run_sh.read_text()
    assert "ulimit -c 0" in content, "run.sh must disable core dumps via ulimit -c 0"
    assert "$VENV_DIR/bin/python" in content or ".venv/bin/python" in content, "run.sh must execute virtualenv python"


def test_ecosystem_config_has_backoff_and_run_sh():
    ecosystem = Path("/root/garminsynapse/ecosystem.config.cjs")
    assert ecosystem.exists(), "ecosystem.config.cjs must exist"
    
    content = ecosystem.read_text()
    assert "run.sh" in content, "ecosystem.config.cjs must target run.sh"
    assert "exp_backoff_restart_delay" in content, "ecosystem.config.cjs must configure exp_backoff_restart_delay"
    assert "restart_delay" in content, "ecosystem.config.cjs must configure restart_delay"
    assert "max_restarts" in content, "ecosystem.config.cjs must configure max_restarts"
    assert "min_uptime" in content, "ecosystem.config.cjs must configure min_uptime"
