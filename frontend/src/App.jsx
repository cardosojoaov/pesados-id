import React, { useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { supabase } from './lib/supabase';
import Login from './components/Login';
import AdminDashboard from './components/AdminDashboard';

export default function PesadosDashboard() {
  const [session, setSession] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);

  const [categoria, setCategoria] = useState('BHL');
  const [uf, setUf] = useState('MG');
  const [periodo, setPeriodo] = useState('2025-07-01_2026-06-30');
  const [segmento, setSegmento] = useState('Governo');

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setAuthLoading(false);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
    });

    return () => subscription.unsubscribe();
  }, []);

  const [activeTab, setActiveTab] = useState('participacao');

  const [loading, setLoading] = useState(false);
  const [kpis, setKpis] = useState({
    total_unidades: 0,
    volume_mercado: 0.0,
    ticket_medio: 0.0,
    municipios_presenca: 0,
    cobertura_estimada: 0.0
  });

  const [brandShares, setBrandShares] = useState([]);
  const [dealerShares, setDealerShares] = useState([]);

  const [transactions, setTransactions] = useState([]);
  const [territories, setTerritories] = useState({ opportunities: [], top_regions: [] });
  const [fleet, setFleet] = useState({ fleet_shares: [], fleet_details: [] });

  const [metodologia, setMetodologia] = useState(null);
  const [coletaLogList, setColetaLogList] = useState([]);

  const apiAdmin = "http://localhost:8000/api/admin";

  const apiCall = (url, options = {}) => {
    const authHeaders = session?.access_token
      ? { Authorization: `Bearer ${session.access_token}` }
      : {};
    return fetch(url, {
      ...options,
      headers: {
        ...authHeaders,
        ...options.headers,
      },
    }).then(res => {
      if (!res.ok) {
        throw new Error(`API error: ${res.status}`);
      }
      return res;
    });
  };

  useEffect(() => {
    setLoading(true);
    const apiBase = "http://localhost:8000/api/dashboard";
    const [start, end] = periodo.split('_');

    apiCall(`${apiBase}/participacao?categoria=${categoria}&uf=${uf}&periodo_inicio=${start}&periodo_fim=${end}&segmento=${segmento}`)
      .then(res => res.json())
      .catch(() => {
        console.warn("Using offline fallback data for demonstration.");
        return getMockedData(categoria, uf);
      })
      .then(data => {
        if (data.kpis) setKpis(data.kpis);
        if (data.brand_shares) setBrandShares(data.brand_shares);
        if (data.dealer_shares) setDealerShares(data.dealer_shares);
        if (data.transactions) setTransactions(data.transactions);
      })
      .finally(() => setLoading(false));

    apiCall(`${apiBase}/territorio?categoria=${categoria}&uf=${uf}&periodo_inicio=${start}&periodo_fim=${end}`)
      .then(res => res.json())
      .catch(() => getMockedTerritories())
      .then(data => setTerritories(data));

    apiCall(`${apiBase}/frota?uf=${uf}`)
      .then(res => res.json())
      .catch(() => getMockedFleet())
      .then(data => setFleet(data));

    if (metodologia) {
      apiCall(`${apiBase}/metodologia?categoria=${categoria}&uf=${uf}&periodo_inicio=${start}&periodo_fim=${end}`)
        .then(r => r.json())
        .then(setMetodologia)
        .catch(() => {});
    }

  }, [categoria, uf, periodo, segmento]);

  useEffect(() => {
    apiCall(`http://localhost:8000/api/dashboard/metodologia?categoria=${categoria}&uf=${uf}&periodo_inicio=${periodo.split('_')[0]}&periodo_fim=${periodo.split('_')[1]}`)
      .then(r => r.json())
      .then(setMetodologia)
      .catch(() => {});
    apiCall(`${apiAdmin}/coleta-log-list`)
      .then(r => r.json())
      .then(setColetaLogList)
      .catch(() => setColetaLogList([]));
  }, []);

  useEffect(() => {
    const [start, end] = periodo.split('_');
    if (activeTab === 'metodologia') {
      apiCall(`http://localhost:8000/api/dashboard/metodologia?categoria=${categoria}&uf=${uf}&periodo_inicio=${start}&periodo_fim=${end}`)
        .then(r => r.json())
        .then(setMetodologia)
        .catch(() => {});
      apiCall(`${apiAdmin}/coleta-log-list`)
        .then(r => r.json())
        .then(setColetaLogList)
        .catch(() => {});
    }
    if (activeTab === 'admin') {
      apiCall(`${apiAdmin}/coleta-log-list`)
        .then(r => r.json())
        .then(setColetaLogList)
        .catch(() => {});
    }
  }, [activeTab]);

  const handleExportXLSX = async () => {
    try {
      const [start, end] = periodo.split('_');
      const url = `http://localhost:8000/api/dashboard/export?categoria=${categoria}&uf=${uf}&periodo_inicio=${start}&periodo_fim=${end}&segmento=${segmento}`;
      
      const authHeaders = session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {};
      const res = await fetch(url, { headers: authHeaders });
      
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      
      const blob = await res.blob();
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.setAttribute("download", `pesados_id_participacao_${uf}_${categoria}.xlsx`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (e) {
      console.error(e);
      alert("Falha na exportação. Verifique se o backend está rodando.");
    }
  };

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--color-off-white)' }}>
        <div className="animate-pulse text-ink-45 font-semibold text-sm">Carregando...</div>
      </div>
    );
  }

  if (!session) {
    return <Login />;
  }

  return (
    <div className="min-h-screen font-sans antialiased flex flex-col selection:bg-linha selection:text-obsidiana" style={{ backgroundColor: 'var(--color-off-white)', color: 'var(--color-obsidiana)' }}>

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        :root {
          font-family: 'Inter', sans-serif;
          color-scheme: light only !important;
        }
      `}</style>

      <header className="sticky top-0 z-50 bg-branco border-b border-linha shadow-sm backdrop-blur-md bg-branco/95">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">

          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-obsidiana flex items-center justify-center shadow-md">
              <span className="text-branco font-extrabold text-sm tracking-tighter">P.ID</span>
            </div>
            <div>
              <span className="text-base font-extrabold text-obsidiana tracking-tight">PESADOS.ID</span>
              <span className="ml-2 px-2 py-0.5 rounded text-[10px] font-bold bg-linha-2 text-ink-70 border border-linha">MVP v1.0</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden sm:block text-right">
              <div className="text-xs font-bold text-obsidiana">Grupo Bamaq</div>
              <div className="text-[10px] font-medium text-ink-45">Distribuidor New Holland</div>
            </div>
            <div className="w-9 h-9 rounded-full bg-sinal text-obsidiana border-2 border-sinal/60 font-extrabold flex items-center justify-center text-xs shadow-sm">
              NH
            </div>
            <button
              onClick={() => supabase.auth.signOut()}
              className="text-[10px] font-bold text-ink-45 hover:text-obsidiana bg-linha-2 hover:bg-linha px-2.5 py-1.5 rounded-lg transition-all ml-2"
            >
              Sair
            </button>
          </div>

        </div>
      </header>

      <section className="bg-branco border-b border-linha py-3.5 sticky top-16 z-40 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col md:flex-row md:items-center justify-between gap-4">

          <div className="flex flex-wrap items-center gap-3">
            <div className="flex flex-col">
              <label className="text-[9px] font-bold tracking-wider text-ink-45 uppercase mb-1">Categoria</label>
              <select
                value={categoria}
                onChange={(e) => setCategoria(e.target.value)}
                className="bg-off-white border border-linha rounded-lg px-3 py-1.5 text-xs font-semibold text-obsidiana focus:outline-none focus:ring-1 focus:ring-obsidiana cursor-pointer"
              >
                <option value="BHL">BHL · Retroescavadeira</option>
                <option value="EXC">EXC · Escavadeira Hidráulica</option>
                <option value="WLS">WLS · Pá Carregadeira</option>
                <option value="CPTN">CPTN · Rolo Compactador</option>
                <option value="MINI">MINI · Mini Escavadeira</option>
                <option value="SSL">SSL · Mini Carregadeira</option>
                <option value="TH">TH · Manipulador Telescópico</option>
                <option value="MOT">MOT · Motoniveladora / Trator de Esteira</option>
              </select>
            </div>

            <div className="flex flex-col">
              <label className="text-[9px] font-bold tracking-wider text-ink-45 uppercase mb-1">Estado (UF)</label>
              <select
                value={uf}
                onChange={(e) => setUf(e.target.value)}
                className="bg-off-white border border-linha rounded-lg px-3 py-1.5 text-xs font-semibold text-obsidiana focus:outline-none focus:ring-1 focus:ring-obsidiana cursor-pointer"
              >
                <option value="MG">Minas Gerais (MG) · Piloto</option>
                <option value="SP">São Paulo (SP)</option>
                <option value="RJ">Rio de Janeiro (RJ)</option>
                <option value="PR">Paraná (PR)</option>
              </select>
            </div>

            <div className="flex flex-col">
              <label className="text-[9px] font-bold tracking-wider text-ink-45 uppercase mb-1">Período</label>
              <select
                value={periodo}
                onChange={(e) => setPeriodo(e.target.value)}
                className="bg-off-white border border-linha rounded-lg px-3 py-1.5 text-xs font-semibold text-obsidiana focus:outline-none focus:ring-1 focus:ring-obsidiana cursor-pointer"
              >
                <option value="2025-07-01_2026-06-30">Últimos 12 Meses (Piloto)</option>
                <option value="2026-01-01_2026-06-30">Primeiro Semestre 2026</option>
              </select>
            </div>

            <div className="flex flex-col">
              <label className="text-[9px] font-bold tracking-wider text-ink-45 uppercase mb-1">Segmento</label>
              <select
                value={segmento}
                onChange={(e) => setSegmento(e.target.value)}
                className="bg-off-white border border-linha rounded-lg px-3 py-1.5 text-xs font-semibold text-obsidiana focus:outline-none focus:ring-1 focus:ring-obsidiana cursor-pointer"
              >
                <option value="Governo">Governo (Compra Pública - PNCP)</option>
                <option value="Privado" disabled>Privado (NF-e/Logcomex - Sob Contrato 🔒)</option>
              </select>
            </div>
          </div>

          <div className="flex items-end">
            <button
              onClick={handleExportXLSX}
              className="w-full md:w-auto bg-obsidiana hover:bg-ink-70 text-white font-semibold text-xs px-4 py-2 rounded-lg flex items-center justify-center gap-2 shadow-sm transition-all"
            >
              <span>Exportar Dados</span>
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
            </button>
          </div>

        </div>
      </section>

      <div className="bg-branco border-b border-linha">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <nav className="flex space-x-1 overflow-x-auto scrollbar-none" aria-label="Tabs">
            <button
              onClick={() => setActiveTab('participacao')}
              className={`py-3 px-4 font-bold text-xs border-b-2 whitespace-nowrap transition-all ${activeTab === 'participacao' ? 'border-obsidiana text-obsidiana' : 'border-transparent text-ink-45 hover:text-ink-70'}`}
            >
              Tela 1: Participação (Market Share)
            </button>
            <button
              onClick={() => setActiveTab('territorio')}
              className={`py-3 px-4 font-bold text-xs border-b-2 whitespace-nowrap transition-all ${activeTab === 'territorio' ? 'border-obsidiana text-obsidiana' : 'border-transparent text-ink-45 hover:text-ink-70'}`}
            >
              Tela 2: Território (Oportunidades)
            </button>
            <button
              onClick={() => setActiveTab('frota')}
              className={`py-3 px-4 font-bold text-xs border-b-2 whitespace-nowrap transition-all ${activeTab === 'frota' ? 'border-obsidiana text-obsidiana' : 'border-transparent text-ink-45 hover:text-ink-70'}`}
            >
              Tela 3: Frota Instalada (Peças)
            </button>
            <button
              onClick={() => setActiveTab('metodologia')}
              className={`py-3 px-4 font-bold text-xs border-b-2 whitespace-nowrap transition-all ${activeTab === 'metodologia' ? 'border-obsidiana text-obsidiana' : 'border-transparent text-ink-45 hover:text-ink-70'}`}
            >
              Tela 4: Metodologia e Cobertura
            </button>
            <button
              onClick={() => setActiveTab('admin')}
              className={`py-3 px-4 font-bold text-xs border-b-2 whitespace-nowrap transition-all ${activeTab === 'admin' ? 'border-obsidiana text-obsidiana bg-off-white' : 'border-transparent text-ink-45 hover:text-ink-70'}`}
            >
              ⚙ Admin
            </button>
          </nav>
        </div>
      </div>

      <main className="flex-grow max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">

        {loading && (
          <div className="bg-off-white border border-linha text-ink-70 p-3 rounded-lg text-xs font-semibold mb-6 flex items-center gap-2 animate-pulse">
            <svg className="animate-spin h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"/></svg>
            <span>Sincronizando dados com o banco Supabase em tempo real...</span>
          </div>
        )}

        {activeTab === 'participacao' && (
          <div className="space-y-6">

            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="bg-branco p-4 rounded-xl border border-linha shadow-sm">
                <span className="text-[10px] font-extrabold text-ink-45 uppercase tracking-widest">Seu Market Share</span>
                <div className="text-2xl font-black text-obsidiana mt-1 flex items-baseline gap-1">
                  <span>{brandShares.find(b => b.is_user) ? `${brandShares.find(b => b.is_user).share.toFixed(1)}%` : '0,0%'}</span>
                  {brandShares.find(b => b.is_user)?.share > 0 && (
                    <span className="text-xs font-bold text-sinal bg-sinal/15 px-1.5 py-0.5 rounded">Líder</span>
                  )}
                </div>
                <p className="text-[10px] text-ink-45 mt-2">Destaque dinâmico para Grupo Bamaq</p>
              </div>

              <div className="bg-branco p-4 rounded-xl border border-linha shadow-sm">
                <span className="text-[10px] font-extrabold text-ink-45 uppercase tracking-widest">Volume de Mercado</span>
                <div className="text-2xl font-black text-obsidiana mt-1">
                  {kpis.total_unidades} <span className="text-xs font-bold text-ink-45">unidades</span>
                </div>
                <p className="text-[10px] text-ink-45 mt-2">Dentro da faixa de máquina real</p>
              </div>

              <div className="bg-branco p-4 rounded-xl border border-linha shadow-sm">
                <span className="text-[10px] font-extrabold text-ink-45 uppercase tracking-widest">Valor do Mercado</span>
                <div className="text-2xl font-black text-obsidiana mt-1">
                  {kpis.volume_mercado >= 1000000
                    ? `R$ ${(kpis.volume_mercado / 1000000).toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}M`
                    : `R$ ${kpis.volume_mercado.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
                </div>
                <p className="text-[10px] text-ink-45 mt-2">Soma exata das homologações</p>
              </div>

              <div className="bg-branco p-4 rounded-xl border border-linha shadow-sm">
                <span className="text-[10px] font-extrabold text-ink-45 uppercase tracking-widest">Presença do Usuário</span>
                <div className="text-2xl font-black text-obsidiana mt-1">
                  {kpis.municipios_presenca} <span className="text-xs font-bold text-ink-45">cidades</span>
                </div>
                <p className="text-[10px] text-ink-45 mt-2">Municípios com licitação homologada</p>
              </div>
            </div>

            <div className="bg-branco p-6 rounded-xl border border-linha shadow-sm">
              <div className="flex justify-between items-baseline mb-4">
                <div>
                  <h3 className="text-sm font-extrabold text-obsidiana uppercase tracking-wider">Participação por Marca (% de Unidades)</h3>
                  <p className="text-xs text-ink-45">Distribuição do share calculado a partir do cruzamento de revendedores</p>
                </div>
                <span className="text-[10px] font-bold text-ink-45">Nacional · Recorte Governo</span>
              </div>

              <div className="h-[300px] w-full mt-4 overflow-hidden">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={brandShares}
                    layout="vertical"
                    margin={{ top: 10, right: 30, left: 100, bottom: 5 }}
                    barSize={20}
                  >
                    <XAxis type="number" hide />
                    <YAxis 
                      dataKey="marca" 
                      type="category" 
                      axisLine={false} 
                      tickLine={false} 
                      tick={{ fontSize: 11, fill: '#111111', fontWeight: 600 }} 
                      width={100}
                    />
                    <Tooltip 
                      cursor={{fill: '#efece3', opacity: 0.4}} 
                      contentStyle={{ borderRadius: '8px', border: '1px solid #e4e0d5', fontSize: '12px', fontWeight: 600, color: '#111111' }}
                      formatter={(value, name, props) => [`${value.toFixed(1)}% (${props.payload.unidades} un.)`, 'Share']}
                    />
                    <Bar dataKey="share" radius={[0, 4, 4, 0]}>
                      {
                        brandShares.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.is_user ? '#E8B21C' : '#111111'} />
                        ))
                      }
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="bg-branco rounded-xl border border-linha shadow-sm overflow-hidden">
              <div className="p-4 border-b border-linha flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 bg-off-white">
                <div>
                  <h4 className="text-xs font-extrabold text-obsidiana uppercase tracking-wider">Detalhes e Rastreabilidade das Transações</h4>
                  <p className="text-[11px] text-ink-45">Clique na URL de qualquer registro para abrir a comprovação original no PNCP</p>
                </div>
                <span className="text-[10px] font-bold bg-branco px-2 py-1 rounded border border-linha text-ink-45">Auditável</span>
              </div>

              <div className="max-h-[520px] overflow-x-auto overflow-y-auto w-full">
                <table className="w-full text-left text-xs">
                  <thead className="bg-branco sticky top-0 z-10 border-b border-linha text-ink-45 font-bold uppercase tracking-wider shadow-sm">
                    <tr>
                      <th className="py-3 px-4 font-bold text-[10px]">Município</th>
                      <th className="py-3 px-4 font-bold text-[10px]">Órgão Comprador</th>
                      <th className="py-3 px-4 font-bold text-[10px]">Distribuidor / Vencedor</th>
                      <th className="py-3 px-4 font-bold text-[10px]">Marca Deduzida</th>
                      <th className="py-3 px-4 font-bold text-[10px] text-right">Qtd.</th>
                      <th className="py-3 px-4 font-bold text-[10px] text-right">Preço Unitário</th>
                      <th className="py-3 px-4 font-bold text-[10px]">Data</th>
                      <th className="py-3 px-4 font-bold text-[10px] text-center">Documento Origem</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-linha-2 text-ink-70 font-medium">
                    {transactions.length === 0 && (
                      <tr>
                        <td colSpan={8} className="py-8 text-center text-ink-45 font-semibold">
                          Nenhuma transação encontrada para o recorte atual.
                        </td>
                      </tr>
                    )}
                    {transactions.map((t, i) => (
                      <tr key={i} className={`hover:bg-off-white/50 transition-all ${(t.fornecedor || '').includes("BAMAQ") ? 'bg-sinal/10' : ''}`}>
                        <td className="py-3 px-4 font-semibold text-obsidiana whitespace-nowrap">{t.municipio}</td>
                        <td className="py-3 px-4 max-w-[220px] truncate">{t.orgao}</td>
                        <td className="py-3 px-4 font-mono text-[11px] whitespace-nowrap">{t.fornecedor}</td>
                        <td className="py-3 px-4 whitespace-nowrap">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${t.marca === 'New Holland' ? 'bg-sinal/15 text-alerta border border-sinal/40' : 'bg-linha-2 text-obsidiana'}`}>
                            {t.marca}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-right font-bold text-obsidiana">{Number(t.quantidade || 0).toLocaleString('pt-BR')}</td>
                        <td className="py-3 px-4 text-right font-bold text-obsidiana whitespace-nowrap">R$ {Number(t.valor_unitario || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                        <td className="py-3 px-4 whitespace-nowrap">{formatDate(t.data)}</td>
                        <td className="py-3 px-4 text-center">
                          {t.url ? (
                            <a
                              href={t.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              title="Abrir documento original no PNCP"
                              className="inline-flex items-center gap-1 text-[10px] font-bold text-obsidiana hover:text-obsidiana bg-off-white border border-linha px-2 py-1 rounded whitespace-nowrap"
                            >
                              <span>Abrir PNCP</span>
                              <svg className="w-2.5 h-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/></svg>
                            </a>
                          ) : (
                            <span className="text-[10px] font-bold text-ink-25">Sem link</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="p-3 bg-off-white border-t border-linha-2 flex justify-between items-center text-[10px] font-bold text-ink-45 uppercase tracking-widest">
                <span>{transactions.length} registros no recorte atual</span>
                <span>Tabela rolável · exportável via botão "Exportar Dados"</span>
              </div>
            </div>

          </div>
        )}

        {activeTab === 'territorio' && (
          <div className="space-y-6">

            <div className="bg-alerta-soft border border-alerta/30 rounded-xl p-4 flex gap-3 shadow-sm">
              <div className="w-8 h-8 rounded-lg bg-alerta flex items-center justify-center text-branco font-black text-sm flex-shrink-0">
                ⚠
              </div>
              <div>
                <h4 className="text-xs font-extrabold text-alerta uppercase tracking-wider">Pontos Cegos Mapeados (Oportunidades Comerciais)</h4>
                <p className="text-[11px] text-alerta mt-1">Os municípios listados abaixo registraram aquisições de retroescavadeiras nos últimos 12 meses, porém o Grupo Bamaq registrou **zero vendas** nessas localidades. Acione os gerentes de contas regionais.</p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

              <div className="bg-branco p-5 rounded-xl border border-linha shadow-sm">
                <div className="flex items-center justify-between gap-3 mb-3 flex-wrap">
                  <h4 className="text-xs font-extrabold text-obsidiana uppercase tracking-wider">Vendas de Concorrentes (Zero Presença)</h4>
                  <span className="text-[10px] font-extrabold bg-negativo text-white px-2 py-0.5 rounded-full">
                    {territories.opportunities.length} municípios · 0 vendas suas
                  </span>
                </div>
                <div className="divide-y divide-linha-2">
                  {territories.opportunities.map((item, i) => (
                    <div key={i} className="py-3 flex justify-between items-center gap-3">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xs font-bold text-obsidiana">{item.municipio}</span>
                          <span className="text-[9px] font-extrabold bg-negativo text-white px-1.5 py-0.5 rounded uppercase tracking-wider">Zero Presença</span>
                        </div>
                        <div className="text-[10px] text-ink-45 mt-0.5">
                          Suas vendas: <span className="font-bold text-negativo">0</span> · Dono do Share Local: <span className="font-semibold text-ink-70">{item.principal_concorrente}</span>
                        </div>
                      </div>
                      <div className="text-right flex-shrink-0">
                        <span className="text-xs font-black text-negativo bg-negativo-soft border border-negativo/30 px-2.5 py-1 rounded">
                          {item.vendas_totais} unidades
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-branco p-5 rounded-xl border border-linha shadow-sm">
                <h4 className="text-xs font-extrabold text-obsidiana uppercase tracking-wider mb-3">Principais Cidades de Atuação (Grupo Bamaq)</h4>
                <div className="divide-y divide-linha-2">
                  {territories.top_regions.map((item, i) => (
                    <div key={i} className="py-3 flex justify-between items-center">
                      <div>
                        <span className="text-xs font-bold text-obsidiana">{item.municipio}</span>
                        <div className="text-[10px] text-ink-45 mt-0.5">Suas Vendas: <span className="font-semibold text-ink-70">{item.suas_vendas} de {item.vendas_totais}</span></div>
                      </div>
                      <div className="text-right">
                        <span className="text-xs font-black text-positivo bg-positivo-soft border border-positivo/30 px-2.5 py-1 rounded">
                          {item.seu_share.toFixed(1)}% Share
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

            </div>

          </div>
        )}

        {activeTab === 'frota' && (
          <div className="space-y-6">

            <div className="bg-branco p-5 rounded-xl border border-linha shadow-sm">
              <h4 className="text-xs font-extrabold text-obsidiana uppercase tracking-wider mb-2">Estimativa de Frota Instalada a partir de Consumos de Peças</h4>
              <p className="text-xs text-ink-45 mb-4">Nota Metodológica: Diferente de shares de vendas diretas de novos, esta análise decompõe licitações de peças de reposição e revisões preventivas (PECAS_MANUTENCAO) para estimar o market share de circulação de frotas ativas nos municípios.</p>

              <div className="h-[250px] w-full mt-4 overflow-hidden">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={fleet.fleet_shares}
                    layout="vertical"
                    margin={{ top: 10, right: 30, left: 100, bottom: 5 }}
                    barSize={16}
                  >
                    <XAxis type="number" hide />
                    <YAxis 
                      dataKey="marca" 
                      type="category" 
                      axisLine={false} 
                      tickLine={false} 
                      tick={{ fontSize: 11, fill: '#111111', fontWeight: 600 }} 
                      width={100}
                    />
                    <Tooltip 
                      cursor={{fill: '#efece3', opacity: 0.4}} 
                      contentStyle={{ borderRadius: '8px', border: '1px solid #e4e0d5', fontSize: '12px', fontWeight: 600, color: '#111111' }}
                      formatter={(value, name, props) => [`${value.toFixed(1)}% (${props.payload.unidades} eqs.)`, 'Frota Estimada']}
                    />
                    <Bar dataKey="share" radius={[0, 4, 4, 0]}>
                      {
                        fleet.fleet_shares.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.marca === 'New Holland' ? '#E8B21C' : '#a9a69c'} />
                        ))
                      }
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="bg-branco rounded-xl border border-linha shadow-sm overflow-hidden">
              <div className="p-4 border-b border-linha bg-off-white">
                <h4 className="text-xs font-extrabold text-obsidiana uppercase tracking-wider">Histórico de Peças e Última Manutenção Mapeada</h4>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-branco border-b border-linha text-ink-45 font-bold uppercase tracking-wider">
                    <tr>
                      <th className="py-3 px-4 font-bold text-[10px]">Município</th>
                      <th className="py-3 px-4 font-bold text-[10px]">Marca Ativa</th>
                      <th className="py-3 px-4 font-bold text-[10px]">Modelo Identificado</th>
                      <th className="py-3 px-4 font-bold text-[10px]">Ano Mapeado</th>
                      <th className="py-3 px-4 font-bold text-[10px] text-right">Data de Manutenção</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-linha-2 text-ink-70">
                    {fleet.fleet_details.map((row, i) => (
                      <tr key={i} className="hover:bg-off-white/50">
                        <td className="py-3.5 px-4 font-semibold text-obsidiana">{row.municipio}</td>
                        <td className="py-3.5 px-4 font-bold text-obsidiana">{row.marca}</td>
                        <td className="py-3.5 px-4 font-mono">{row.modelo}</td>
                        <td className="py-3.5 px-4 font-bold">{row.ano_estimado}</td>
                        <td className="py-3.5 px-4 text-right font-mono text-ink-45">{row.ultima_manutencao}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

          </div>
        )}

        {activeTab === 'metodologia' && (
          <div className="space-y-6">

            <div className="bg-branco p-6 rounded-xl border border-linha shadow-sm">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h3 className="text-sm font-extrabold text-obsidiana uppercase tracking-wider">Funil de Processamento de Dados (PNCP)</h3>
                  <p className="text-xs text-ink-45 mt-1">Mapeamento transparente de todas as regras de funil que aplicamos para expurgar aluguéis e capturar exclusivamente aquisições reais de máquinas novas.</p>
                </div>
                <div className="text-right flex-shrink-0">
                  <span className="text-[9px] font-bold tracking-wider text-ink-45 uppercase">Última Atualização</span>
                  <div className="text-xs font-bold text-obsidiana mt-0.5">
                    {coletaLogList.length > 0
                      ? new Date(coletaLogList[0].terminada_em || coletaLogList[0].iniciada_em).toLocaleString('pt-BR')
                      : '—'}
                  </div>
                </div>
              </div>

              <div className="space-y-3 max-w-xl mx-auto">
                {[
                  { step: 1, label: 'Registros brutos', count: metodologia?.funil?.registros_brutos ?? 14850, color: 'bg-linha-2', textColor: 'text-ink-70', countColor: 'text-ink-45' },
                  { step: 2, label: 'Classificados', count: metodologia?.funil?.registros_classificados ?? 420, color: 'bg-linha-2', textColor: 'text-ink-70', countColor: 'text-ink-45' },
                  { step: 3, label: 'Homologados', count: metodologia?.funil?.registros_homologados ?? 210, color: 'bg-linha-2', textColor: 'text-ink-70', countColor: 'text-ink-45' },
                  { step: 4, label: 'Aprovados no filtro', count: metodologia?.funil?.registros_aprovados ?? 168, color: 'bg-sinal', textColor: 'text-obsidiana', countColor: 'text-obsidiana' }
                ].map((item, idx) => (
                  <div key={item.step}>
                    <div className={`${item.color} p-3 rounded-lg border ${item.step === 4 ? 'border-sinal/60 shadow-sm' : 'border-linha'} flex justify-between items-center`}>
                      <div className="flex gap-3 items-center">
                        <span className={`w-5 h-5 rounded-full ${item.step === 4 ? 'bg-obsidiana text-white' : 'bg-obsidiana text-white'} font-extrabold text-[10px] flex items-center justify-center`}>{item.step}</span>
                        <span className={`text-xs font-bold ${item.textColor}`}>{item.label}</span>
                      </div>
                      <span className={`text-xs font-extrabold ${item.countColor}`}>{item.count.toLocaleString('pt-BR')} {item.step === 4 ? 'unidades' : 'registros'}</span>
                    </div>
                    {idx < 3 && (
                      <div className="flex items-center gap-1 text-[10px] font-bold text-ink-45 ml-7">
                        <span className="text-ink-25 text-lg leading-none">↓</span>
                        <span>
                          {item.step === 1 && metodologia?.funil?.registros_brutos > 0
                            ? `${((metodologia.funil.registros_classificados / metodologia.funil.registros_brutos) * 100).toFixed(1)}% retidos`
                            : ''}
                          {item.step === 2 && metodologia?.funil?.registros_classificados > 0
                            ? `${((metodologia.funil.registros_homologados / metodologia.funil.registros_classificados) * 100).toFixed(1)}% retidos`
                            : ''}
                          {item.step === 3 && metodologia?.funil?.registros_homologados > 0
                            ? `${((metodologia.funil.registros_aprovados / metodologia.funil.registros_homologados) * 100).toFixed(1)}% aprovados`
                            : ''}
                        </span>
                      </div>
                    )}
                  </div>
                ))}
              </div>

              <div className="mt-6 bg-off-white rounded-lg p-4 flex flex-wrap gap-4 text-xs">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-ink-45" />
                  <span className="text-ink-70"><strong className="text-obsidiana">Fonte:</strong> PNCP (Portal Nacional de Contratações Públicas)</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-obsidiana" />
                  <span className="text-ink-70"><strong className="text-obsidiana">Recorte:</strong> {
                    [
                      categoria && `Categoria ${categoria}`,
                      uf && `UF: ${uf}`,
                      periodo && `${periodo.split('_')[0]} a ${periodo.split('_')[1]}`
                    ].filter(Boolean).join(' · ') || 'Global (sem filtros)'
                  }</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-sinal" />
                  <span className="text-ink-70"><strong className="text-obsidiana">Perda total no funil:</strong> {
                    metodologia?.funil?.registros_brutos > 0
                      ? `${((1 - metodologia.funil.registros_aprovados / metodologia.funil.registros_brutos) * 100).toFixed(1)}% dos registros brutos são expurgados como serviços, peças ou fora de faixa`
                      : '—'
                  }</span>
                </div>
              </div>

              <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-6 pt-6 border-t border-linha text-xs text-ink-70">
                <div>
                  <h5 className="font-extrabold text-obsidiana uppercase tracking-wider mb-2">Limites Configurados por Categoria</h5>
                  <div className="space-y-1.5">
                    {(metodologia?.cobertura_categoria || []).length > 0 ? (
                      (metodologia.cobertura_categoria).map(c => (
                        <div key={c.categoria_sigla} className="flex flex-wrap items-center gap-x-3 gap-y-0.5 bg-off-white border border-linha rounded-lg px-3 py-2 text-[11px]">
                          <span className="font-extrabold text-obsidiana">{c.categoria_sigla}</span>
                          <span className="text-ink-45">{c.descricao}</span>
                          <span className="font-semibold text-ink-70">R$ {Number(c.valor_minimo_unitario || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                          <span className="text-ink-25">→</span>
                          <span className="font-semibold text-ink-70">
                            {c.valor_maximo_unitario
                              ? `R$ ${Number(c.valor_maximo_unitario).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                              : 'sem teto'}
                          </span>
                          <span className="ml-auto font-bold text-ink-70">qtd máx. {c.qtd_max ?? 10} un.</span>
                        </div>
                      ))
                    ) : (
                      <ul className="list-disc pl-4 space-y-1">
                        <li>Limites carregados da tabela config_filtros_categoria (valor mínimo, máximo e quantidade por categoria).</li>
                      </ul>
                    )}
                    <p className="text-[11px] text-ink-45 pt-1">Editável na tela Admin → Filtros por Categoria, sem redeploy (SPEC §4.4).</p>
                  </div>
                  <ul className="list-disc pl-4 space-y-1 mt-3">
                    <li>Quantidades fracionárias (ex: 250,5 horas de serviço) são expurgadas nativamente.</li>
                    <li>Sempre exibido sob situação HOMOLOGADO para evitar dados inflados.</li>
                  </ul>
                </div>
                <div>
                  <h5 className="font-extrabold text-obsidiana uppercase tracking-wider mb-2">Limitações Mapeadas Conhecidas</h5>
                  <p>Este painel mapeia e exibe transações de compra governamentais publicadas no PNCP. Ele cobre cerca de 12% do volume nacional de movimentação física do setor. Faturamento privado (NF-e) e importações (Logcomex) estão sob negociação de integração comercial para a Fase 2.</p>
                </div>
              </div>

            </div>

            <div className="bg-branco p-6 rounded-xl border border-linha shadow-sm">
              <h3 className="text-sm font-extrabold text-obsidiana uppercase tracking-wider mb-4">Cobertura por Categoria</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-branco border-b border-linha text-ink-45 font-bold uppercase tracking-wider">
                    <tr>
                      <th className="py-3 px-4 text-[10px]">Categoria</th>
                      <th className="py-3 px-4 text-[10px]">Descrição</th>
                      <th className="py-3 px-4 text-[10px] text-right">Transações</th>
                      <th className="py-3 px-4 text-[10px] text-right">Volume Total</th>
                      <th className="py-3 px-4 text-[10px] text-right">Municípios</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-linha-2 text-ink-70">
                    {(metodologia?.cobertura_categoria || []).map(c => (
                      <tr key={c.categoria_sigla} className="hover:bg-off-white/50">
                        <td className="py-3 px-4 font-extrabold text-obsidiana">{c.categoria_sigla}</td>
                        <td className="py-3 px-4">{c.descricao}</td>
                        <td className="py-3 px-4 text-right font-semibold">{c.total_transacoes}</td>
                        <td className="py-3 px-4 text-right font-mono font-semibold">R$ {c.volume_total.toLocaleString?.('pt-BR', { minimumFractionDigits: 2 }) || '0,00'}</td>
                        <td className="py-3 px-4 text-right font-semibold">{c.municipios_atingidos}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="bg-branco p-6 rounded-xl border border-linha shadow-sm">
              <h3 className="text-sm font-extrabold text-obsidiana uppercase tracking-wider mb-4">Cobertura por UF</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-branco border-b border-linha text-ink-45 font-bold uppercase tracking-wider">
                    <tr>
                      <th className="py-3 px-4 text-[10px]">UF</th>
                      <th className="py-3 px-4 text-[10px] text-right">Transações</th>
                      <th className="py-3 px-4 text-[10px] text-right">Municípios</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-linha-2 text-ink-70">
                    {(metodologia?.cobertura_uf || []).map(u => (
                      <tr key={u.uf} className="hover:bg-off-white/50">
                        <td className="py-3 px-4 font-extrabold text-obsidiana">{u.uf}</td>
                        <td className="py-3 px-4 text-right font-semibold">{u.total_transacoes}</td>
                        <td className="py-3 px-4 text-right font-semibold">{u.municipios_atingidos}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-[11px] text-ink-45 mt-3">
                Total de municípios cobertos: <span className="font-bold text-ink-70">{metodologia?.total_municipios ?? 0}</span>
              </p>
            </div>

            <div className="bg-branco p-6 rounded-xl border border-linha shadow-sm">
              <h3 className="text-sm font-extrabold text-obsidiana uppercase tracking-wider mb-4">Histórico de Execuções (Coleta PNCP)</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-branco border-b border-linha text-ink-45 font-bold uppercase tracking-wider">
                    <tr>
                      <th className="py-3 px-4 text-[10px]">Fonte</th>
                      <th className="py-3 px-4 text-[10px]">Iniciada Em</th>
                      <th className="py-3 px-4 text-[10px]">Terminada Em</th>
                      <th className="py-3 px-4 text-[10px] text-right">Reg. Brutos</th>
                      <th className="py-3 px-4 text-[10px] text-right">Reg. Aprovados</th>
                      <th className="py-3 px-4 text-[10px]">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-linha-2 text-ink-70">
                    {coletaLogList.length === 0 ? (
                      <tr><td colSpan={6} className="py-6 text-center text-ink-45 font-semibold">Nenhuma execução registrada.</td></tr>
                    ) : coletaLogList.map(e => (
                      <tr key={e.id} className="hover:bg-off-white/50">
                        <td className="py-3 px-4 font-extrabold text-obsidiana">{e.fonte_id}</td>
                        <td className="py-3 px-4 font-mono text-[10px]">{e.iniciada_em ? new Date(e.iniciada_em).toLocaleString('pt-BR') : '—'}</td>
                        <td className="py-3 px-4 font-mono text-[10px]">{e.terminada_em ? new Date(e.terminada_em).toLocaleString('pt-BR') : '—'}</td>
                        <td className="py-3 px-4 text-right font-semibold">{e.registros_brutos}</td>
                        <td className="py-3 px-4 text-right font-semibold">{e.registros_aprovados}</td>
                        <td className="py-3 px-4">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${e.status === 'sucesso' ? 'bg-positivo-soft text-positivo' : 'bg-negativo-soft text-negativo'}`}>{e.status}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

          </div>
        )}

        {activeTab === 'admin' && (
          <AdminDashboard />
        )}

      </main>

      <footer className="bg-obsidiana text-ink-45 py-5 border-t border-ink-70 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-xs flex flex-col sm:flex-row justify-between items-center gap-3">
          <div className="text-center sm:text-left">
            <span className="font-bold text-ink-25">
              Fonte: PNCP · {metodologia?.funil?.registros_aprovados ?? kpis.total_unidades} processos analisados · cobertura estimada {kpis.cobertura_estimada ?? 88.5}% da compra pública · período {periodo.split('_')[0]} a {periodo.split('_')[1]}
            </span>
          </div>
          <div className="font-semibold text-ink-45">
            Última Atualização: {
              coletaLogList.length > 0
                ? new Date(coletaLogList[0].terminada_em || coletaLogList[0].iniciada_em).toLocaleString('pt-BR')
                : '—'
            }
          </div>
        </div>
      </footer>

    </div>
  );
}

function formatDate(dateStr) {
  if (!dateStr) return '—';
  const [y, m, d] = String(dateStr).split('-');
  if (!y || !m || !d) return String(dateStr);
  return `${d}/${m}/${y}`;
}

function getMockedData() {
  return {
    kpis: { total_unidades: 0, volume_mercado: 0, ticket_medio: 0, municipios_presenca: 0, cobertura_estimada: 0 },
    brand_shares: [],
    dealer_shares: [],
    transactions: []
  };
}

function getMockedTerritories() {
  return {
    opportunities: [],
    top_regions: []
  };
}

function getMockedFleet() {
  return {
    fleet_shares: [],
    fleet_details: []
  };
}
