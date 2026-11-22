"""
make_model_card_md.py -- writes docs/M1_MODEL_CARD.md from data/processed/m1_model_card.json.
    python -m scripts.make_model_card_md
"""
import json
from pathlib import Path

CARD = Path("data/processed/m1_model_card.json")
OUT = Path("docs/M1_MODEL_CARD.md")


def pct(x):
    return f"{100 * x:.1f}%"


def row(name, r):
    ci = r.get("auc_95ci")
    auc = f"{r['auc']:.3f}" + (f" ({ci[0]:.3f}-{ci[1]:.3f})" if ci else "")
    return (f"| {name} | {r['n']:,} | {r['positives']:,} | {pct(r['base_rate'])} | {auc} | "
            f"{r['pr_auc']:.3f} | {pct(r['precision_top10pct'])} |")


def main():
    c = json.loads(CARD.read_text())
    ev, tr, bands = c["evaluation"], c["training"], c["bands"]
    base = ev["baseline_experiments"]
    L = [
        "# M1 mortality-likelihood model card", "",
        f"Model `{c['model_version']}` - {c['algorithm']}. Generated {c['generated_at']} by "
        "`python -m scripts.train_final`. **This file is generated; do not edit it by hand** "
        "(run `python -m scripts.make_model_card_md`).", "",
        "## What it predicts", "", c["target"], "",
        "It estimates where USFS aerial surveys would map tree mortality. It is not a general "
        "forest-health measure, and the likelihood is relative to surveyed forest, not a "
        "real-world probability.", "",
        "## Training data", "",
        f"- {tr['rows']:,} labelled patch-years ({tr['positives']:,} positive), {tr['years']}, "
        f"{tr['spatial_blocks_20km']} spatial blocks of 20 km.",
        f"- Negatives: {tr['negatives']}.",
        "- Excluded: " + "; ".join(tr["excluded"]) + ".",
        f"- Shaver Lake in training: {'yes' if tr['shaver_lake_in_training'] else 'no (never used)'}.", "",
        "## Evaluation", "",
        "| Test | Cells | Positives | Base rate | AUC (95% interval) | PR-AUC | Precision, top 10% |",
        "|---|---|---|---|---|---|---|",
        row("Whole 20 km blocks held out (out-of-fold, deployed features)",
            ev["whole_blocks_held_out_out_of_fold_2021_2024"]),
    ]
    for y, r in ev["by_year_out_of_fold"].items():
        L.append(row(f"... of which year {y}", r))
    for key, label in (("space_test_blocks_held_out_2021_2023", "Experiment 1: blocks held out 2021-2023"),
                       ("strict_test_new_blocks_and_2024", "Experiment 2: new blocks AND new year 2024"),
                       ("shaver_lake_never_seen_baseline", "Experiment 3: Shaver Lake never seen")):
        b = base.get(key)
        if b:
            L.append(row(f"{label}: environment only", b["1_environment_only"]))
            L.append(row(f"{label}: environment + satellite", b["2_option_A"]))
    L.append(row("**Deployed model on Shaver Lake (never seen)**",
                 ev["shaver_lake_never_seen_deployed_model"]))
    L.append("")
    for key, label in (("space_test_blocks_held_out_2021_2023", "blocks held out"),
                       ("strict_test_new_blocks_and_2024", "new blocks and 2024")):
        g = (base.get(key) or {}).get("auc_gain_A_over_env_95ci")
        if g:
            L.append(f"- AUC gain of satellite features over environment only ({label}): "
                     f"95% interval {g[0]:+.3f} to {g[1]:+.3f}.")

    t = bands["table"]
    L += ["", "## Bands", "",
          f"Cutoffs come from the out-of-fold score distribution: High at or above {bands['high']:.3f}, "
          f"Elevated at or above {bands['elevated']:.3f}, Lower below.", "",
          "| Band | Share of patches | Observed damage rate |", "|---|---|---|"]
    for name in ("High", "Elevated", "Lower"):
        L.append(f"| {name} | {pct(t[name]['share_of_cells'])} | {pct(t[name]['observed_damage_rate'])} |")
    pos = tr["positives"]
    tp_h = t["High"]["n"] * t["High"]["observed_damage_rate"]
    tp_e = t["Elevated"]["n"] * t["Elevated"]["observed_damage_rate"]
    n_he = t["High"]["n"] + t["Elevated"]["n"]
    L += ["", f"High alone catches about {pct(tp_h / pos)} of all mapped damage. High plus Elevated flags "
              f"{pct(n_he / tr['rows'])} of patches, {pct((tp_h + tp_e) / n_he)} of them damaged, and catches "
              f"about {pct((tp_h + tp_e) / pos)} of all mapped damage.", ""]

    L += ["## Calibration (out-of-fold, by decile of predicted likelihood)", "",
          "| Decile | Mean predicted | Observed rate | Patches |", "|---|---|---|---|"]
    for r in c["calibration_deciles"]:
        L.append(f"| {r['decile'] + 1} | {r['mean_predicted']:.3f} | {r['observed_rate']:.3f} | {r['n']:,} |")

    L += ["", "## What the model relies on (AUC drop when a feature is shuffled)", "",
          "| Feature | Meaning | AUC drop |", "|---|---|---|"]
    for r in c["permutation_importance"][:10]:
        L.append(f"| {r['feature']} | {c['feature_notes'].get(r['feature'], '')} | {r['auc_drop']:.4f} |")

    L += ["", "## Limitations", ""] + [f"- {x}" for x in c["limitations"]]
    L += ["", "## Sources", ""] + [f"- {x}" for x in c["sources"]]
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("Wrote", OUT)


if __name__ == "__main__":
    main()