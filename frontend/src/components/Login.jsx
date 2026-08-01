import { useState } from 'react'
import { supabase } from '../lib/supabase'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  const handleLogin = async (e) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    setLoading(false)
    if (error) {
      setError(
        error.message === 'Invalid login credentials'
          ? 'E-mail ou senha incorretos.'
          : error.message
      )
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--color-off-white)' }}>
      <div className="w-full max-w-md mx-4">
        <div className="bg-branco rounded-2xl shadow-lg border border-linha p-8">
          <div className="text-center mb-8">
            <div className="w-12 h-12 rounded-xl bg-obsidiana flex items-center justify-center mx-auto mb-4 shadow-md">
              <span className="text-off-white font-extrabold text-lg tracking-tighter">P.ID</span>
            </div>
            <h1 className="text-2xl font-extrabold tracking-tight" style={{ color: 'var(--color-obsidiana)' }}>PESADOS.ID</h1>
            <p className="text-sm text-ink-45 mt-1 font-medium">Acesse sua conta</p>
          </div>

          <form onSubmit={handleLogin} className="space-y-5">
            <div>
              <label className="block text-xs font-bold text-ink-70 uppercase tracking-wider mb-1.5">
                E-mail
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="seu@email.com"
                required
                className="w-full px-4 py-2.5 rounded-lg border border-linha text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-obsidiana focus:border-transparent transition-all"
                style={{ color: 'var(--color-obsidiana)', backgroundColor: 'var(--color-off-white)' }}
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-ink-70 uppercase tracking-wider mb-1.5">
                Senha
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                className="w-full px-4 py-2.5 rounded-lg border border-linha text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-obsidiana focus:border-transparent transition-all"
                style={{ color: 'var(--color-obsidiana)', backgroundColor: 'var(--color-off-white)' }}
              />
            </div>

            {error && (
              <div className="bg-negativo-soft border border-negativo/30 text-negativo px-4 py-3 rounded-lg text-xs font-semibold">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 rounded-lg font-bold text-sm transition-all disabled:opacity-50"
              style={{ backgroundColor: 'var(--color-obsidiana)', color: 'white' }}
            >
              {loading ? 'Entrando...' : 'Entrar'}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-ink-45 mt-6 font-medium">
          PESADOS.ID · MVP v1.0
        </p>
      </div>
    </div>
  )
}
