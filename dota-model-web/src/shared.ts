export const API = 'http://localhost:8000';
export const PLACEHOLDER = '/assets/roles/ChampionSquare.png';
export const GOLD_ICON = 'https://ddragon.leagueoflegends.com/cdn/5.5.1/img/ui/gold.png';
export const ROLE_LABELS = ['TOP', 'JNG', 'MID', 'BOT', 'SUP'];
export const ROLE_KEYS = ['top', 'jng', 'mid', 'bot', 'sup'];

export interface Champion {
  id: string;
  name: string;
  image: { full: string };
  tags: string[];
}

export interface SlotInfo {
  player?: string | null;
  playerWr?: number;
  playerGames?: number;
  muWr?: number;
  muGd15?: number | null;
  muGames?: number;
}


export const C = {
  bgDeep: '#010a13',
  bgPanel: '#0a0e13',
  bgSlot: '#0d1117',
  border: '#1e2328',
  gold: '#c8aa6e',
  goldBright: '#f0e6d2',
  textDim: '#5b5a56',
  textMid: '#a09b8c',
  blue: '#0a96aa',
  blueBright: '#0ac8b9',
  blueDeep: '#0a3242',
  red: '#c6403b',
  redBright: '#e84057',
  redDeep: '#3c1214',
};


const ALIASES: Record<string, string> = {
  nunuwillump: 'nunu',
  wukong: 'monkeyking',
  renataglasc: 'renata',
};

export function normChamp(name: string): string {
  const key = (name || '').toLowerCase().replace(/[^a-z]/g, '');
  return ALIASES[key] ?? key;
}

export const GLOBAL_CSS = `
  .no-scrollbar { scrollbar-width: none; -ms-overflow-style: none; }
  .no-scrollbar::-webkit-scrollbar { display: none; width: 0; height: 0; }
  .champ-card:hover .champ-img { transform: scale(1.08); }
  .team-option:hover { background-color: #1e232866 !important; color: #f0e6d2 !important; }
  .live-row:hover { border-color: #c8aa6e88 !important; }
  @keyframes nextpulse {
    0%, 100% { box-shadow: 0 0 5px #c8aa6e44, inset 0 0 6px #c8aa6e22; }
    50% { box-shadow: 0 0 16px #c8aa6ebb, inset 0 0 10px #c8aa6e33; }
  }
  @keyframes livepulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.35; }
  }
`;