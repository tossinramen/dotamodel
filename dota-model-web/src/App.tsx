import { useState, useEffect } from 'react';
import { C, GLOBAL_CSS } from './shared.ts';
import DraftPage from './DraftPage.tsx';
import LivePage from './LivePage.tsx';
import DotaPage from './DotaPage.tsx';

export default function App() {
  const [route, setRoute] = useState<string>(window.location.pathname);

  useEffect(() => {
    const onPop = () => setRoute(window.location.pathname);
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  const navigate = (path: string) => {
    if (path === route) return;
    window.history.pushState({}, '', path);
    setRoute(path);
  };

  const isLive = route.startsWith('/live');
  const isDota = route.startsWith('/dota');
  const isDraft = !isLive && !isDota;

  const tab = (label: string, path: string, active: boolean) => (
    <span
      onClick={() => navigate(path)}
      style={{
        fontSize: '12px',
        fontWeight: 700,
        cursor: 'pointer',
        letterSpacing: '3px',
        color: active ? C.gold : C.textDim,
        borderBottom: active ? `2px solid ${C.gold}` : '2px solid transparent',
        paddingBottom: '4px',
        transition: 'color 0.15s',
      }}
    >
      {label}
    </span>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', width: '100vw', backgroundColor: C.bgDeep, color: C.goldBright, fontFamily: "'Segoe UI', 'Helvetica Neue', sans-serif", userSelect: 'none', overflow: 'hidden' }}>
      <style>{GLOBAL_CSS}</style>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 32px', height: '52px', borderBottom: `1px solid ${C.border}`, backgroundColor: C.bgPanel, flexShrink: 0 }}>
        <div
          onClick={() => navigate('/')}
          style={{ fontFamily: 'Georgia, serif', fontSize: '19px', fontWeight: 700, letterSpacing: '5px', color: C.gold, cursor: 'pointer' }}
        >
          TAH<span style={{ color: C.goldBright }}>MODEL</span>
        </div>
        <div style={{ display: 'flex', gap: '28px' }}>
          {tab('DRAFT', '/', isDraft)}
          {tab('LIVE', '/live', isLive)}
          {tab('DOTA', '/dota', isDota)}
        </div>
      </div>

      
      <div style={{ flex: 1, minHeight: 0, display: isDraft ? 'flex' : 'none', flexDirection: 'column' }}>
        <DraftPage />
      </div>
      <div style={{ flex: 1, minHeight: 0, display: isLive ? 'flex' : 'none', flexDirection: 'column' }}>
        <LivePage active={isLive} />
      </div>
      <div style={{ flex: 1, minHeight: 0, display: isDota ? 'flex' : 'none', flexDirection: 'column' }}>
        <DotaPage />
      </div>
    </div>
  );
}
