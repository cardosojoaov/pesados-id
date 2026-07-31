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
    <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#F8F6F1' }}>
      <div className="w-full max-w-md mx-4">
        <div className="bg-white rounded-2xl shadow-lg border border-gray-200 p-8">
          <div className="text-center mb-8">
            <div className="w-12 h-12 rounded-xl bg-[#111111] flex items-center justify-center mx-auto mb-4 shadow-md">
              <span className="text-[#F8F6F1] font-extrabold text-lg tracking-tighter">P.ID</span>
            </div>
            <h1 className="text-2xl font-extrabold tracking-tight" style={{ color: '#111111' }}>PESADOS.ID</h1>
            <p className="text-sm text-gray-500 mt-1 font-medium">Acesse sua conta</p>
          </div>

          <form onSubmit={handleLogin} className="space-y-5">
            <div>
              <label className="block text-xs font-bold text-gray-600 uppercase tracking-wider mb-1.5">
                E-mail
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="seu@email.com"
                required
                className="w-full px-4 py-2.5 rounded-lg border border-gray-200 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-[#111111] focus:border-transparent transition-all"
                style={{ color: '#111111', backgroundColor: '#F8F6F1' }}
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-gray-600 uppercase tracking-wider mb-1.5">
                Senha
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                className="w-full px-4 py-2.5 rounded-lg border border-gray-200 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-[#111111] focus:border-transparent transition-all"
                style={{ color: '#111111', backgroundColor: '#F8F6F1' }}
              />
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-xs font-semibold">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 rounded-lg font-bold text-sm transition-all disabled:opacity-50"
              style={{ backgroundColor: '#111111', color: 'white' }}
            >
              {loading ? 'Entrando...' : 'Entrar'}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-gray-400 mt-6 font-medium">
          PESADOS.ID · MVP v1.0
        </p>
      </div>
    </div>
  )
}
