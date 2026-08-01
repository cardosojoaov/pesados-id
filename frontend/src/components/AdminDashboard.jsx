import { useState, useEffect } from 'react'
import { supabase } from '../lib/supabase'

const API = 'http://localhost:8000/api/admin'

async function apiCall(url, options = {}) {
  const { data: { session } } = await supabase.auth.getSession()
  const authHeaders = session?.access_token
    ? { Authorization: `Bearer ${session.access_token}` }
    : {}
  const res = await fetch(url, {
    ...options,
    headers: { ...authHeaders, ...options.headers },
  })
  if (!res.ok) {
    throw new Error(`API error: ${res.status}`)
  }
  return res
}

const TABS = [
  { key: 'fornecedores', label: 'Fornecedores' },
  { key: 'dealer-marca', label: 'Dealer → Marca' },
  { key: 'filtros', label: 'Filtros por Categoria' },
  { key: 'nao-identificadas', label: 'Não Identificadas' },
  { key: 'coleta', label: 'Coleta PNCP' },
]

export default function AdminDashboard() {
  const [tab, setTab] = useState('fornecedores')
  const [msg, setMsg] = useState('')

  const [rules, setRules] = useState([])
  const [editingRule, setEditingRule] = useState(null)

  const [mappings, setMappings] = useState([])
  const [editingMapping, setEditingMapping] = useState(null)

  const [filters, setFilters] = useState([])
  const [editingFilter, setEditingFilter] = useState(null)

  const [orphans, setOrphans] = useState([])
  const [coletaLog, setColetaLog] = useState('')
  const [coletaLogList, setColetaLogList] = useState([])
  const [coletaRunning, setColetaRunning] = useState(false)

  useEffect(() => {
    apiCall(`${API}/normalizacao`).then(r => r.json()).then(setRules).catch(() => setRules([]))
    apiCall(`${API}/dealer-marca`).then(r => r.json()).then(setMappings).catch(() => setMappings([]))
    apiCall(`${API}/filtros-categoria`).then(r => r.json()).then(setFilters).catch(() => setFilters([]))
    apiCall(`${API}/nao-identificadas`).then(r => r.json()).then(setOrphans).catch(() => setOrphans([]))
    apiCall(`${API}/coleta-log-list`).then(r => r.json()).then(setColetaLogList).catch(() => setColetaLogList([]))
  }, [])

  const refreshRules = () => apiCall(`${API}/normalizacao`).then(r => r.json()).then(setRules)
  const refreshMappings = () => apiCall(`${API}/dealer-marca`).then(r => r.json()).then(setMappings)
  const refreshOrphans = () => apiCall(`${API}/nao-identificadas`).then(r => r.json()).then(setOrphans)

  function showMsg(text) {
    setMsg(text)
    setTimeout(() => setMsg(''), 4000)
  }

  return (
    <div className="space-y-6">
      {msg && (
        <div className="bg-off-white border border-linha text-ink-70 p-3 rounded-lg text-xs font-semibold flex items-center gap-2">
          <span>{msg}</span>
          <button onClick={() => setMsg('')} className="ml-auto text-ink-45 font-bold">✕</button>
        </div>
      )}

      <div className="bg-branco border-b border-linha rounded-xl overflow-hidden">
        <div className="flex space-x-1 overflow-x-auto p-1 bg-off-white">
          {TABS.map(s => (
            <button key={s.key} onClick={() => setTab(s.key)}
              className={`py-2 px-3 font-bold text-xs rounded-lg whitespace-nowrap transition-all ${tab === s.key ? 'bg-branco text-obsidiana shadow-sm border border-linha' : 'text-ink-45 hover:text-ink-70'}`}>
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {tab === 'fornecedores' && (
        <div className="bg-branco rounded-xl border border-linha shadow-sm overflow-hidden">
          <div className="p-4 border-b border-linha bg-off-white flex justify-between items-center">
            <div>
              <h4 className="text-xs font-extrabold text-obsidiana uppercase tracking-wider">Normalização de Fornecedores</h4>
              <p className="text-[11px] text-ink-45">Termo de busca → Nome normalizado (usado no trigger de INSERT)</p>
            </div>
            <button onClick={() => setEditingRule({ termo_busca: '', nome_normalizado: '' })}
              className="bg-obsidiana text-white text-[10px] font-bold px-3 py-1.5 rounded-lg">
              + Novo
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-branco border-b border-linha text-ink-45 font-bold uppercase tracking-wider">
                <tr>
                  <th className="py-3 px-4 text-[10px]">Termo de Busca</th>
                  <th className="py-3 px-4 text-[10px]">Nome Normalizado</th>
                  <th className="py-3 px-4 text-[10px] text-right">Ações</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-linha-2 text-ink-70">
                {rules.map(r => (
                  <tr key={r.id} className="hover:bg-off-white/50">
                    <td className="py-3 px-4 font-mono font-semibold text-obsidiana">{r.termo_busca}</td>
                    <td className="py-3 px-4 font-semibold">{r.nome_normalizado}</td>
                    <td className="py-3 px-4 text-right">
                      <button onClick={() => setEditingRule(r)}
                        className="text-[10px] font-bold text-obsidiana hover:text-obsidiana bg-off-white border border-linha px-2 py-1 rounded mr-1">Editar</button>
                      <button onClick={() => {
                        apiCall(`${API}/normalizacao/${r.id}`, { method: 'DELETE' })
                          .then(() => refreshRules())
                          .then(() => showMsg('Regra excluída.'))
                      }}
                        className="text-[10px] font-bold text-negativo hover:text-negativo bg-negativo-soft border border-negativo/30 px-2 py-1 rounded">Excluir</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {editingRule !== null && (
            <div className="p-4 border-t border-linha bg-off-white">
              <div className="flex flex-wrap gap-3 items-end">
                <div className="flex flex-col">
                  <label className="text-[9px] font-bold text-ink-45 uppercase mb-1">Termo de Busca</label>
                  <input value={editingRule.termo_busca}
                    onChange={e => setEditingRule({ ...editingRule, termo_busca: e.target.value })}
                    className="bg-branco border border-linha rounded-lg px-3 py-1.5 text-xs font-semibold w-48" />
                </div>
                <div className="flex flex-col">
                  <label className="text-[9px] font-bold text-ink-45 uppercase mb-1">Nome Normalizado</label>
                  <input value={editingRule.nome_normalizado}
                    onChange={e => setEditingRule({ ...editingRule, nome_normalizado: e.target.value })}
                    className="bg-branco border border-linha rounded-lg px-3 py-1.5 text-xs font-semibold w-48" />
                </div>
                <button onClick={() => {
                  const method = editingRule.id ? 'PUT' : 'POST'
                  const url = editingRule.id ? `${API}/normalizacao/${editingRule.id}` : `${API}/normalizacao`
                  apiCall(url, {
                    method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ termo_busca: editingRule.termo_busca, nome_normalizado: editingRule.nome_normalizado })
                  }).then(r => r.json()).then(() => {
                    setEditingRule(null)
                    refreshRules()
                    showMsg('Regra salva com sucesso.')
                  })
                }}
                  className="bg-obsidiana text-white text-[10px] font-bold px-4 py-2 rounded-lg">
                  Salvar
                </button>
                <button onClick={() => setEditingRule(null)}
                  className="text-[10px] font-bold text-ink-45 bg-branco border border-linha px-4 py-2 rounded-lg">Cancelar</button>
              </div>
            </div>
          )}
        </div>
      )}

      {tab === 'dealer-marca' && (
        <div className="bg-branco rounded-xl border border-linha shadow-sm overflow-hidden">
          <div className="p-4 border-b border-linha bg-off-white flex justify-between items-center">
            <div>
              <h4 className="text-xs font-extrabold text-obsidiana uppercase tracking-wider">Mapeamento Dealer → Marca</h4>
              <p className="text-[11px] text-ink-45">Vínculo fornecedor normalizado → fabricante com vigência e confiança</p>
            </div>
            <button onClick={() => setEditingMapping({
              fornecedor_normalizado: '', marca: '', confianca: 'confirmado',
              data_inicio_vigencia: '2025-01-01', data_fim_vigencia: ''
            })}
              className="bg-obsidiana text-white text-[10px] font-bold px-3 py-1.5 rounded-lg">
              + Novo
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-branco border-b border-linha text-ink-45 font-bold uppercase tracking-wider">
                <tr>
                  <th className="py-3 px-4 text-[10px]">Fornecedor</th>
                  <th className="py-3 px-4 text-[10px]">Marca</th>
                  <th className="py-3 px-4 text-[10px]">Confiança</th>
                  <th className="py-3 px-4 text-[10px]">Início Vig.</th>
                  <th className="py-3 px-4 text-[10px]">Fim Vig.</th>
                  <th className="py-3 px-4 text-[10px] text-right">Ações</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-linha-2 text-ink-70">
                {mappings.map(m => (
                  <tr key={m.id} className="hover:bg-off-white/50">
                    <td className="py-3 px-4 font-semibold text-obsidiana">{m.fornecedor_normalizado}</td>
                    <td className="py-3 px-4 font-semibold">{m.marca}</td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${m.confianca === 'confirmado' ? 'bg-positivo-soft text-positivo' : 'bg-alerta-soft text-alerta'}`}>{m.confianca}</span>
                    </td>
                    <td className="py-3 px-4">{m.data_inicio_vigencia}</td>
                    <td className="py-3 px-4">{m.data_fim_vigencia || '—'}</td>
                    <td className="py-3 px-4 text-right">
                      <button onClick={() => setEditingMapping(m)}
                        className="text-[10px] font-bold text-obsidiana hover:text-obsidiana bg-off-white border border-linha px-2 py-1 rounded mr-1">Editar</button>
                      <button onClick={() => {
                        apiCall(`${API}/dealer-marca/${m.id}`, { method: 'DELETE' })
                          .then(() => refreshMappings())
                          .then(() => showMsg('Mapping excluído.'))
                      }}
                        className="text-[10px] font-bold text-negativo hover:text-negativo bg-negativo-soft border border-negativo/30 px-2 py-1 rounded">Excluir</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {editingMapping !== null && (
            <div className="p-4 border-t border-linha bg-off-white">
              <div className="flex flex-wrap gap-3 items-end">
                <div className="flex flex-col">
                  <label className="text-[9px] font-bold text-ink-45 uppercase mb-1">Fornecedor</label>
                  <input value={editingMapping.fornecedor_normalizado}
                    onChange={e => setEditingMapping({ ...editingMapping, fornecedor_normalizado: e.target.value })}
                    className="bg-branco border border-linha rounded-lg px-3 py-1.5 text-xs font-semibold w-36" />
                </div>
                <div className="flex flex-col">
                  <label className="text-[9px] font-bold text-ink-45 uppercase mb-1">Marca</label>
                  <input value={editingMapping.marca}
                    onChange={e => setEditingMapping({ ...editingMapping, marca: e.target.value })}
                    className="bg-branco border border-linha rounded-lg px-3 py-1.5 text-xs font-semibold w-36" />
                </div>
                <div className="flex flex-col">
                  <label className="text-[9px] font-bold text-ink-45 uppercase mb-1">Confiança</label>
                  <select value={editingMapping.confianca}
                    onChange={e => setEditingMapping({ ...editingMapping, confianca: e.target.value })}
                    className="bg-branco border border-linha rounded-lg px-3 py-1.5 text-xs font-semibold">
                    <option value="confirmado">Confirmado</option>
                    <option value="presumido">Presumido</option>
                  </select>
                </div>
                <div className="flex flex-col">
                  <label className="text-[9px] font-bold text-ink-45 uppercase mb-1">Início Vig.</label>
                  <input type="date" value={editingMapping.data_inicio_vigencia}
                    onChange={e => setEditingMapping({ ...editingMapping, data_inicio_vigencia: e.target.value })}
                    className="bg-branco border border-linha rounded-lg px-3 py-1.5 text-xs font-semibold w-36" />
                </div>
                <div className="flex flex-col">
                  <label className="text-[9px] font-bold text-ink-45 uppercase mb-1">Fim Vig. (opc)</label>
                  <input type="date" value={editingMapping.data_fim_vigencia || ''}
                    onChange={e => setEditingMapping({ ...editingMapping, data_fim_vigencia: e.target.value || null })}
                    className="bg-branco border border-linha rounded-lg px-3 py-1.5 text-xs font-semibold w-36" />
                </div>
                <button onClick={() => {
                  const method = editingMapping.id ? 'PUT' : 'POST'
                  const url = editingMapping.id ? `${API}/dealer-marca/${editingMapping.id}` : `${API}/dealer-marca`
                  apiCall(url, {
                    method, headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(editingMapping)
                  }).then(r => r.json()).then(() => {
                    setEditingMapping(null)
                    refreshMappings()
                    showMsg('Mapping salvo com sucesso.')
                  })
                }}
                  className="bg-obsidiana text-white text-[10px] font-bold px-4 py-2 rounded-lg">
                  Salvar
                </button>
                <button onClick={() => setEditingMapping(null)}
                  className="text-[10px] font-bold text-ink-45 bg-branco border border-linha px-4 py-2 rounded-lg">Cancelar</button>
              </div>
            </div>
          )}
        </div>
      )}

      {tab === 'filtros' && (
        <div className="bg-branco rounded-xl border border-linha shadow-sm overflow-hidden">
          <div className="p-4 border-b border-linha bg-off-white">
            <h4 className="text-xs font-extrabold text-obsidiana uppercase tracking-wider">Parâmetros de Filtro por Categoria</h4>
            <p className="text-[11px] text-ink-45">Valor mínimo/máximo unitário e quantidade máxima para validação de máquinas reais (SPEC §4.4)</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-branco border-b border-linha text-ink-45 font-bold uppercase tracking-wider">
                <tr>
                  <th className="py-3 px-4 text-[10px]">Sigla</th>
                  <th className="py-3 px-4 text-[10px]">Descrição</th>
                  <th className="py-3 px-4 text-[10px] text-right">Valor Mínimo</th>
                  <th className="py-3 px-4 text-[10px] text-right">Valor Máximo</th>
                  <th className="py-3 px-4 text-[10px] text-right">Qtd. Máx</th>
                  <th className="py-3 px-4 text-[10px] text-right">Ações</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-linha-2 text-ink-70">
                {filters.map(f => (
                  <tr key={f.categoria_sigla} className="hover:bg-off-white/50">
                    <td className="py-3 px-4 font-extrabold text-obsidiana">{f.categoria_sigla}</td>
                    <td className="py-3 px-4">{f.descricao}</td>
                    <td className="py-3 px-4 text-right font-mono font-bold">
                      R$ {f.valor_minimo_unitario.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="py-3 px-4 text-right font-mono">
                      {f.valor_maximo_unitario
                        ? `R$ ${f.valor_maximo_unitario.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`
                        : '—'}
                    </td>
                    <td className="py-3 px-4 text-right font-mono font-bold">
                      {f.qtd_max ?? 10} un.
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button onClick={() => setEditingFilter(f)}
                        className="text-[10px] font-bold text-obsidiana hover:text-obsidiana bg-off-white border border-linha px-2 py-1 rounded">Editar</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {editingFilter !== null && (
            <div className="p-4 border-t border-linha bg-off-white">
              <div className="flex flex-wrap gap-3 items-end">
                <div className="flex flex-col">
                  <label className="text-[9px] font-bold text-ink-45 uppercase mb-1">Descrição</label>
                  <input value={editingFilter.descricao}
                    onChange={e => setEditingFilter({ ...editingFilter, descricao: e.target.value })}
                    className="bg-branco border border-linha rounded-lg px-3 py-1.5 text-xs font-semibold w-48" />
                </div>
                <div className="flex flex-col">
                  <label className="text-[9px] font-bold text-ink-45 uppercase mb-1">Valor Mínimo (R$)</label>
                  <input type="number" step="0.01" value={editingFilter.valor_minimo_unitario}
                    onChange={e => setEditingFilter({ ...editingFilter, valor_minimo_unitario: parseFloat(e.target.value) })}
                    className="bg-branco border border-linha rounded-lg px-3 py-1.5 text-xs font-semibold w-32" />
                </div>
                <div className="flex flex-col">
                  <label className="text-[9px] font-bold text-ink-45 uppercase mb-1">Valor Máximo (R$, opc)</label>
                  <input type="number" step="0.01" value={editingFilter.valor_maximo_unitario || ''}
                    onChange={e => setEditingFilter({
                      ...editingFilter,
                      valor_maximo_unitario: e.target.value ? parseFloat(e.target.value) : null
                    })}
                    className="bg-branco border border-linha rounded-lg px-3 py-1.5 text-xs font-semibold w-32" />
                </div>
                <div className="flex flex-col">
                  <label className="text-[9px] font-bold text-ink-45 uppercase mb-1">Qtd. Máx. (un.)</label>
                  <input type="number" step="1" min="1" value={editingFilter.qtd_max ?? 10}
                    onChange={e => setEditingFilter({
                      ...editingFilter,
                      qtd_max: e.target.value ? parseInt(e.target.value, 10) : 10
                    })}
                    className="bg-branco border border-linha rounded-lg px-3 py-1.5 text-xs font-semibold w-24" />
                </div>
                <button onClick={() => {
                  apiCall(`${API}/filtros-categoria/${editingFilter.categoria_sigla}`, {
                    method: 'PUT', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                      categoria_sigla: editingFilter.categoria_sigla,
                      descricao: editingFilter.descricao,
                      valor_minimo_unitario: editingFilter.valor_minimo_unitario,
                      valor_maximo_unitario: editingFilter.valor_maximo_unitario,
                      qtd_max: editingFilter.qtd_max ?? 10
                    })
                  }).then(r => r.json()).then(() => {
                    setEditingFilter(null)
                    apiCall(`${API}/filtros-categoria`).then(r => r.json()).then(setFilters)
                    showMsg('Filtro atualizado com sucesso.')
                  })
                }}
                  className="bg-obsidiana text-white text-[10px] font-bold px-4 py-2 rounded-lg">
                  Salvar
                </button>
                <button onClick={() => setEditingFilter(null)}
                  className="text-[10px] font-bold text-ink-45 bg-branco border border-linha px-4 py-2 rounded-lg">Cancelar</button>
              </div>
            </div>
          )}
        </div>
      )}

      {tab === 'nao-identificadas' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <div>
              <h4 className="text-xs font-extrabold text-obsidiana uppercase tracking-wider">Registros Não Identificados / Indefinidos</h4>
              <p className="text-[11px] text-ink-45">{orphans.length} registros sem marca deduzida</p>
            </div>
            <button onClick={refreshOrphans}
              className="bg-obsidiana text-white text-[10px] font-bold px-3 py-1.5 rounded-lg flex items-center gap-1">
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5"
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Atualizar
            </button>
          </div>
          <div className="bg-branco rounded-xl border border-linha shadow-sm overflow-hidden">
            <div className="overflow-x-auto" style={{ maxHeight: '400px' }}>
              <table className="w-full text-left text-xs">
                <thead className="bg-branco border-b border-linha text-ink-45 font-bold uppercase tracking-wider sticky top-0">
                  <tr>
                    <th className="py-3 px-4 text-[10px]">Município</th>
                    <th className="py-3 px-4 text-[10px]">Órgão</th>
                    <th className="py-3 px-4 text-[10px]">Fornecedor</th>
                    <th className="py-3 px-4 text-[10px]">Marca Deduzida</th>
                    <th className="py-3 px-4 text-[10px] text-right">Valor Unit.</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-linha-2 text-ink-70">
                  {orphans.length === 0 ? (
                    <tr><td colSpan={5} className="py-6 text-center text-ink-45 font-semibold">Nenhum registro pendente de identificação.</td></tr>
                  ) : orphans.map((t, i) => (
                    <tr key={i} className="hover:bg-off-white/50">
                      <td className="py-3 px-4 font-semibold text-obsidiana">{t.municipio}</td>
                      <td className="py-3 px-4 max-w-[200px] truncate">{t.orgao}</td>
                      <td className="py-3 px-4 font-mono">{t.fornecedor_normalizado}</td>
                      <td className="py-3 px-4">
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-negativo-soft text-negativo border border-negativo/30">{t.marca_deduzida}</span>
                      </td>
                      <td className="py-3 px-4 text-right font-bold">
                        R$ {t.valor_unitario.toLocaleString?.('pt-BR', { minimumFractionDigits: 2 }) || '0,00'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <div className="bg-alerta-soft border border-alerta/30 rounded-xl p-4 text-xs text-alerta">
            <span className="font-bold">Dica:</span> Para identificar estes registros, adicione regras de normalização de fornecedores e mapeamentos Dealer → Marca nas abas acima. Após criar as regras, execute uma nova coleta PNCP para reprocessar.
          </div>
        </div>
      )}

      {tab === 'coleta' && (
        <div className="space-y-4">
          <div className="bg-branco rounded-xl border border-linha shadow-sm p-5">
            <h4 className="text-xs font-extrabold text-obsidiana uppercase tracking-wider mb-2">Disparar Coleta Manual PNCP</h4>
            <p className="text-xs text-ink-45 mb-4">
              Executa o pipeline de ingestão para buscar novos processos no PNCP, normalizar fornecedores e atualizar o banco de dados.
            </p>
            <button onClick={() => {
              setColetaRunning(true)
              showMsg('Coleta em andamento...')
              apiCall(`${API}/coleta-pncp`, { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                  setColetaRunning(false)
                  showMsg(data.message || 'Coleta finalizada.')
                  apiCall(`${API}/coleta-log`).then(r => r.json()).then(d => setColetaLog(d.log || ''))
                  apiCall(`${API}/coleta-log-list`).then(r => r.json()).then(setColetaLogList)
                })
                .catch(() => { setColetaRunning(false); showMsg('Erro ao executar coleta.') })
            }}
              disabled={coletaRunning}
              className={`text-xs font-bold px-5 py-2.5 rounded-lg flex items-center gap-2 ${coletaRunning ? 'bg-linha text-ink-45 cursor-not-allowed' : 'bg-obsidiana text-branco hover:bg-ink-70 shadow-sm'}`}>
              {coletaRunning ? (
                <><svg className="animate-spin h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg> Executando...</>
              ) : '▶ Executar Coleta PNCP'}
            </button>
          </div>

          <div className="bg-branco rounded-xl border border-linha shadow-sm overflow-hidden">
            <div className="p-4 border-b border-linha bg-off-white flex justify-between items-center">
              <h4 className="text-xs font-extrabold text-obsidiana uppercase tracking-wider">Histórico de Execuções</h4>
            </div>
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

          <div className="bg-branco rounded-xl border border-linha shadow-sm overflow-hidden">
            <div className="p-4 border-b border-linha bg-off-white flex justify-between items-center">
              <h4 className="text-xs font-extrabold text-obsidiana uppercase tracking-wider">Log da Última Execução</h4>
              <button onClick={() => { apiCall(`${API}/coleta-log`).then(r => r.json()).then(d => setColetaLog(d.log || '')) }}
                className="text-[10px] font-bold text-ink-70 bg-branco border border-linha px-2 py-1 rounded">Atualizar</button>
            </div>
            <pre className="p-4 text-[11px] font-mono text-ink-70 whitespace-pre-wrap max-h-80 overflow-y-auto bg-off-white m-0">
              {coletaLog || 'Nenhuma coleta executada ainda. Clique no botão acima para iniciar.'}
            </pre>
          </div>
        </div>
      )}
    </div>
  )
}
