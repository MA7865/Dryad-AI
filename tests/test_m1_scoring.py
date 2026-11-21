import numpy as np
import pandas as pd

from modules.forest_health.scoring import score_table


def _frame():
    rows = []
    for i in range(100):                       # 100 unburned forest patches, evenly spread
        rows.append(dict(patch_id=f"P_r000_c{i:03d}", row=0, col=i, year=2026,
                         NDVI=0.40 + 0.3 * i / 100, NDMI=-0.1 + 0.3 * i / 100, NBR=0.2,
                         valid=1.0, forest_frac=0.9, burn_frac=0.0, obs_count=5.0))
    rows.append(dict(patch_id="P_r001_c000", row=1, col=0, year=2026,      # mostly burned
                     NDVI=0.3, NDMI=-0.2, NBR=-0.1, valid=1.0,
                     forest_frac=0.9, burn_frac=0.9, obs_count=5.0))
    rows.append(dict(patch_id="P_r001_c001", row=1, col=1, year=2026,      # no forest
                     NDVI=np.nan, NDMI=np.nan, NBR=np.nan, valid=1.0,
                     forest_frac=0.0, burn_frac=0.0, obs_count=np.nan))
    return pd.DataFrame(rows)


def test_bands_and_null_handling():
    scored, trends, bounds = score_table(_frame())
    s = scored.set_index("patch_id")
    assert s.loc["P_r001_c000", "health_band"] == "Post-fire recovery"
    assert s.loc["P_r001_c001", "health_band"] == "Not scored"
    assert np.isnan(s.loc["P_r001_c001", "health_index"])

    unburned = scored[(scored["burn_status"] == "unburned") & scored["health_index"].notna()]
    assert set(unburned["health_band"]) == {"High stress", "Moderate stress", "Healthy"}
    share_high = (unburned["health_band"] == "High stress").mean()
    assert 0.05 <= share_high <= 0.15            # about 10% by construction
    assert scored["health_index"].dropna().between(0, 100).all()


def test_single_window_has_no_trend():
    _, trends, _ = score_table(_frame())
    assert (trends["trend_label"] == "Not enough data").all()