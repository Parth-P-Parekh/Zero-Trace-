const DS = () => window.ZeroTraceDesignSystem_7f4295;

function SiteNav() {
  const { Wordmark, Button } = DS();
  const [scrolled, setScrolled] = React.useState(false);
  React.useEffect(() => {
    const el = document.scrollingElement || document.documentElement;
    const on = () => setScrolled(el.scrollTop > 8);
    window.addEventListener('scroll', on, { passive: true });
    return () => window.removeEventListener('scroll', on);
  }, []);

  const link = { font: 'var(--type-body-sm)', color: 'var(--text-body)', textDecoration: 'none' };

  return (
    <header style={{ position: 'sticky', top: 0, zIndex: 30, background: scrolled ? 'rgba(232,232,230,0.72)' : 'transparent', backdropFilter: scrolled ? 'var(--blur-panel)' : 'none', boxShadow: scrolled ? 'inset 0 -1px 0 var(--border-hairline)' : 'none', transition: 'background-color var(--d-base) var(--ease-out), box-shadow var(--d-base) var(--ease-out)' }}>
      <div style={{ maxWidth: 1200, margin: '0 auto', height: 64, display: 'flex', alignItems: 'center', gap: 28, padding: '0 24px' }}>
        <Wordmark size={16} />
        <nav style={{ display: 'flex', gap: 22, marginLeft: 14 }}>
          <a href="#how" style={link}>How it works</a>
          <a href="#coverage" style={link}>Coverage</a>
          <a href="#install" style={link}>Install</a>
          <a href="#pricing" style={link}>Pricing</a>
        </nav>
        <span style={{ flex: 1 }} />
        <a href="#" style={{ ...link, color: 'var(--text-strong)' }}>Log in</a>
        <Button size="sm" pill>Start sweeping</Button>
      </div>
    </header>
  );
}
Object.assign(window, { SiteNav });
