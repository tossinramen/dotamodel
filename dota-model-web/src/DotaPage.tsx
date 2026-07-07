import { useState, useEffect, useMemo, useRef } from 'react';
import { C } from './shared.ts';

const DOTA_API = 'http://localhost:8001';
const STEAM_CDN = 'https://cdn.cloudflare.steamstatic.com';

// Radiant/Dire accents layered on top of the shared theme
const D = {
  radiant: '#3fae59',
  radiantBright: '#66d98c',
  radiantDeep: '#123a20',
  dire: C.red,
  direBright: C.redBright,
  direDeep: C.redDeep,
};

interface Hero {
  id: number;
  name: string;
  img: string;
  icon: string;
  attr: string;   // 'str' | 'agi' | 'int' | 'all'
  roles: string;
}

interface SlotInfo {
  player?: string | null;
  playerWr?: number;
  playerGames?: number;
  muWr?: number;
  muGames?: number;
}

const EMPTY_SLOTS: SlotInfo[] = [{}, {}, {}, {}, {}];

const PICK_ORDER: Array<['radiant' | 'dire', number]> = [
  ['radiant', 0], ['dire', 0], ['dire', 1], ['radiant', 1], ['radiant', 2],
  ['dire', 2], ['dire', 3], ['radiant', 3], ['radiant', 4], ['dire', 4],
];

const ATTR_FILTERS = ['ALL', 'STR', 'AGI', 'INT', 'UNI'] as const;
const ATTR_MAP: Record<string, string> = { STR: 'str', AGI: 'agi', INT: 'int', UNI: 'all' };
const ATTR_COLOR: Record<string, string> = {
  str: '#ec3d06', agi: '#26e030', int: '#00d9ec', all: '#d0a869',
};

function heroImg(h: Hero) {
  return `${STEAM_CDN}${h.img}`;
}

function TeamSelect({
  side, value, teams, onSelect, online,
}: {
  side: 'radiant' | 'dire';
  value: string;
  teams: string[];
  onSelect: (team: string) => void;
  online: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const isRad = side === 'radiant';
  const accent = isRad ? D.radiantBright : D.direBright;
  const deep = isRad ? D.radiantDeep : D.direDeep;

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
        setQuery('');
      }
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  const filtered = teams.filter((t) => t.toLowerCase().includes(query.toLowerCase()));

  return (
    <div ref={wrapRef} style={{ position: 'relative', width: '100%' }}>
      <div
        onClick={() => online && setOpen(!open)}
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '9px 14px', backgroundColor: C.bgSlot,
          border: `1px solid ${value ? deep : C.border}`,
          borderBottom: open ? `1px solid ${C.gold}` : `1px solid ${value ? deep : C.border}`,
          borderRadius: '2px', cursor: online ? 'pointer' : 'default',
          boxShadow: value ? `inset 0 0 12px ${isRad ? 'rgba(63,174,89,0.12)' : 'rgba(200,64,59,0.12)'}` : 'none',
          transition: 'border-color 0.2s',
        }}
      >
        <span style={{
          fontSize: '12px', fontWeight: value ? 700 : 400,
          letterSpacing: value ? '1.5px' : '0.5px',
          color: value ? C.goldBright : C.textDim,
          fontFamily: value ? 'Georgia, serif' : 'inherit',
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
        }}>
          {value || (online ? 'SELECT TEAM' : 'MODEL OFFLINE')}
        </span>
        <span style={{ color: value ? accent : C.gold, fontSize: '9px', transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s', marginLeft: '8px', flexShrink: 0 }}>▼</span>
      </div>

      {open && (
        <div style={{ position: 'absolute', top: 'calc(100% + 4px)', left: 0, right: 0, zIndex: 50, backgroundColor: C.bgPanel, border: `1px solid ${C.gold}55`, borderRadius: '2px', boxShadow: '0 8px 24px rgba(0,0,0,0.7)', overflow: 'hidden' }}>
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search teams..."
            style={{ width: '100%', boxSizing: 'border-box', padding: '8px 12px', backgroundColor: C.bgSlot, border: 'none', borderBottom: `1px solid ${C.border}`, color: C.goldBright, fontSize: '12px', outline: 'none' }}
          />
          <div className="no-scrollbar" style={{ maxHeight: '240px', overflowY: 'auto' }}>
            {value && (
              <div
                onClick={() => { onSelect(''); setOpen(false); setQuery(''); }}
                className="team-option"
                style={{ padding: '8px 14px', fontSize: '11px', color: C.textDim, cursor: 'pointer', letterSpacing: '1px', borderBottom: `1px solid ${C.border}` }}
              >
                ✕ CLEAR SELECTION
              </div>
            )}
            {filtered.length === 0 && (
              <div style={{ padding: '12px 14px', fontSize: '11px', color: C.textDim, letterSpacing: '1px' }}>NO TEAMS FOUND</div>
            )}
            {filtered.map((t) => (
              <div
                key={t}
                className="team-option"
                onClick={() => { onSelect(t); setOpen(false); setQuery(''); }}
                style={{ padding: '9px 14px', fontSize: '12px', letterSpacing: '0.5px', color: t === value ? C.gold : C.textMid, backgroundColor: t === value ? `${deep}66` : 'transparent', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '10px' }}
              >
                <span style={{ width: '3px', height: '14px', backgroundColor: t === value ? accent : 'transparent', flexShrink: 0 }} />
                {t}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function WinBar({
  prob, leftLabel, rightLabel, centerLabel, dim,
}: {
  prob: number;
  leftLabel: string;
  rightLabel: string;
  centerLabel?: string;
  dim?: boolean;
}) {
  return (
    <div style={{ width: '100%', height: '36px', display: 'flex', position: 'relative', fontSize: '12px', fontWeight: 700, letterSpacing: '1.5px', borderBottom: `1px solid ${C.border}`, opacity: dim ? 0.45 : 1, transition: 'opacity 0.3s' }}>
      <div style={{ width: `${prob}%`, background: `linear-gradient(90deg, ${D.radiantDeep}, ${D.radiant})`, display: 'flex', alignItems: 'center', paddingLeft: '20px', transition: 'width 0.5s ease-out', color: '#dfffe8', whiteSpace: 'nowrap', overflow: 'hidden' }}>
        {leftLabel}&nbsp;<span style={{ color: '#fff' }}>{prob.toFixed(1)}%</span>
      </div>
      <div style={{ width: `${100 - prob}%`, background: `linear-gradient(270deg, ${D.direDeep}, ${D.dire})`, display: 'flex', alignItems: 'center', justifyContent: 'flex-end', paddingRight: '20px', transition: 'width 0.5s ease-out', color: '#ffd9dc', whiteSpace: 'nowrap', overflow: 'hidden' }}>
        <span style={{ color: '#fff' }}>{(100 - prob).toFixed(1)}%</span>&nbsp;{rightLabel}
      </div>
      {centerLabel && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', pointerEvents: 'none' }}>
          <span style={{ fontSize: '9px', letterSpacing: '3px', fontWeight: 600, color: 'rgba(255,255,255,0.5)', textShadow: '0 1px 3px rgba(0,0,0,0.55)' }}>
            {centerLabel}
          </span>
        </div>
      )}
      <div style={{ position: 'absolute', left: `${prob}%`, top: 0, bottom: 0, width: '2px', backgroundColor: C.gold, transition: 'left 0.5s ease-out' }} />
    </div>
  );
}

export default function DotaPage() {
  const [heroes, setHeroes] = useState<Hero[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedAttr, setSelectedAttr] = useState<string>('ALL');
  const [selectedHero, setSelectedHero] = useState<Hero | null>(null);

  const [radPicks, setRadPicks] = useState<(Hero | null)[]>([null, null, null, null, null]);
  const [direPicks, setDirePicks] = useState<(Hero | null)[]>([null, null, null, null, null]);

  const [teamList, setTeamList] = useState<string[]>([]);
  const [radTeam, setRadTeam] = useState('');
  const [direTeam, setDireTeam] = useState('');
  const [radPlayers, setRadPlayers] = useState<string[]>(['', '', '', '', '']);
  const [direPlayers, setDirePlayers] = useState<string[]>(['', '', '', '', '']);

  const [probDraft, setProbDraft] = useState<number | null>(null);
  const [probTeam, setProbTeam] = useState<number | null>(null);
  const [slotStats, setSlotStats] = useState<{ radiant: SlotInfo[]; dire: SlotInfo[] }>({ radiant: EMPTY_SLOTS, dire: EMPTY_SLOTS });
  const [modelOnline, setModelOnline] = useState(false);
  const debounceRef = useRef<number | null>(null);

  useEffect(() => {
    fetch(`${DOTA_API}/heroes`)
      .then((r) => r.json())
      .then((hs: Hero[]) => { setHeroes(hs); setModelOnline(true); setLoading(false); })
      .catch(() => { setModelOnline(false); setLoading(false); });
    fetch(`${DOTA_API}/teams`)
      .then((r) => r.json())
      .then((t: string[]) => setTeamList(t))
      .catch(() => {});
  }, []);

  const selectTeam = (side: 'radiant' | 'dire', team: string) => {
    const setTeam = side === 'radiant' ? setRadTeam : setDireTeam;
    const setPlayers = side === 'radiant' ? setRadPlayers : setDirePlayers;
    setTeam(team);
    if (!team) {
      setPlayers(['', '', '', '', '']);
      return;
    }
    fetch(`${DOTA_API}/roster?team=${encodeURIComponent(team)}`)
      .then((r) => r.json())
      .then((players: string[]) => setPlayers(players))
      .catch(() => setPlayers(['', '', '', '', '']));
  };

  useEffect(() => {
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(() => {
      const rad = radPicks.filter(Boolean).map((h) => h!.name);
      const dire = direPicks.filter(Boolean).map((h) => h!.name);
      if (rad.length === 0 && dire.length === 0 && !radTeam && !direTeam) {
        setProbDraft(null); setProbTeam(null);
        setSlotStats({ radiant: EMPTY_SLOTS, dire: EMPTY_SLOTS });
        return;
      }
      fetch(`${DOTA_API}/predict`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ radiant: rad, dire, radiantTeam: radTeam || null, direTeam: direTeam || null }),
      })
        .then((r) => r.json())
        .then((d) => {
          setProbDraft(d.draftOnly != null ? d.draftOnly * 100 : null);
          setProbTeam(d.withTeam != null ? d.withTeam * 100 : null);
          setModelOnline(true);
        })
        .catch(() => { setModelOnline(false); setProbDraft(null); setProbTeam(null); });

      fetch(`${DOTA_API}/slotstats`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          radiant: radPicks.map((h) => (h ? h.name : null)),
          dire: direPicks.map((h) => (h ? h.name : null)),
          radiantTeam: radTeam || null,
          direTeam: direTeam || null,
        }),
      })
        .then((r) => r.json())
        .then((d) => setSlotStats(d))
        .catch(() => setSlotStats({ radiant: EMPTY_SLOTS, dire: EMPTY_SLOTS }));
    }, 350);
  }, [radPicks, direPicks, radTeam, direTeam]);

  const usedHeroIds = useMemo(() => {
    const ids = new Set<number>();
    [...radPicks, ...direPicks].forEach((h) => { if (h) ids.add(h.id); });
    return ids;
  }, [radPicks, direPicks]);

  const nextPick = useMemo(() => {
    for (const [side, idx] of PICK_ORDER) {
      const arr = side === 'radiant' ? radPicks : direPicks;
      if (!arr[idx]) return { side, idx };
    }
    return null;
  }, [radPicks, direPicks]);

  const fallbackProb = useMemo(() => {
    const r = radPicks.filter(Boolean).length;
    const d = direPicks.filter(Boolean).length;
    if (r === 0 && d === 0) return 50;
    return Math.max(15, Math.min(85, 50 + (r - d) * 4));
  }, [radPicks, direPicks]);

  const barDraft = probDraft ?? fallbackProb;
  const barTeam = probTeam ?? barDraft;
  const teamsChosen = Boolean(radTeam || direTeam);

  const placeInSlot = (hero: Hero, side: 'radiant' | 'dire', index: number) => {
    if (usedHeroIds.has(hero.id)) return;
    const [arr, set] = side === 'radiant'
      ? [radPicks, setRadPicks] as const
      : [direPicks, setDirePicks] as const;
    const n = [...arr];
    n[index] = hero;
    set(n);
  };

  const removeHero = (side: 'radiant' | 'dire', index: number) => {
    const [arr, set] = side === 'radiant'
      ? [radPicks, setRadPicks] as const
      : [direPicks, setDirePicks] as const;
    if (!arr[index]) return;
    const n = [...arr];
    n[index] = null;
    set(n);
  };

  const handleHeroClick = (hero: Hero) => {
    if (usedHeroIds.has(hero.id)) return;
    if (selectedHero?.id === hero.id) {
      setSelectedHero(null);
      return;
    }
    if (nextPick) {
      placeInSlot(hero, nextPick.side, nextPick.idx);
      setSelectedHero(null);
    } else {
      setSelectedHero(hero);
    }
  };

  const handleHeroRightClick = (e: React.MouseEvent, hero: Hero) => {
    e.preventDefault();
    if (usedHeroIds.has(hero.id)) return;
    setSelectedHero(selectedHero?.id === hero.id ? null : hero);
  };

  const handleSlotClick = (side: 'radiant' | 'dire', index: number) => {
    if (selectedHero) {
      placeInSlot(selectedHero, side, index);
      setSelectedHero(null);
    } else {
      removeHero(side, index);
    }
  };

  const filteredHeroes = useMemo(() => {
    return heroes.filter((h) => {
      const matchesSearch = h.name.toLowerCase().includes(searchQuery.toLowerCase());
      if (selectedAttr === 'ALL') return matchesSearch;
      return matchesSearch && h.attr === ATTR_MAP[selectedAttr];
    });
  }, [heroes, searchQuery, selectedAttr]);

  if (loading) {
    return (
      <div style={{ flex: 1, backgroundColor: C.bgDeep, color: C.gold, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'Georgia, serif', letterSpacing: '3px', fontSize: '14px' }}>
        LOADING ASSETS...
      </div>
    );
  }

  if (heroes.length === 0) {
    return (
      <div style={{ flex: 1, backgroundColor: C.bgDeep, color: C.textDim, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'Georgia, serif', letterSpacing: '3px', fontSize: '13px', textAlign: 'center', lineHeight: 2 }}>
        DOTA MODEL OFFLINE<br />
        <span style={{ fontSize: '11px', letterSpacing: '1px' }}>run: uvicorn dota_model.serve_dota:app --port 8001</span>
      </div>
    );
  }

  const pickSlot = (side: 'radiant' | 'dire', hero: Hero | null, idx: number) => {
    const isRad = side === 'radiant';
    const label = isRad ? `R${idx + 1}` : `D${idx + 1}`;
    const player = isRad ? radPlayers[idx] : direPlayers[idx];
    const stats: SlotInfo = (isRad ? slotStats.radiant : slotStats.dire)[idx] || {};
    const accent = isRad ? D.radiantBright : D.direBright;
    const deep = isRad ? D.radiantDeep : D.direDeep;
    const isNext = nextPick && nextPick.side === side && nextPick.idx === idx;
    const gradient = isRad
      ? 'linear-gradient(90deg, rgba(63,174,89,0.10), rgba(1,10,19,0) 60%)'
      : 'linear-gradient(270deg, rgba(200,64,59,0.12), rgba(1,10,19,0) 60%)';

    const portrait = (
      <div style={{ width: '80px', height: '48px', backgroundColor: C.bgDeep, borderRadius: '2px', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center', border: `1px solid ${hero ? deep : C.border}`, flexShrink: 0 }}>
        {hero
          ? <img src={heroImg(hero)} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          : <span style={{ color: C.textDim, fontSize: '10px', letterSpacing: '1px' }}>{label}</span>}
      </div>
    );

    const playerLine = hero && player && stats.playerWr != null && (
      <div style={{ fontSize: '10px', color: C.textMid, marginTop: '5px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
        <span style={{ color: C.gold }}>{player}</span>
        {' on '}{hero.name}: <span style={{ color: (stats.playerWr ?? 0) >= 0.5 ? D.radiantBright : D.direBright, fontWeight: 700 }}>{((stats.playerWr ?? 0) * 100).toFixed(0)}%</span>
        {' '}({stats.playerGames}G)
      </div>
    );

    const matchupLine = hero && stats.muWr != null && (
      <div style={{ fontSize: '10px', color: C.textMid, marginTop: '3px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', textAlign: isRad ? 'left' : 'right' }}>
        vs enemy draft: <span style={{ color: (stats.muWr ?? 0) >= 0.5 ? D.radiantBright : D.direBright, fontWeight: 700 }}>{((stats.muWr ?? 0) * 100).toFixed(0)}%</span> ({stats.muGames}G)
      </div>
    );

    const text = (
      <div style={{ textAlign: isRad ? 'left' : 'right', flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 600, fontSize: '14px', color: hero ? C.goldBright : C.textDim, letterSpacing: '0.5px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {hero ? hero.name : isNext ? 'Picking...' : 'Empty'}
        </div>
        <div style={{ fontSize: '10px', color: accent, marginTop: '4px', letterSpacing: '2px', fontWeight: 700, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {label}
          {player && <span style={{ color: C.gold, letterSpacing: '1px' }}> · {player.toUpperCase()}</span>}
        </div>
        {playerLine}
        {matchupLine}
      </div>
    );

    return (
      <div
        key={`${side}-${idx}`}
        onClick={() => handleSlotClick(side, idx)}
        onContextMenu={(e) => { e.preventDefault(); removeHero(side, idx); }}
        style={{
          flex: 1, minHeight: 0,
          border: isNext ? `1px solid ${C.gold}` : `1px solid ${C.border}`,
          borderLeft: isRad ? `3px solid ${hero ? accent : isNext ? C.gold : deep}` : undefined,
          borderRight: !isRad ? `3px solid ${hero ? accent : isNext ? C.gold : deep}` : undefined,
          background: `${gradient}, ${C.bgPanel}`,
          borderRadius: '3px', display: 'flex', alignItems: 'center',
          padding: '8px 14px', gap: '14px', cursor: 'pointer',
          transition: 'border-color 0.2s',
          animation: isNext ? 'nextpulse 1.6s ease-in-out infinite' : 'none',
        }}
        title={hero ? `${hero.name} (click or right-click to remove)` : isNext ? 'Next pick — click a hero to place it here' : 'Empty slot'}
      >
        {isRad ? <>{portrait}{text}</> : <>{text}{portrait}</>}
      </div>
    );
  };

  return (
    <>
      <WinBar prob={barDraft} leftLabel="RADIANT" rightLabel="DIRE" centerLabel="DRAFT ONLY" />
      <WinBar
        prob={barTeam}
        leftLabel={(radTeam || 'SELECT TEAM').toUpperCase()}
        rightLabel={(direTeam || 'SELECT TEAM').toUpperCase()}
        centerLabel="WITH TEAM STRENGTH"
        dim={!teamsChosen}
      />

      <div style={{ display: 'flex', flex: 1, padding: '16px 32px 28px', gap: '28px', overflow: 'hidden', minHeight: 0 }}>

        {/* Radiant */}
        <div style={{ width: '330px', display: 'flex', flexDirection: 'column', gap: '12px', minHeight: 0 }}>
          <h2 style={{ fontSize: '13px', color: D.radiantBright, margin: 0, textAlign: 'center', letterSpacing: '4px', fontFamily: 'Georgia, serif', fontWeight: 600 }}>RADIANT</h2>
          <TeamSelect side="radiant" value={radTeam} teams={teamList} onSelect={(t) => selectTeam('radiant', t)} online={modelOnline} />
          {radPicks.map((h, idx) => pickSlot('radiant', h, idx))}
        </div>

        {/* Hero grid */}
        <div style={{ flex: 1, maxWidth: '880px', margin: '0 auto', display: 'flex', flexDirection: 'column', backgroundColor: C.bgPanel, borderRadius: '4px', border: `1px solid ${C.border}`, overflow: 'hidden', minHeight: 0 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 20px', borderBottom: `1px solid ${C.border}`, gap: '14px' }}>
            <input
              type="text"
              placeholder="Search heroes..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ backgroundColor: C.bgSlot, border: `1px solid ${C.border}`, borderRadius: '2px', color: C.goldBright, fontSize: '14px', outline: 'none', padding: '8px 14px', width: '200px' }}
            />
            <div style={{ fontSize: '9px', letterSpacing: '1px', color: C.textDim, whiteSpace: 'nowrap' }}>
              {selectedHero
                ? `${selectedHero.name.toUpperCase()} SELECTED — CLICK ANY SLOT (OR CLICK IT AGAIN TO CANCEL)`
                : !nextPick
                  ? 'DRAFT COMPLETE'
                  : ''}
            </div>
            <div style={{ display: 'flex', gap: '16px' }}>
              {ATTR_FILTERS.map((attr) => (
                <span
                  key={attr}
                  onClick={() => setSelectedAttr(attr)}
                  style={{ fontSize: '12px', fontWeight: 700, cursor: 'pointer', letterSpacing: '1.5px', color: selectedAttr === attr ? (ATTR_COLOR[ATTR_MAP[attr]] ?? C.gold) : C.textDim, borderBottom: selectedAttr === attr ? `2px solid ${C.gold}` : '2px solid transparent', paddingBottom: '3px', transition: 'color 0.15s' }}
                >
                  {attr}
                </span>
              ))}
            </div>
          </div>

          <div className="no-scrollbar" style={{ flex: 1, overflowY: 'auto', padding: '22px', display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(92px, 1fr))', gap: '18px 12px', alignContent: 'start' }}>
            {filteredHeroes.map((h) => {
              const isSelected = selectedHero?.id === h.id;
              const isUsed = usedHeroIds.has(h.id);
              return (
                <div
                  key={h.id}
                  className="champ-card"
                  onClick={() => handleHeroClick(h)}
                  onContextMenu={(e) => handleHeroRightClick(e, h)}
                  style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', cursor: isUsed ? 'not-allowed' : 'pointer', gap: '6px', opacity: isUsed ? 0.35 : 1, transition: 'opacity 0.2s' }}
                  title={isUsed ? h.name : `${h.name} — click to pick, right-click to select for manual placement`}
                >
                  <div style={{ width: '100%', aspectRatio: '16 / 9', borderRadius: '2px', overflow: 'hidden', border: isSelected ? `2px solid ${C.gold}` : `2px solid ${isUsed ? 'transparent' : C.border}`, boxShadow: isSelected ? `0 0 10px ${C.gold}66` : 'none', position: 'relative' }}>
                    <img
                      className="champ-img"
                      src={heroImg(h)}
                      loading="lazy"
                      style={{ width: '100%', height: '100%', objectFit: 'cover', filter: isUsed ? 'grayscale(100%)' : 'none', transition: 'transform 0.2s' }}
                    />
                    <span style={{ position: 'absolute', bottom: '3px', left: '3px', width: '7px', height: '7px', borderRadius: '50%', backgroundColor: ATTR_COLOR[h.attr] ?? C.gold, boxShadow: '0 0 4px rgba(0,0,0,0.8)' }} />
                  </div>
                  <div style={{ fontSize: '11px', color: isSelected ? C.gold : isUsed ? C.textDim : C.textMid, textAlign: 'center', letterSpacing: '0.3px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', width: '100%' }}>
                    {h.name}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Dire */}
        <div style={{ width: '330px', display: 'flex', flexDirection: 'column', gap: '12px', minHeight: 0 }}>
          <h2 style={{ fontSize: '13px', color: D.direBright, margin: 0, textAlign: 'center', letterSpacing: '4px', fontFamily: 'Georgia, serif', fontWeight: 600 }}>DIRE</h2>
          <TeamSelect side="dire" value={direTeam} teams={teamList} onSelect={(t) => selectTeam('dire', t)} online={modelOnline} />
          {direPicks.map((h, idx) => pickSlot('dire', h, idx))}
        </div>

      </div>
    </>
  );
}
