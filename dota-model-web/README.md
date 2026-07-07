# Dota 2 Draft Model

Mirrors the LoL model: same 8-feature layout (6 draft-only + 2 team), same
LR / HistGBM / LightGBM comparison, same artifact/serve/UI pattern.

## File placement (in your DOTAMODEL root)

```
DOTAMODEL/
  data/
    massive_pro_dataset.csv     (already there)
    hero_meta_stats.csv         (already there)
  dota_model/
    train_dota_model.py         <- new
    serve_dota.py               <- new
    artifacts/                  <- created by training
```

Frontend files go in your website's `src/`:
- `DotaPage.tsx` (new)
- `App.tsx` (replaces yours — adds the DOTA tab, keeps everything else)

## Run

```bash
pip install lightgbm fastapi uvicorn scikit-learn pandas joblib

# 1. train (from DOTAMODEL root)
python dota_model/train_dota_model.py

# 2. serve on port 8001 (your LoL API keeps 8000)
uvicorn dota_model.serve_dota:app --port 8001
```

Then open the site and click the DOTA tab.

## Features (radiant minus dire)

| # | feature        | source                                              |
|---|----------------|-----------------------------------------------------|
| 0 | hero_wr_diff   | pro winrate per hero (train games only, smoothed)   |
| 1 | presence_diff  | pro pick presence                                   |
| 2 | synergy_diff   | same-team hero-pair winrates                        |
| 3 | counter_score  | hero-vs-hero matchup winrates derived from your pro matches |
| 4 | pub_wr_diff    | soloq winrate (hero_meta_stats pub_pick/pub_win)    |
| 5 | hs_wr_diff     | high-bracket (divine/immortal) soloq winrate        |
| 6 | team_wr_diff   | expanding team winrate (state before each game)     |
| 7 | comfort_diff   | expanding player-on-hero winrate from pro matches   |

Draft-only prediction uses features 0–5; "with team" uses all 8.




