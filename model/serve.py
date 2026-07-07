import json
import os
from itertools import combinations

import joblib
import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ART = os.path.join(os.path.dirname(__file__), "artifacts")


def jload(name):
    with open(os.path.join(ART, name), encoding="utf-8") as f:
        return json.load(f)


HEROES = {int(k): v for k, v in jload("heroes.json").items()}
NAME2ID = {v["name"].lower(): k for k, v in HEROES.items()}
HS = jload("hero_stats.json")
HERO_WR = {int(k): v for k, v in HS["hero_wr"].items()}
PRESENCE = {int(k): v for k, v in HS["presence"].items()}
SYNERGY = jload("synergy.json")
COUNTERS = jload("counters.json")          
PLAYERS = jload("player_stats.json")       
TEAMS = jload("teams.json")
ROSTERS = jload("rosters.json")
LRM = jload("lr_model.json")
N_DRAFT = LRM["n_draft"]

GBM = joblib.load(os.path.join(ART, "gbm.joblib"))
try:
    LGBM = joblib.load(os.path.join(ART, "lgbm.joblib"))
    LGBM_DRAFT = joblib.load(os.path.join(ART, "lgbm_draft.joblib"))
except FileNotFoundError:
    LGBM = LGBM_DRAFT = None

app = FastAPI()
app.add_middleware(
    CORSMiddleware, allow_origins=["*"],
    allow_methods=["*"], allow_headers=["*"],
)


class PredictReq(BaseModel):
    radiant: list[str] = []
    dire: list[str] = []
    radiantTeam: str | None = None
    direTeam: str | None = None


class SlotReq(BaseModel):
    radiant: list[str | None] = [None] * 5
    dire: list[str | None] = [None] * 5
    radiantTeam: str | None = None
    direTeam: str | None = None


def to_ids(names):
    out = []
    for n in names:
        if n and n.lower() in NAME2ID:
            out.append(NAME2ID[n.lower()])
    return out


def comfort_val(player, hid):
    if not player:
        return 0.5
    v = PLAYERS.get(f"{player.lower()}|{hid}")
    return v[0] if v else 0.5


def build_features(rad_ids, dire_ids, rad_team, dire_team,
                   rad_players=None, dire_players=None):
    def side_vals(ids):
        if not ids:
            return 0.5, 0.0, 0.5, 0.5, 0.5
        wr = float(np.mean([HERO_WR.get(h, 0.5) for h in ids]))
        pres = float(np.mean([PRESENCE.get(h, 0.0) for h in ids]))
        pairs = [SYNERGY.get(f"{a}|{b}", 0.5)
                 for a, b in combinations(sorted(ids), 2)]
        syn = float(np.mean(pairs)) if pairs else 0.5
        pub = float(np.mean([HEROES[h]["pub_wr"] for h in ids]))
        hsk = float(np.mean([HEROES[h]["hs_wr"] for h in ids]))
        return wr, pres, syn, pub, hsk

    rwr, rpres, rsyn, rpub, rhs = side_vals(rad_ids)
    dwr, dpres, dsyn, dpub, dhs = side_vals(dire_ids)

    cs = []
    for a in rad_ids:
        for b in dire_ids:
            v = COUNTERS.get(f"{a}|{b}")
            if v is not None:
                cs.append(v[0] - 0.5)
    counter_score = float(np.mean(cs)) if cs else 0.0

    team_diff = (TEAMS.get(rad_team, 0.5) if rad_team else 0.5) \
        - (TEAMS.get(dire_team, 0.5) if dire_team else 0.5)

    def comfort(ids, players):
        if not ids or not players:
            return 0.5
        vals = [comfort_val(p, h) for p, h in zip(players, ids) if h]
        return float(np.mean(vals)) if vals else 0.5

    rp = rad_players or (ROSTERS.get(rad_team, []) if rad_team else [])
    dp = dire_players or (ROSTERS.get(dire_team, []) if dire_team else [])
    comfort_diff = comfort(rad_ids, rp) - comfort(dire_ids, dp)

    return np.array([[rwr - dwr, rpres - dpres, rsyn - dsyn, counter_score,
                      rpub - dpub, rhs - dhs, team_diff, comfort_diff]])


def lr_prob(x, draft_only=False):
    mean = np.array(LRM["scaler_mean"])
    scale = np.array(LRM["scaler_scale"])
    xs = (x[0] - mean) / scale
    coef = np.array(LRM["coef"])
    if draft_only:
        z = LRM["intercept"] + xs[:N_DRAFT] @ coef[:N_DRAFT]
    else:
        z = LRM["intercept"] + xs @ coef
    return float(1 / (1 + np.exp(-z)))


@app.get("/heroes")
def heroes():
    return [{"id": h["id"], "name": h["name"], "img": h["img"],
             "icon": h["icon"], "attr": h["attr"], "roles": h["roles"]}
            for h in sorted(HEROES.values(), key=lambda x: x["name"])]


@app.get("/teams")
def teams():
    return sorted(ROSTERS.keys())


@app.get("/roster")
def roster(team: str = ""):
    return ROSTERS.get(team, ["", "", "", "", ""])


@app.post("/predict")
def predict(req: PredictReq):
    rad, dire = to_ids(req.radiant), to_ids(req.dire)
    if not rad and not dire and not req.radiantTeam and not req.direTeam:
        return {"draftOnly": None, "withTeam": None}
    x = build_features(rad, dire, req.radiantTeam, req.direTeam)
    if LGBM is not None:
        draft_p = float(LGBM_DRAFT.predict_proba(x[:, :N_DRAFT])[0, 1])
        full_p = float(LGBM.predict_proba(x)[0, 1])
    else:
        draft_p = lr_prob(x, draft_only=True)
        full_p = float(GBM.predict_proba(x)[0, 1])
    return {"draftOnly": draft_p, "withTeam": full_p}


@app.post("/slotstats")
def slotstats(req: SlotReq):
    rad_ids = [NAME2ID.get((n or "").lower()) for n in req.radiant]
    dire_ids = [NAME2ID.get((n or "").lower()) for n in req.dire]
    rad_roster = ROSTERS.get(req.radiantTeam or "", [""] * 5)
    dire_roster = ROSTERS.get(req.direTeam or "", [""] * 5)

    def side(ids, roster, enemy_ids):
        out = []
        enemies = [e for e in enemy_ids if e]
        for i in range(5):
            info = {}
            hid = ids[i] if i < len(ids) else None
            player = roster[i] if i < len(roster) else ""
            info["player"] = player or None
            if hid and player:
                v = PLAYERS.get(f"{player.lower()}|{hid}")
                if v:
                    info["playerWr"] = v[1]
                    info["playerGames"] = v[2]
            if hid and enemies:
                # aggregate matchup vs everything on the enemy draft
                ws, ns = 0.0, 0
                for e in enemies:
                    v = COUNTERS.get(f"{hid}|{e}")
                    if v:
                        ws += v[0] * v[1]
                        ns += v[1]
                if ns:
                    info["muWr"] = round(ws / ns, 4)
                    info["muGames"] = ns
            out.append(info)
        return out

    return {"radiant": side(rad_ids, rad_roster, dire_ids),
            "dire": side(dire_ids, dire_roster, rad_ids)}