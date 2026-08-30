import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("OPENAI_API_KEY", "sk-test-not-used")

from accounting_agent.config import load_config  # noqa: E402

TEST_CONFIG = load_config(ROOT / "config.yaml")
