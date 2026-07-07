import json
import os
import sys
from collections import defaultdict
from itertools import combinations, product

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss, roc_auc_score
from sklearn.preprocessing import StandardScaler

try:
    import lightgbm as lgb
    HAS_LGBM = True
except ImportError:
    HAS_LGBM = False
    print("WARNING: lightgbm not installed - run `pip install lightgbm`.")

DATA_DIR = "data"
OUT_DIR = os.path.join("dota_model", "artifacts")
MATCH_FILE = os.path.join(DATA_DIR, "massive_pro_dataset.csv")
HERO_FILE = os.path.join(DATA_DIR, "hero_meta_stats.csv")

TEST_FRAC = 0.15          
MIN_DURATION = 600        
SMOOTH_GAMES = 25
MIN_PAIR_GAMES = 8        
MIN_COUNTER_GAMES = 10    
BAD_TEAMS = {"", "unknown", "nan", "none"}


FEATURES = [
    "hero_wr_diff", "presence_diff", "synergy_diff", "counter_score",
    "pub_wr_diff", "hs_wr_diff",    
    "team_wr_diff", "comfort_diff",  
]
N_DRAFT = 6


def smooth(wins, games, prior=0.5, k=SMOOTH_GAMES):
    return (wins + prior * k) / (games + k)


def team_ok(t):
    return isinstance(t, str) and t.strip().lower() not in BAD_TEAMS



def load_heroes():
    """id -> hero dict with name, img, attr, pub & high-skill winrates."""
    if not os.path.exists(HERO_FILE):
        sys.exit(f"Missing {HERO_FILE}")
    df = pd.read_csv(HERO_FILE)
    heroes = {}
    for _, r in df.iterrows():
        hid = int(r["id"])
        pub_pick = float(r.get("pub_pick", 0) or 0)
        pub_win = float(r.get("pub_win", 0) or 0)
      
        hs_pick = sum(float(r.get(f"{b}_pick", 0) or 0) for b in (6, 7, 8))
        hs_win = sum(float(r.get(f"{b}_win", 0) or 0) for b in (6, 7, 8))
        pro_pick = float(r.get("pro_pick", 0) or 0)
        pro_win = float(r.get("pro_win", 0) or 0)
        heroes[hid] = {
            "id": hid,
            "name": str(r["localized_name"]),
            "img": str(r.get("img", "")),
            "icon": str(r.get("icon", "")),
            "attr": str(r.get("primary_attr", "all")),
            "roles": str(r.get("roles", "")),
            "pub_wr": smooth(pub_win, pub_pick, k=200),
            "hs_wr": smooth(hs_win, hs_pick, k=200),
            "pro_wr_meta": smooth(pro_win, pro_pick, k=10),
            "pro_ban": float(r.get("pro_ban", 0) or 0),
        }
    print(f"  loaded {len(heroes)} heroes")
    return heroes


def load_matches(heroes):
    if not os.path.exists(MATCH_FILE):
        sys.exit(f"Missing {MATCH_FILE} - run from DOTAMODEL root.")
    df = pd.read_csv(MATCH_FILE, low_memory=False)
    games, skipped = [], 0
    for _, row in df.iterrows():
        try:
            dur = float(row.get("duration", 0) or 0)
            if dur and dur < MIN_DURATION:
                skipped += 1
                continue
            g = {
                "match_id": int(row["match_id"]),
                "radiant_win": 1 if str(row["radiant_win"]).strip().lower()
                                    in ("true", "1") else 0,
                "radiant_team": str(row.get("radiant_team", "")).strip(),
                "dire_team": str(row.get("dire_team", "")).strip(),
                "radiant": [], "dire": [],
            }
            ok = True
            for side in ("radiant", "dire"):
                for i in range(1, 6):
                    hid = row.get(f"{side}_hero_{i}")
                    player = str(row.get(f"{side}_player_{i}", "")).strip()
                    if pd.isna(hid) or int(hid) not in heroes:
                        ok = False
                        break
                    g[side].append({"hero": int(hid), "player": player})
                if not ok:
                    break
            if ok and len(g["radiant"]) == 5 and len(g["dire"]) == 5:
                games.append(g)
            else:
                skipped += 1
        except (ValueError, TypeError):
            skipped += 1
    games.sort(key=lambda g: g["match_id"])   
    print(f"  loaded {len(games)} complete games ({skipped} skipped)")
    return games




def build_hero_tables(train_games):
    """Pro winrate, presence, same-team synergy, cross-team counters."""
    wins, cnt = defaultdict(float), defaultdict(int)
    pair_w, pair_n = defaultdict(float), defaultdict(int)
    ctr_w, ctr_n = defaultdict(float), defaultdict(int)
    n_games = len(train_games)

    for g in train_games:
        rad = [p["hero"] for p in g["radiant"]]
        dire = [p["hero"] for p in g["dire"]]
        for side_heroes, win in ((rad, g["radiant_win"]),
                                 (dire, 1 - g["radiant_win"])):
            for h in side_heroes:
                wins[h] += win
                cnt[h] += 1
            for a, b in combinations(sorted(side_heroes), 2):
                pair_w[(a, b)] += win
                pair_n[(a, b)] += 1
        
        for a, b in product(rad, dire):
            ctr_w[(a, b)] += g["radiant_win"]
            ctr_n[(a, b)] += 1
            ctr_w[(b, a)] += 1 - g["radiant_win"]
            ctr_n[(b, a)] += 1

    hero_wr = {h: smooth(wins[h], cnt[h]) for h in cnt}
    presence = {h: cnt[h] / (2 * n_games) for h in cnt}
    synergy = {f"{a}|{b}": smooth(pair_w[(a, b)], pair_n[(a, b)])
               for (a, b) in pair_n if pair_n[(a, b)] >= MIN_PAIR_GAMES}
    counters = {f"{a}|{b}": [round(smooth(ctr_w[(a, b)], ctr_n[(a, b)], k=10), 4),
                             ctr_n[(a, b)]]
                for (a, b) in ctr_n if ctr_n[(a, b)] >= MIN_COUNTER_GAMES}
    return hero_wr, presence, synergy, counters, cnt


def build_rosters(games, tail_frac=0.25):
    """team -> 5 most frequent players in the most recent games."""
    tail = games[int(len(games) * (1 - tail_frac)):]
    freq = defaultdict(lambda: defaultdict(int))
    for g in tail:
        for side in ("radiant", "dire"):
            team = g[f"{side}_team"]
            if not team_ok(team):
                continue
            for p in g[side]:
                if p["player"]:
                    freq[team][p["player"]] += 1
    rosters = {}
    for team, players in freq.items():
        top = sorted(players.items(), key=lambda kv: -kv[1])[:5]
        rosters[team] = [p for p, _ in top] + [""] * (5 - len(top))
    return rosters




def featurize(g, T, team_wr_pair, comfort_pair):
    def side_vals(side):
        hs = [p["hero"] for p in g[side]]
        wr = np.mean([T["hero_wr"].get(h, 0.5) for h in hs])
        pres = np.mean([T["presence"].get(h, 0.0) for h in hs])
        pairs = [T["synergy"].get(f"{a}|{b}", 0.5)
                 for a, b in combinations(sorted(hs), 2)]
        syn = np.mean(pairs)
        pub = np.mean([T["heroes"][h]["pub_wr"] for h in hs])
        hsk = np.mean([T["heroes"][h]["hs_wr"] for h in hs])
        return wr, pres, syn, pub, hsk

    rwr, rpres, rsyn, rpub, rhs = side_vals("radiant")
    dwr, dpres, dsyn, dpub, dhs = side_vals("dire")

    cs = []
    for a in (p["hero"] for p in g["radiant"]):
        for b in (p["hero"] for p in g["dire"]):
            v = T["counters"].get(f"{a}|{b}")
            if v is not None:
                cs.append(v[0] - 0.5)
    counter_score = float(np.mean(cs)) if cs else 0.0

    return [rwr - dwr, rpres - dpres, rsyn - dsyn, counter_score,
            rpub - dpub, rhs - dhs,
            team_wr_pair[0] - team_wr_pair[1],
            comfort_pair[0] - comfort_pair[1]]


def make_lgbm():
    return lgb.LGBMClassifier(
        n_estimators=1500, learning_rate=0.03, num_leaves=15,
        max_depth=4, subsample=0.8, colsample_bytree=0.9,
        reg_lambda=1.0, random_state=42, verbose=-1)




def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print("Loading data...")
    heroes = load_heroes()
    games = load_matches(heroes)

    n_test = int(len(games) * TEST_FRAC)
    train, test = games[:-n_test], games[-n_test:]
    print(f"  train: {len(train)} games, test: {len(test)} games "
          f"(last {TEST_FRAC:.0%} by match_id)")

    hero_wr, presence, synergy, counters, hero_cnt = build_hero_tables(train)
    rosters = build_rosters(games)
    print(f"  {len(synergy)} synergy pairs, {len(counters)//1} counter "
          f"matchups, {len(rosters)} teams with rosters")

    T = {"hero_wr": hero_wr, "presence": presence, "synergy": synergy,
         "counters": counters, "heroes": heroes}


    tw, tn = defaultdict(float), defaultdict(int)
    pw, pn = defaultdict(float), defaultdict(int)

    X, y, Xt, yt = [], [], [], []
    split_id = train[-1]["match_id"]
    for g in games:
        rt, dt = g["radiant_team"], g["dire_team"]
        team_pair = (smooth(tw[rt], tn[rt], k=10) if team_ok(rt) else 0.5,
                     smooth(tw[dt], tn[dt], k=10) if team_ok(dt) else 0.5)

        def comfort(side):
            vals = []
            for p in g[side]:
                key = f"{p['player'].lower()}|{p['hero']}"
                vals.append(smooth(pw[key], pn[key], k=8))
            return float(np.mean(vals))
        comfort_pair = (comfort("radiant"), comfort("dire"))

        row = featurize(g, T, team_pair, comfort_pair)
        if g["match_id"] <= split_id:
            X.append(row); y.append(g["radiant_win"])
        else:
            Xt.append(row); yt.append(g["radiant_win"])

        # update expanding state AFTER featurizing
        if team_ok(rt):
            tw[rt] += g["radiant_win"]; tn[rt] += 1
        if team_ok(dt):
            tw[dt] += 1 - g["radiant_win"]; tn[dt] += 1
        for side, win in (("radiant", g["radiant_win"]),
                          ("dire", 1 - g["radiant_win"])):
            for p in g[side]:
                key = f"{p['player'].lower()}|{p['hero']}"
                pw[key] += win; pn[key] += 1

    X, y, Xt, yt = map(np.asarray, (X, y, Xt, yt))


    scaler = StandardScaler().fit(X)
    Xs, Xts = scaler.transform(X), scaler.transform(Xt)
    lr = LogisticRegression(C=1.0, max_iter=2000).fit(Xs, y)
    lr_draft = LogisticRegression(C=1.0, max_iter=2000).fit(Xs[:, :N_DRAFT], y)
    gbm = HistGradientBoostingClassifier(
        max_depth=3, learning_rate=0.05, max_iter=400,
        validation_fraction=0.15, random_state=42).fit(X, y)

    lgbm = lgbm_draft = None
    if HAS_LGBM:
        cut = int(len(X) * 0.85)
        lgbm = make_lgbm()
        lgbm.fit(X[:cut], y[:cut], eval_set=[(X[cut:], y[cut:])],
                 callbacks=[lgb.early_stopping(100, verbose=False)])
        lgbm_draft = make_lgbm()
        lgbm_draft.fit(X[:cut, :N_DRAFT], y[:cut],
                       eval_set=[(X[cut:, :N_DRAFT], y[cut:])],
                       callbacks=[lgb.early_stopping(100, verbose=False)])

    def scores(p):
        return (roc_auc_score(yt, p), accuracy_score(yt, p > 0.5),
                log_loss(yt, p))

    lines = []
    lines.append("=" * 70)
    lines.append("DOTA 2 DRAFT WIN-PROBABILITY - MODEL COMPARISON")
    lines.append(f"Train: {len(y)} games   Test (newest): {len(yt)} games")
    lines.append(f"Radiant base winrate in train: {y.mean():.3f}")
    lines.append("=" * 70)
    lines.append("")
    lines.append("MODEL COMPARISON (full model: draft + team features)")
    lines.append("-" * 70)

    model_probs = {}
    if len(yt) > 0:
        model_probs["LogReg"] = lr.predict_proba(Xts)[:, 1]
        model_probs["HistGBM"] = gbm.predict_proba(Xt)[:, 1]
        if lgbm is not None:
            model_probs["LightGBM"] = lgbm.predict_proba(Xt)[:, 1]
        for name, p in model_probs.items():
            auc, acc, ll = scores(p)
            lines.append(f"  {name:<14} AUC={auc:.3f}  acc={acc:.3f}  "
                         f"logloss={ll:.3f}")
        best_name = max(model_probs, key=lambda k: scores(model_probs[k])[0])
        lines.append(f"  -> Best on holdout: {best_name}")
        lines.append("")

        lines.append("BACKTEST: PURELY DRAFT vs DRAFT + TEAM")
        lines.append("-" * 70)
        lines.append(f"  {'model':<10}{'features':<14}{'acc':>8}{'AUC':>8}"
                     f"{'logloss':>10}")
        p_lr_d = lr_draft.predict_proba(Xts[:, :N_DRAFT])[:, 1]
        rows = [("LogReg", "draft only", p_lr_d),
                ("LogReg", "draft+team", model_probs["LogReg"])]
        p_lgbm_d = p_lgbm_f = None
        if lgbm is not None:
            p_lgbm_d = lgbm_draft.predict_proba(Xt[:, :N_DRAFT])[:, 1]
            p_lgbm_f = model_probs["LightGBM"]
            rows += [("LightGBM", "draft only", p_lgbm_d),
                     ("LightGBM", "draft+team", p_lgbm_f)]
        for m, f, p in rows:
            auc, acc, ll = scores(p)
            lines.append(f"  {m:<10}{f:<14}{acc:>7.1%}{auc:>8.3f}{ll:>10.3f}")
        if p_lgbm_d is not None:
            gain_pts = (accuracy_score(yt, p_lgbm_f > 0.5)
                        - accuracy_score(yt, p_lgbm_d > 0.5)) * 100
            lines.append(f"  -> team information adds {gain_pts:+.1f} "
                         f"accuracy points (LightGBM)")
        lines.append("")


        lines.append("TEAM WEIGHT SWEEP (0 = ignore team, 1 = as trained)")
        lines.append("-" * 70)
        header = f"  {'w':>5}{'LR acc':>9}{'LR AUC':>9}"
        if p_lgbm_d is not None:
            header += f"{'LGBM acc':>10}{'LGBM AUC':>10}"
        lines.append(header)
        eps = 1e-6
        z_draft = lr.intercept_[0] + Xts[:, :N_DRAFT] @ lr.coef_[0][:N_DRAFT]
        z_team = Xts[:, N_DRAFT:] @ lr.coef_[0][N_DRAFT:]
        if p_lgbm_d is not None:
            ld = np.log(np.clip(p_lgbm_d, eps, 1 - eps)
                        / np.clip(1 - p_lgbm_d, eps, 1 - eps))
            lf = np.log(np.clip(p_lgbm_f, eps, 1 - eps)
                        / np.clip(1 - p_lgbm_f, eps, 1 - eps))
        best_w, best_acc = None, -1
        for w in [0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0]:
            p_lr_w = 1 / (1 + np.exp(-(z_draft + w * z_team)))
            auc_l, acc_l, _ = scores(p_lr_w)
            row = f"  {w:>5.2f}{acc_l:>8.1%}{auc_l:>9.3f}"
            if p_lgbm_d is not None:
                p_g_w = 1 / (1 + np.exp(-(ld + w * (lf - ld))))
                auc_g, acc_g, _ = scores(p_g_w)
                row += f"{acc_g:>9.1%}{auc_g:>10.3f}"
                if acc_g > best_acc:
                    best_acc, best_w = acc_g, w
            elif acc_l > best_acc:
                best_acc, best_w = acc_l, w
            lines.append(row)
        lines.append(f"  -> best weight on holdout: w={best_w:.2f} "
                     f"(acc={best_acc:.1%})")
        lines.append("")


    imp_model = lgbm if lgbm is not None else gbm
    if len(yt) > 50:
        perm = permutation_importance(imp_model, Xt, yt, n_repeats=30,
                                      scoring="roc_auc", random_state=42)
    else:
        perm = permutation_importance(imp_model, X, y, n_repeats=10,
                                      scoring="roc_auc", random_state=42)
    coefs = lr.coef_[0]
    gain = (lgbm.booster_.feature_importance("gain")
            if lgbm is not None else np.zeros(len(FEATURES)))
    gain = gain / (gain.sum() or 1)
    order = np.argsort(-perm.importances_mean)
    lines.append("FEATURE IMPORTANCE (perm on holdout; negative = hurts)")
    lines.append("-" * 70)
    lines.append(f"  {'feature':<16}{'perm_imp':>10}{'+/-':>8}"
                 f"{'lgbm_gain%':>12}{'lr_coef':>10}")
    for i in order:
        lines.append(f"  {FEATURES[i]:<16}{perm.importances_mean[i]:>10.4f}"
                     f"{perm.importances_std[i]:>8.4f}"
                     f"{100*gain[i]:>11.1f}%{coefs[i]:>10.3f}")
    lines.append("")
    lines.append("DATA WORTH ADDING LATER")
    lines.append("-" * 70)
    lines.append(" 1. start_time + patch per match (OpenDota has both)")
    lines.append(" 2. Captains Mode bans (OpenDota picks_bans field)")
    lines.append(" 3. account_id instead of player names (names change)")
    lines.append(" 4. Soloq hero-vs-hero counters (OpenDota /heroes/{id}/matchups)")
    lines.append(" 5. Elo/Glicko team ratings instead of rolling winrate")

    report_txt = "\n".join(lines)
    print("\n" + report_txt)
    with open(os.path.join(OUT_DIR, "feature_report.txt"), "w",
              encoding="utf-8") as f:
        f.write(report_txt)



    teams_final = {t: smooth(tw[t], tn[t], k=10) for t in tn if team_ok(t)}
    player_raw = {k: [round(smooth(pw[k], pn[k], k=8), 4),
                      round(pw[k] / pn[k], 4) if pn[k] else 0.5, pn[k]]
                  for k in pn}

    def jdump(obj, name):
        with open(os.path.join(OUT_DIR, name), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)

    jdump({str(h): v for h, v in heroes.items()}, "heroes.json")
    jdump({"hero_wr": {str(k): v for k, v in hero_wr.items()},
           "presence": {str(k): v for k, v in presence.items()},
           "counts": {str(k): v for k, v in hero_cnt.items()}},
          "hero_stats.json")
    jdump(synergy, "synergy.json")
    jdump(counters, "counters.json")
    jdump(player_raw, "player_stats.json")
    jdump(teams_final, "teams.json")
    jdump(rosters, "rosters.json")
    jdump({"features": FEATURES, "n_draft": N_DRAFT,
           "coef": lr.coef_[0].tolist(),
           "intercept": float(lr.intercept_[0]),
           "scaler_mean": scaler.mean_.tolist(),
           "scaler_scale": scaler.scale_.tolist()}, "lr_model.json")
    joblib.dump(gbm, os.path.join(OUT_DIR, "gbm.joblib"))
    if lgbm is not None:
        joblib.dump(lgbm, os.path.join(OUT_DIR, "lgbm.joblib"))
        joblib.dump(lgbm_draft, os.path.join(OUT_DIR, "lgbm_draft.joblib"))
    print(f"\nArtifacts written to {OUT_DIR}/")


if __name__ == "__main__":
    main()