"""Write tests/fixtures/fire_spread.json: one fixed Goose-style simulation (seed 0, fixed timestamp)."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modules.fire_monitoring import simulate_fire_spread

# western-tip start (inside the Goose perimeter), dry-hours wind, k = 2
fc = simulate_fire_spread((-119.4987, 37.0140), 9.07, wind_toward_deg=92, wind_k=2.0, seed=0,
                          generated_at="2026-11-18T00:00:00Z")
out = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "fire_spread.json"
out.write_text(json.dumps(fc, indent=1))
print(f"{len(fc['features'])} patches -> {out}")
