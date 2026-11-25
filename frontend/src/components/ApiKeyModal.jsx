import { useState } from 'react'
import { KeyRound, CheckCircle2, AlertCircle, Sparkles, X } from 'lucide-react'
import { api, extractErrorMessage } from '../api'

export default function ApiKeyModal({ aiStatus, onSaved, onDismiss }) {
  const [apiKey, setApiKey] = useState('')
  const [primaryModel, setPrimaryModel] = useState(aiStatus?.gemini_model || 'gemini-3.6-flash')
  const [testing, setTesting] = useState(false)
  const [saving, setSaving] = useState(false)
  const [feedback, setFeedback] = useState(null)

  async function handleTest() {
    if (!apiKey.trim()) {
      setFeedback({ ok: false, text: 'Cole sua chave do Google AI Studio antes de testar.' })
      return
    }
    setTesting(true)
    setFeedback(null)
    try {
      const { data } = await api.post('/settings/ai/test', { gemini_api_key: apiKey.trim() })
      setFeedback({ ok: data.ok, text: data.message })
    } catch (err) {
      setFeedback({ ok: false, text: extractErrorMessage(err) })
    } finally {
      setTesting(false)
    }
  }

  async function handleSave(e) {
    e.preventDefault()
    if (!apiKey.trim()) {
      setFeedback({ ok: false, text: 'Informe sua API key ou escolha continuar no modo manual.' })
      return
    }
    setSaving(true)
    setFeedback(null)
    try {
      const { data } = await api.put('/settings/ai', {
        vision_provider: 'gemini',
        gemini_api_key: apiKey.trim(),
        gemini_model: primaryModel,
        gemini_fallback_model: 'gemini-3.5-flash-lite',
        onboarding_dismissed: true,
      })
      onSaved(data)
    } catch (err) {
      setFeedback({ ok: false, text: extractErrorMessage(err) })
    } finally {
      setSaving(false)
    }
  }

  async function handleSkip() {
    try {
      const { data } = await api.put('/settings/ai', { onboarding_dismissed: true })
      onDismiss(data)
    } catch {
      onDismiss()
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/85 p-4 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-500/15 text-emerald-400">
              <KeyRound className="h-6 w-6" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Configurar API de Visão (Início Rápido)</h2>
              <p className="text-xs text-slate-400">
                Nenhuma chave vem embarcada no app. Seus dados ficam 100% no seu homelab.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleSkip}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white"
            aria-label="Fechar"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSave} className="space-y-4">
          <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3 text-xs text-slate-300 space-y-1">
            <p className="font-medium text-emerald-300 flex items-center gap-1.5">
              <Sparkles className="h-4 w-4" /> Como pegar sua chave grátis no Google AI Studio:
            </p>
            <p>
              Acesse <span className="font-mono text-slate-200">aistudio.google.com</span> →{' '}
              <strong>Get API key</strong> → <strong>Create API key</strong> (Free Tier, sem precisar pagar pré-pago).
            </p>
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-200">
              Chave da Gemini API
            </label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="AIza..."
              className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2.5 text-sm text-white placeholder-slate-500 focus:border-emerald-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-200">
              Modelo padrão (com fallback automático para 3.5 Flash-Lite)
            </label>
            <select
              value={primaryModel}
              onChange={(e) => setPrimaryModel(e.target.value)}
              className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2.5 text-sm text-white focus:border-emerald-500 focus:outline-none"
            >
              <option value="gemini-3.6-flash">Gemini 3.6 Flash — Preciso (20 req/dia grátis + fallback)</option>
              <option value="gemini-3.5-flash-lite">Gemini 3.5 Flash-Lite — Econômico (500 req/dia grátis)</option>
            </select>
          </div>

          {feedback && (
            <div
              className={`flex items-center gap-2 rounded-xl px-3.5 py-2.5 text-xs ${
                feedback.ok
                  ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                  : 'bg-rose-500/15 text-rose-300 border border-rose-500/30'
              }`}
            >
              {feedback.ok ? <CheckCircle2 className="h-4 w-4 shrink-0" /> : <AlertCircle className="h-4 w-4 shrink-0" />}
              <span>{feedback.text}</span>
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between gap-2 pt-2">
            <button
              type="button"
              onClick={handleSkip}
              className="rounded-xl px-3.5 py-2 text-xs font-medium text-slate-400 hover:bg-slate-800 hover:text-slate-200"
            >
              Usar só Tabela TACO manual por enquanto
            </button>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleTest}
                disabled={testing}
                className="rounded-xl border border-slate-700 bg-slate-800 px-3.5 py-2 text-xs font-medium text-slate-200 hover:bg-slate-700 disabled:opacity-50"
              >
                {testing ? 'Testando...' : 'Testar chave'}
              </button>
              <button
                type="submit"
                disabled={saving}
                className="rounded-xl bg-emerald-500 px-4 py-2 text-xs font-semibold text-slate-950 hover:bg-emerald-400 disabled:opacity-50"
              >
                {saving ? 'Salvando...' : 'Salvar e começar'}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  )
}
