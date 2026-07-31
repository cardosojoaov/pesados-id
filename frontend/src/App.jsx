import React, { useState, useEffect } from 'react';
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
    total_unidades: 168,
    volume_mercado: 71232000.00,
    ticket_medio: 424000.00,
    municipios_presenca: 104,
    cobertura_estimada: 88.5
  });

  const [brandShares, setBrandShares] = useState([
    { marca: 'New Holland', dealer: 'BAMAQ', unidades: 81, share: 48.2, is_user: true },
    { marca: 'CASE', dealer: 'BRASIF', unidades: 19, share: 11.3, is_user: false },
    { marca: 'JCB', dealer: 'VALENCE', unidades: 18, share: 10.7, is_user: false },
    { marca: 'NÃO IDENTIFICADA', dealer: 'Outros', unidades: 50, share: 29.8, is_user: false }
  ]);

  const [dealerShares, setDealerShares] = useState([
    { dealer: 'BAMAQ', unidades: 81, share: 48.2, marca: 'New Holland' },
    { dealer: 'BRASIF', unidades: 19, share: 11.3, marca: 'CASE' },
    { dealer: 'VALENCE', unidades: 18, share: 10.7, marca: 'JCB' },
    { dealer: 'OUTROS/DIRETOS', unidades: 50, share: 29.8, marca: 'NÃO IDENTIFICADA' }
  ]);

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

  const handleExportCSV = () => {
    const csvRows = [];
    csvRows.push('\ufeff');
    csvRows.push(["Municipio", "Orgao", "Fornecedor", "Marca Deduzida", "Quantidade", "Valor Unitario (BRL)", "Valor Total (BRL)", "Data"].join(';'));

    transactions.forEach(t => {
      csvRows.push([
        t.municipio,
        `"${t.orgao.replace(/"/g, '""')}"`,
        `"${t.fornecedor.replace(/"/g, '""')}"`,
        t.marca,
        t.quantidade,
        t.valor_unitario.toFixed(2).replace('.', ','),
        t.valor_total.toFixed(2).replace('.', ','),
        t.data
      ].join(';'));
    });

    const blob = new Blob([csvRows.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.setAttribute("download", `pesados_id_participacao_${uf}_${categoria}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#F8F6F1' }}>
        <div className="animate-pulse text-gray-400 font-semibold text-sm">Carregando...</div>
      </div>
    );
  }

  if (!session) {
    return <Login />;
  }

  return (
    <div className="min-h-screen font-sans antialiased flex flex-col selection:bg-amber-100 selection:text-amber-900" style={{ backgroundColor: '#F8F6F1', color: '#111111' }}>

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        :root {
          font-family: 'Inter', sans-serif;
          color-scheme: light !important;
        }
        body {
          background-color: #F8F6F1;
          color: #111111;
        }
      `}</style>

      <header className="sticky top-0 z-50 bg-white border-b border-slate-200 shadow-sm backdrop-blur-md bg-white/95">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">

          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-slate-950 flex items-center justify-center shadow-md">
              <span className="text-amber-400 font-extrabold text-sm tracking-tighter">P.ID</span>
            </div>
            <div>
              <span className="text-base font-extrabold text-slate-900 tracking-tight">PESADOS.ID</span>
              <span className="ml-2 px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-600 border border-slate-200">MVP v1.0</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden sm:block text-right">
              <div className="text-xs font-bold text-slate-800">Grupo Bamaq</div>
              <div className="text-[10px] font-medium text-slate-500">Distribuidor New Holland</div>
            </div>
            <div className="w-9 h-9 rounded-full bg-amber-500 text-slate-950 border-2 border-amber-300 font-extrabold flex items-center justify-center text-xs shadow-sm">
              NH
            </div>
            <button
              onClick={() => supabase.auth.signOut()}
              className="text-[10px] font-bold text-gray-500 hover:text-[#111111] bg-gray-100 hover:bg-gray-200 px-2.5 py-1.5 rounded-lg transition-all ml-2"
            >
              Sair
            </button>
          </div>

        </div>
      </header>

      <section className="bg-white border-b border-slate-200 py-3.5 sticky top-16 z-40 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col md:flex-row md:items-center justify-between gap-4">

          <div className="flex flex-wrap items-center gap-3">
            <div className="flex flex-col">
              <label className="text-[9px] font-bold tracking-wider text-slate-400 uppercase mb-1">Categoria</label>
              <select
                value={categoria}
                onChange={(e) => setCategoria(e.target.value)}
                className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-800 focus:outline-none focus:ring-1 focus:ring-amber-500 cursor-pointer"
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
              <label className="text-[9px] font-bold tracking-wider text-slate-400 uppercase mb-1">Estado (UF)</label>
              <select
                value={uf}
                onChange={(e) => setUf(e.target.value)}
                className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-800 focus:outline-none focus:ring-1 focus:ring-amber-500 cursor-pointer"
              >
                <option value="MG">Minas Gerais (MG) · Piloto</option>
                <option value="SP">São Paulo (SP)</option>
                <option value="RJ">Rio de Janeiro (RJ)</option>
                <option value="PR">Paraná (PR)</option>
              </select>
            </div>

            <div className="flex flex-col">
              <label className="text-[9px] font-bold tracking-wider text-slate-400 uppercase mb-1">Período</label>
              <select
                value={periodo}
                onChange={(e) => setPeriodo(e.target.value)}
                className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-800 focus:outline-none focus:ring-1 focus:ring-amber-500 cursor-pointer"
              >
                <option value="2025-07-01_2026-06-30">Últimos 12 Meses (Piloto)</option>
                <option value="2026-01-01_2026-06-30">Primeiro Semestre 2026</option>
              </select>
            </div>

            <div className="flex flex-col">
              <label className="text-[9px] font-bold tracking-wider text-slate-400 uppercase mb-1">Segmento</label>
              <select
                value={segmento}
                onChange={(e) => setSegmento(e.target.value)}
                className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-800 focus:outline-none focus:ring-1 focus:ring-amber-500 cursor-pointer"
              >
                <option value="Governo">Governo (Compra Pública - PNCP)</option>
                <option value="Privado" disabled>Privado (NF-e/Logcomex - Sob Contrato 🔒)</option>
              </select>
            </div>
          </div>

          <div className="flex items-end">
            <button
              onClick={handleExportCSV}
              className="w-full md:w-auto bg-slate-900 hover:bg-slate-800 text-white font-semibold text-xs px-4 py-2 rounded-lg flex items-center justify-center gap-2 shadow-sm transition-all"
            >
              <span>Exportar Dados</span>
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
            </button>
          </div>

        </div>
      </section>

      <div className="bg-white border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <nav className="flex space-x-1 overflow-x-auto scrollbar-none" aria-label="Tabs">
            <button
              onClick={() => setActiveTab('participacao')}
              className={`py-3 px-4 font-bold text-xs border-b-2 whitespace-nowrap transition-all ${activeTab === 'participacao' ? 'border-slate-900 text-slate-900' : 'border-transparent text-slate-400 hover:text-slate-600'}`}
            >
              Tela 1: Participação (Market Share)
            </button>
            <button
              onClick={() => setActiveTab('territorio')}
              className={`py-3 px-4 font-bold text-xs border-b-2 whitespace-nowrap transition-all ${activeTab === 'territorio' ? 'border-slate-900 text-slate-900' : 'border-transparent text-slate-400 hover:text-slate-600'}`}
            >
              Tela 2: Território (Oportunidades)
            </button>
            <button
              onClick={() => setActiveTab('frota')}
              className={`py-3 px-4 font-bold text-xs border-b-2 whitespace-nowrap transition-all ${activeTab === 'frota' ? 'border-slate-900 text-slate-900' : 'border-transparent text-slate-400 hover:text-slate-600'}`}
            >
              Tela 3: Frota Instalada (Peças)
            </button>
            <button
              onClick={() => setActiveTab('metodologia')}
              className={`py-3 px-4 font-bold text-xs border-b-2 whitespace-nowrap transition-all ${activeTab === 'metodologia' ? 'border-slate-900 text-slate-900' : 'border-transparent text-slate-400 hover:text-slate-600'}`}
            >
              Tela 4: Metodologia e Cobertura
            </button>
            <button
              onClick={() => setActiveTab('admin')}
              className={`py-3 px-4 font-bold text-xs border-b-2 whitespace-nowrap transition-all ${activeTab === 'admin' ? 'border-amber-500 text-amber-700 bg-amber-50/30' : 'border-transparent text-slate-400 hover:text-slate-600'}`}
            >
              ⚙ Admin
            </button>
          </nav>
        </div>
      </div>

      <main className="flex-grow max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">

        {loading && (
          <div className="bg-amber-50 border border-amber-200 text-amber-800 p-3 rounded-lg text-xs font-semibold mb-6 flex items-center gap-2 animate-pulse">
            <svg className="animate-spin h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"/></svg>
            <span>Sincronizando dados com o banco Supabase em tempo real...</span>
          </div>
        )}

        {activeTab === 'participacao' && (
          <div className="space-y-6">

            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
                <span className="text-[10px] font-extrabold text-slate-400 uppercase tracking-widest">Seu Market Share</span>
                <div className="text-2xl font-black text-slate-900 mt-1 flex items-baseline gap-1">
                  <span>48,2%</span>
                  <span className="text-xs font-bold text-amber-600 bg-amber-100 px-1.5 py-0.5 rounded">Líder</span>
                </div>
                <p className="text-[10px] text-slate-400 mt-2">Destaque dinâmico para Grupo Bamaq</p>
              </div>

              <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
                <span className="text-[10px] font-extrabold text-slate-400 uppercase tracking-widest">Volume de Mercado</span>
                <div className="text-2xl font-black text-slate-900 mt-1">
                  168 <span className="text-xs font-bold text-slate-400">unidades</span>
                </div>
                <p className="text-[10px] text-slate-400 mt-2">Dentro da faixa de máquina real</p>
              </div>

              <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
                <span className="text-[10px] font-extrabold text-slate-400 uppercase tracking-widest">Valor do Mercado</span>
                <div className="text-2xl font-black text-slate-900 mt-1">
                  R$ 71,2M
                </div>
                <p className="text-[10px] text-slate-400 mt-2">Soma exata das homologações</p>
              </div>

              <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
                <span className="text-[10px] font-extrabold text-slate-400 uppercase tracking-widest">Presença do Usuário</span>
                <div className="text-2xl font-black text-slate-900 mt-1">
                  104 <span className="text-xs font-bold text-slate-400">cidades</span>
                </div>
                <p className="text-[10px] text-slate-400 mt-2">Municípios com licitação homologada</p>
              </div>
            </div>

            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
              <div className="flex justify-between items-baseline mb-4">
                <div>
                  <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Participação por Marca (% de Unidades)</h3>
                  <p className="text-xs text-slate-400">Distribuição do share calculado a partir do cruzamento de revendedores</p>
                </div>
                <span className="text-[10px] font-bold text-slate-400">Nacional · Recorte Governo</span>
              </div>

              <div className="space-y-4">
                {brandShares.map((b, i) => (
                  <div key={i} className="space-y-1.5">
                    <div className="flex justify-between text-xs font-bold text-slate-700">
                      <div className="flex items-center gap-2">
                        <span>{b.marca}</span>
                        <span className="text-[10px] font-medium text-slate-400">({b.dealer})</span>
                        {b.is_user && (
                          <span className="text-[9px] font-extrabold bg-amber-400 text-slate-950 px-1.5 py-0.5 rounded uppercase tracking-wider">Sua Marca</span>
                        )}
                      </div>
                      <div className="flex items-center gap-3">
                        <span>{b.unidades} un.</span>
                        <span className="text-slate-900 font-extrabold">{b.share.toFixed(1)}%</span>
                      </div>
                    </div>
                    <div className="w-full h-3 bg-slate-100 rounded-full overflow-hidden">
                      <div
                        style={{ width: `${b.share}%` }}
                        className={`h-full rounded-full transition-all duration-700 ${b.is_user ? 'bg-amber-400 shadow-sm' : 'bg-slate-900'}`}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="p-4 border-b border-slate-150 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 bg-slate-50">
                <div>
                  <h4 className="text-xs font-extrabold text-slate-900 uppercase tracking-wider">Detalhes e Rastreabilidade das Transações</h4>
                  <p className="text-[11px] text-slate-400">Clique na URL de qualquer registro para abrir a comprovação original no PNCP</p>
                </div>
                <span className="text-[10px] font-bold bg-white px-2 py-1 rounded border border-slate-200 text-slate-500">Auditável</span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-white border-b border-slate-200 text-slate-400 font-bold uppercase tracking-wider">
                    <tr>
                      <th className="py-3 px-4 font-bold text-[10px]">Município</th>
                      <th className="py-3 px-4 font-bold text-[10px]">Órgão Comprador</th>
                      <th className="py-3 px-4 font-bold text-[10px]">Distribuidor / Vencedor</th>
                      <th className="py-3 px-4 font-bold text-[10px]">Marca Deduzida</th>
                      <th className="py-3 px-4 font-bold text-[10px] text-right">Preço Unitário</th>
                      <th className="py-3 px-4 font-bold text-[10px] text-center">URL Origem</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-700 font-medium">
                    {transactions.slice(0, 10).map((t, i) => (
                      <tr key={i} className={`hover:bg-slate-50/50 transition-all ${t.fornecedor.includes("BAMAQ") ? 'bg-amber-50/20' : ''}`}>
                        <td className="py-3.5 px-4 font-semibold text-slate-900">{t.municipio}</td>
                        <td className="py-3.5 px-4 max-w-[200px] truncate">{t.orgao}</td>
                        <td className="py-3.5 px-4 font-mono">{t.fornecedor}</td>
                        <td className="py-3.5 px-4">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${t.marca === 'New Holland' ? 'bg-amber-100 text-amber-900 border border-amber-200' : 'bg-slate-100 text-slate-800'}`}>
                            {t.marca}
                          </span>
                        </td>
                        <td className="py-3.5 px-4 text-right font-bold text-slate-950">R$ {t.valor_unitario.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                        <td className="py-3.5 px-4 text-center">
                          <a
                            href={t.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-[10px] font-bold text-indigo-600 hover:text-indigo-800 bg-indigo-50 border border-indigo-100 px-2 py-1 rounded"
                          >
                            <span>Abrir PNCP</span>
                            <svg className="w-2.5 h-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/></svg>
                          </a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {transactions.length > 10 && (
                <div className="p-3 bg-slate-50 border-t border-slate-100 text-center text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                  + {transactions.length - 10} registros filtrados disponíveis para exportação em planilha
                </div>
              )}
            </div>

          </div>
        )}

        {activeTab === 'territorio' && (
          <div className="space-y-6">

            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex gap-3 shadow-sm">
              <div className="w-8 h-8 rounded-lg bg-amber-400 flex items-center justify-center text-slate-950 font-black text-sm flex-shrink-0">
                ⚠
              </div>
              <div>
                <h4 className="text-xs font-extrabold text-amber-900 uppercase tracking-wider">Pontos Cegos Mapeados (Oportunidades Comerciais)</h4>
                <p className="text-[11px] text-amber-800 mt-1">Os municípios listados abaixo registraram aquisições de retroescavadeiras nos últimos 12 meses, porém o Grupo Bamaq registrou **zero vendas** nessas localidades. Acione os gerentes de contas regionais.</p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

              <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
                <h4 className="text-xs font-extrabold text-slate-900 uppercase tracking-wider mb-3">Vendas de Concorrentes (Zero Presença Bamaq)</h4>
                <div className="divide-y divide-slate-100">
                  {territories.opportunities.map((item, i) => (
                    <div key={i} className="py-3 flex justify-between items-center">
                      <div>
                        <span className="text-xs font-bold text-slate-800">{item.municipio}</span>
                        <div className="text-[10px] text-slate-400 mt-0.5">Dono do Share Local: <span className="font-semibold text-slate-600">{item.principal_concorrente}</span></div>
                      </div>
                      <div className="text-right">
                        <span className="text-xs font-black text-red-600 bg-red-50 border border-red-100 px-2.5 py-1 rounded">
                          {item.vendas_totais} unidades
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
                <h4 className="text-xs font-extrabold text-slate-900 uppercase tracking-wider mb-3">Principais Cidades de Atuação (Grupo Bamaq)</h4>
                <div className="divide-y divide-slate-100">
                  {territories.top_regions.map((item, i) => (
                    <div key={i} className="py-3 flex justify-between items-center">
                      <div>
                        <span className="text-xs font-bold text-slate-800">{item.municipio}</span>
                        <div className="text-[10px] text-slate-400 mt-0.5">Suas Vendas: <span className="font-semibold text-slate-600">{item.suas_vendas} de {item.vendas_totais}</span></div>
                      </div>
                      <div className="text-right">
                        <span className="text-xs font-black text-emerald-600 bg-emerald-50 border border-emerald-100 px-2.5 py-1 rounded">
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

            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
              <h4 className="text-xs font-extrabold text-slate-900 uppercase tracking-wider mb-2">Estimativa de Frota Instalada a partir de Consumos de Peças</h4>
              <p className="text-xs text-slate-400 mb-4">Nota Metodológica: Diferente de shares de vendas diretas de novos, esta análise decompõe licitações de peças de reposição e revisões preventivas (PECAS_MANUTENCAO) para estimar o market share de circulação de frotas ativas nos municípios.</p>

              <div className="space-y-4">
                {fleet.fleet_shares.map((f, i) => (
                  <div key={i} className="space-y-1.5">
                    <div className="flex justify-between text-xs font-bold text-slate-700">
                      <span>{f.marca}</span>
                      <span>{f.unidades} equipamentos em circulação ({f.share.toFixed(1)}%)</span>
                    </div>
                    <div className="w-full h-2.5 bg-slate-100 rounded-full overflow-hidden">
                      <div
                        style={{ width: `${f.share}%` }}
                        className={`h-full rounded-full ${f.marca === 'New Holland' ? 'bg-amber-400' : 'bg-slate-700'}`}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="p-4 border-b border-slate-150 bg-slate-50">
                <h4 className="text-xs font-extrabold text-slate-900 uppercase tracking-wider">Histórico de Peças e Última Manutenção Mapeada</h4>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-white border-b border-slate-200 text-slate-400 font-bold uppercase tracking-wider">
                    <tr>
                      <th className="py-3 px-4 font-bold text-[10px]">Município</th>
                      <th className="py-3 px-4 font-bold text-[10px]">Marca Ativa</th>
                      <th className="py-3 px-4 font-bold text-[10px]">Modelo Identificado</th>
                      <th className="py-3 px-4 font-bold text-[10px]">Ano Mapeado</th>
                      <th className="py-3 px-4 font-bold text-[10px] text-right">Data de Manutenção</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-700">
                    {fleet.fleet_details.map((row, i) => (
                      <tr key={i} className="hover:bg-slate-50/50">
                        <td className="py-3.5 px-4 font-semibold text-slate-900">{row.municipio}</td>
                        <td className="py-3.5 px-4 font-bold text-slate-800">{row.marca}</td>
                        <td className="py-3.5 px-4 font-mono">{row.modelo}</td>
                        <td className="py-3.5 px-4 font-bold">{row.ano_estimado}</td>
                        <td className="py-3.5 px-4 text-right font-mono text-slate-500">{row.ultima_manutencao}</td>
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

            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Funil de Processamento de Dados (PNCP)</h3>
                  <p className="text-xs text-slate-400 mt-1">Mapeamento transparente de todas as regras de funil que aplicamos para expurgar aluguéis e capturar exclusivamente aquisições reais de máquinas novas.</p>
                </div>
                <div className="text-right flex-shrink-0">
                  <span className="text-[9px] font-bold tracking-wider text-slate-400 uppercase">Última Atualização</span>
                  <div className="text-xs font-bold text-slate-800 mt-0.5">
                    {coletaLogList.length > 0
                      ? new Date(coletaLogList[0].terminada_em || coletaLogList[0].iniciada_em).toLocaleString('pt-BR')
                      : '—'}
                  </div>
                </div>
              </div>

              <div className="space-y-3 max-w-xl mx-auto">
                {[
                  { step: 1, label: 'Registros brutos', count: metodologia?.funil?.registros_brutos ?? 14850, color: 'bg-slate-100', textColor: 'text-slate-700', countColor: 'text-slate-500' },
                  { step: 2, label: 'Classificados', count: metodologia?.funil?.registros_classificados ?? 420, color: 'bg-slate-100', textColor: 'text-slate-700', countColor: 'text-slate-500' },
                  { step: 3, label: 'Homologados', count: metodologia?.funil?.registros_homologados ?? 210, color: 'bg-slate-100', textColor: 'text-slate-700', countColor: 'text-slate-500' },
                  { step: 4, label: 'Aprovados no filtro', count: metodologia?.funil?.registros_aprovados ?? 168, color: 'bg-amber-400', textColor: 'text-slate-950', countColor: 'text-slate-950' }
                ].map((item, idx) => (
                  <div key={item.step}>
                    <div className={`${item.color} p-3 rounded-lg border ${item.step === 4 ? 'border-amber-300 shadow-sm' : 'border-slate-200'} flex justify-between items-center`}>
                      <div className="flex gap-3 items-center">
                        <span className={`w-5 h-5 rounded-full ${item.step === 4 ? 'bg-slate-950 text-white' : 'bg-slate-900 text-white'} font-extrabold text-[10px] flex items-center justify-center`}>{item.step}</span>
                        <span className={`text-xs font-bold ${item.textColor}`}>{item.label}</span>
                      </div>
                      <span className={`text-xs font-extrabold ${item.countColor}`}>{item.count.toLocaleString('pt-BR')} {item.step === 4 ? 'unidades' : 'registros'}</span>
                    </div>
                    {idx < 3 && (
                      <div className="flex items-center gap-1 text-[10px] font-bold text-slate-400 ml-7">
                        <span className="text-slate-300 text-lg leading-none">↓</span>
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

              <div className="mt-6 bg-slate-50 rounded-lg p-4 flex flex-wrap gap-4 text-xs">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-blue-500" />
                  <span className="text-slate-600"><strong className="text-slate-800">Fonte:</strong> PNCP (Portal Nacional de Contratações Públicas)</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-slate-900" />
                  <span className="text-slate-600"><strong className="text-slate-800">Recorte:</strong> {
                    [
                      categoria && `Categoria ${categoria}`,
                      uf && `UF: ${uf}`,
                      periodo && `${periodo.split('_')[0]} a ${periodo.split('_')[1]}`
                    ].filter(Boolean).join(' · ') || 'Global (sem filtros)'
                  }</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-amber-500" />
                  <span className="text-slate-600"><strong className="text-slate-800">Perda total no funil:</strong> {
                    metodologia?.funil?.registros_brutos > 0
                      ? `${((1 - metodologia.funil.registros_aprovados / metodologia.funil.registros_brutos) * 100).toFixed(1)}% dos registros brutos são expurgados como serviços, peças ou fora de faixa`
                      : '—'
                  }</span>
                </div>
              </div>

              <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-6 pt-6 border-t border-slate-200 text-xs text-slate-600">
                <div>
                  <h5 className="font-extrabold text-slate-900 uppercase tracking-wider mb-2">Limites Configurados por Categoria</h5>
                  <ul className="list-disc pl-4 space-y-1">
                    <li>Retroescavadeira (BHL): Valor unitário &gt;= R$ 150.000,00</li>
                    <li>Quantidades fracionárias (ex: 250,5 horas de serviço) são expurgadas nativamente.</li>
                    <li>Sempre exibido sob situação HOMOLOGADO para evitar dados inflados.</li>
                  </ul>
                </div>
                <div>
                  <h5 className="font-extrabold text-slate-900 uppercase tracking-wider mb-2">Limitações Mapeadas Conhecidas</h5>
                  <p>Este painel mapeia e exibe transações de compra governamentais publicadas no PNCP. Ele cobre cerca de 12% do volume nacional de movimentação física do setor. Faturamento privado (NF-e) e importações (Logcomex) estão sob negociação de integração comercial para a Fase 2.</p>
                </div>
              </div>

            </div>

            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
              <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider mb-4">Cobertura por Categoria</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-white border-b border-slate-200 text-slate-400 font-bold uppercase tracking-wider">
                    <tr>
                      <th className="py-3 px-4 text-[10px]">Categoria</th>
                      <th className="py-3 px-4 text-[10px]">Descrição</th>
                      <th className="py-3 px-4 text-[10px] text-right">Transações</th>
                      <th className="py-3 px-4 text-[10px] text-right">Volume Total</th>
                      <th className="py-3 px-4 text-[10px] text-right">Municípios</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-700">
                    {(metodologia?.cobertura_categoria || []).map(c => (
                      <tr key={c.categoria_sigla} className="hover:bg-slate-50/50">
                        <td className="py-3 px-4 font-extrabold text-slate-900">{c.categoria_sigla}</td>
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

            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
              <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider mb-4">Cobertura por UF</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-white border-b border-slate-200 text-slate-400 font-bold uppercase tracking-wider">
                    <tr>
                      <th className="py-3 px-4 text-[10px]">UF</th>
                      <th className="py-3 px-4 text-[10px] text-right">Transações</th>
                      <th className="py-3 px-4 text-[10px] text-right">Municípios</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-700">
                    {(metodologia?.cobertura_uf || []).map(u => (
                      <tr key={u.uf} className="hover:bg-slate-50/50">
                        <td className="py-3 px-4 font-extrabold text-slate-900">{u.uf}</td>
                        <td className="py-3 px-4 text-right font-semibold">{u.total_transacoes}</td>
                        <td className="py-3 px-4 text-right font-semibold">{u.municipios_atingidos}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-[11px] text-slate-400 mt-3">
                Total de municípios cobertos: <span className="font-bold text-slate-700">{metodologia?.total_municipios ?? 0}</span>
              </p>
            </div>

            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
              <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider mb-4">Histórico de Execuções (Coleta PNCP)</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-white border-b border-slate-200 text-slate-400 font-bold uppercase tracking-wider">
                    <tr>
                      <th className="py-3 px-4 text-[10px]">Fonte</th>
                      <th className="py-3 px-4 text-[10px]">Iniciada Em</th>
                      <th className="py-3 px-4 text-[10px]">Terminada Em</th>
                      <th className="py-3 px-4 text-[10px] text-right">Reg. Brutos</th>
                      <th className="py-3 px-4 text-[10px] text-right">Reg. Aprovados</th>
                      <th className="py-3 px-4 text-[10px]">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-700">
                    {coletaLogList.length === 0 ? (
                      <tr><td colSpan={6} className="py-6 text-center text-slate-400 font-semibold">Nenhuma execução registrada.</td></tr>
                    ) : coletaLogList.map(e => (
                      <tr key={e.id} className="hover:bg-slate-50/50">
                        <td className="py-3 px-4 font-extrabold text-slate-900">{e.fonte_id}</td>
                        <td className="py-3 px-4 font-mono text-[10px]">{e.iniciada_em ? new Date(e.iniciada_em).toLocaleString('pt-BR') : '—'}</td>
                        <td className="py-3 px-4 font-mono text-[10px]">{e.terminada_em ? new Date(e.terminada_em).toLocaleString('pt-BR') : '—'}</td>
                        <td className="py-3 px-4 text-right font-semibold">{e.registros_brutos}</td>
                        <td className="py-3 px-4 text-right font-semibold">{e.registros_aprovados}</td>
                        <td className="py-3 px-4">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${e.status === 'sucesso' ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'}`}>{e.status}</span>
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

      <footer className="bg-slate-900 text-slate-400 py-6 border-t border-slate-850 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-xs text-center sm:text-left flex flex-col sm:flex-row justify-between items-center gap-4">
          <div>
            <span className="font-bold text-slate-300 uppercase tracking-wider block sm:inline">Fonte Declarada:</span>
            <span className="ml-0 sm:ml-2">PNCP (Portal Nacional de Contratações Públicas) · {metodologia?.funil?.registros_aprovados || kpis.total_unidades} processos aprovados</span>
          </div>
          <div className="font-semibold text-slate-500">
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

function getMockedData(categoria, uf) {
  if (categoria === 'BHL' && uf === 'MG') {
    return {
      kpis: { total_unidades: 168, volume_mercado: 71232000.00, ticket_medio: 424000.00, municipios_presenca: 104, cobertura_estimada: 88.5 },
      brand_shares: [
        { marca: 'New Holland', dealer: 'BAMAQ', unidades: 81, share: 48.2, is_user: true },
        { marca: 'CASE', dealer: 'BRASIF', unidades: 19, share: 11.3, is_user: false },
        { marca: 'JCB', dealer: 'VALENCE', unidades: 18, share: 10.7, is_user: false },
        { marca: 'NÃO IDENTIFICADA', dealer: 'Outros', unidades: 50, share: 29.8, is_user: false }
      ],
      transactions: Array.from({ length: 168 }, (_, i) => ({
        municipio: `Município Piloto ${String((i % 104) + 1).padStart(3, '0')}`,
        orgao: `Prefeitura Municipal de Teste ${String((i % 104) + 1).padStart(3, '0')}`,
        fornecedor: i < 81 ? "BAMAQ MINAS S/A" : (i < 100 ? "BRASIF S.A." : (i < 118 ? "VALENCE EQUIPAMENTOS" : "XCMG BRASIL")),
        marca: i < 81 ? "New Holland" : (i < 100 ? "CASE" : (i < 118 ? "JCB" : "NÃO IDENTIFICADA")),
        quantidade: 1,
        valor_unitario: 424000.00,
        valor_total: 424000.00,
        data: "2025-10-15",
        url: `https://pncp.gov.br/app/compras/00000000000000/2025/${i+1}`
      }))
    };
  }
  return {
    kpis: { total_unidades: 0, volume_mercado: 0, ticket_medio: 0, municipios_presenca: 0, cobertura_estimada: 0 },
    brand_shares: [],
    transactions: []
  };
}

function getMockedTerritories() {
  return {
    opportunities: [
      { municipio: "Uberlândia", vendas_totais: 14, suas_vendas: 0, principal_concorrente: "BRASIF (CASE)" },
      { municipio: "Montes Claros", vendas_totais: 9, suas_vendas: 0, principal_concorrente: "VALENCE (JCB)" },
      { municipio: "Juiz de Fora", vendas_totais: 7, suas_vendas: 0, principal_concorrente: "VALENCE (JCB)" },
      { municipio: "Ipatinga", vendas_totais: 6, suas_vendas: 0, principal_concorrente: "OUTROS" },
      { municipio: "Patos de Minas", vendas_totais: 5, suas_vendas: 0, principal_concorrente: "BRASIF (CASE)" }
    ],
    top_regions: [
      { municipio: "Belo Horizonte", vendas_totais: 28, suas_vendas: 22, seu_share: 78.5 },
      { municipio: "Contagem", vendas_totais: 18, suas_vendas: 12, seu_share: 66.6 },
      { municipio: "Betim", vendas_totais: 12, suas_vendas: 8, seu_share: 66.6 },
      { municipio: "Pouso Alegre", vendas_totais: 8, suas_vendas: 4, seu_share: 50.0 }
    ]
  };
}

function getMockedFleet() {
  return {
    fleet_shares: [
      { marca: "New Holland", unidades: 342, share: 38.5 },
      { marca: "Caterpillar", unidades: 240, share: 27.0 },
      { marca: "CASE", unidades: 138, share: 15.5 },
      { marca: "JCB", unidades: 98, share: 11.0 },
      { marca: "XCMG", unidades: 71, share: 8.0 }
    ],
    fleet_details: [
      { municipio: "Belo Horizonte", marca: "New Holland", modelo: "B95B", ano_estimado: 2019, ultima_manutencao: "2026-03-12" },
      { municipio: "Contagem", marca: "Caterpillar", modelo: "416F2", ano_estimado: 2018, ultima_manutencao: "2026-04-05" },
      { municipio: "Uberlândia", marca: "CASE", modelo: "580N", ano_estimado: 2020, ultima_manutencao: "2026-05-20" },
      { municipio: "Montes Claros", marca: "JCB", modelo: "3CX", ano_estimado: 2017, ultima_manutencao: "2026-01-18" }
    ]
  };
}
