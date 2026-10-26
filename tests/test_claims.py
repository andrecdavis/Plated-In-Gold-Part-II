import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_every_readme_claim_matches_results():
    spec = importlib.util.spec_from_file_location("audit_claims", ROOT / "scripts" / "audit_claims.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.main() == 0
