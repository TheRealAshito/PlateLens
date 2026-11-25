import { useEffect, useState } from 'react'
import {
  Calculator,
  CheckCircle2,
  AlertCircle,
  KeyRound,
  Save,
  Trash2,
} from 'lucide-react'
import { api, extractErrorMessage } from '../api'
import { ACTIVITY_LEVELS, GOAL_MODES, MACRO_PRESETS } from '../constants'

function computeMacrosForCalories(kcalInput, weightKgInput, goalMode, preset) {
  const targetKcal = Math.max(1000, Number(kcalInput) || 2000)
  const weightKg = Math.max(30, Number(weightKgInput) || 75)
  let proteinG = 0
  let carbsG = 0
  let fatG = 0

  if (preset === 'zone_30_40_30') {
    proteinG = Math.round((targetKcal * 0.3) / 4)
    carbsG = Math.round((targetKcal * 0.4) / 4)
    fatG = Math.round((targetKcal * 0.3) / 9)
  } else if (preset === 'low_carb') {
    const proteinKcal = Math.min(weightKg * 1.8 * 4, targetKcal * 0.4)
    proteinG = Math.round(proteinKcal / 4)
    carbsG = Math.round((targetKcal * 0.2) / 4)
    const remainingFatKcal = Math.max(0, targetKcal - proteinG * 4 - carbsG * 4)
    fatG = Math.round(remainingFatKcal / 9)
  } else {
    const proteinPerKg =
      preset === 'high_protein' ? 2.1 : goalMode === 'maintain' ? 1.6 : 1.8
    const maxProtRatio = preset === 'high_protein' ? 0.45 : 0.4
    const fatRatio = preset === 'high_protein' ? 0.25 : 0.27

    const proteinKcal = Math.min(weightKg * proteinPerKg * 4, targetKcal * maxProtRatio)
    proteinG = Math.round(proteinKcal / 4)
    fatG = Math.round((targetKcal * fatRatio) / 9)
    const remainingKcal = Math.max(0, targetKcal - proteinG * 4 - fatG * 9)
    carbsG = Math.round(remainingKcal / 4)
  }

  const fiberG = Math.round(Math.max(20, (targetKcal / 1000) * 14))
  return {
    protein_goal_g: proteinG,
    carbs_goal_g: carbsG,
    fat_goal_g: fatG,
    fiber_goal_g: fiberG,
  }
}

export default function GoalsSettingsPage({ aiStatus, onAiStatusUpdated }) {
  const [goals, setGoals] = useState(null)
  const [tdeeResult, setTdeeResult] = useState(null)
  const [macroPreset, setMacroPreset] = useState('balanced')
  const [autoRestructure, setAutoRestructure] = useState(true)
  const [savingGoals, setSavingGoals] = useState(false)
  const [goalFeedback, setGoalFeedback] = useState(null)

  // Configurações de IA
  const [provider, setProvider] = useState(aiStatus?.vision_provider || 'gemini')
  const [newKey, setNewKey] = useState('')
  const [geminiModel, setGeminiModel] = useState(aiStatus?.gemini_model || 'gemini-3.6-flash')
  const [fallbackModel, setFallbackModel] = useState(
    aiStatus?.gemini_fallback_model || 'gemini-3.5-flash-lite'
  )
  const [ollamaUrl, setOllamaUrl] = useState(aiStatus?.ollama_base_url || '')
  const [ollamaModel, setOllamaModel] = useState(aiStatus?.ollama_model || 'qwen2.5vl:3b')
  const [testingKey, setTestingKey] = useState(false)
  const [savingAi, setSavingAi] = useState(false)
  const [aiFeedback, setAiFeedback] = useState(null)

  useEffect(() => {
    api.get('/goals').then((res) => setGoals(res.data))
  }, [])

  useEffect(() => {
    if (aiStatus) {
      setProvider(aiStatus.vision_provider)
      setGeminiModel(aiStatus.gemini_model)
      setFallbackModel(aiStatus.gemini_fallback_model)
      setOllamaUrl(aiStatus.ollama_base_url || '')
      setOllamaModel(aiStatus.ollama_model || 'qwen2.5vl:3b')
    }
  }, [aiStatus])

  async function handleCalculateTdee() {
    if (!goals) return
    setGoalFeedback(null)
    try {
      const { data } = await api.post('/goals/calculate-tdee', {
        sex: goals.sex,
        age: Number(goals.age),
        weight_kg: Number(goals.weight_kg),
        height_cm: Number(goals.height_cm),
        activity_level: goals.activity_level,
        goal_mode: goals.goal_mode,
      })
      setTdeeResult(data)
    } catch (err) {
      setGoalFeedback({ ok: false, text: extractErrorMessage(err) })
    }
  }

  function applyTdeeToGoals() {
    if (!tdeeResult || !goals) return
    const nextMacros = computeMacrosForCalories(
      tdeeResult.recommended_kcal,
      goals.weight_kg,
      goals.goal_mode,
      macroPreset
    )
    setGoals({
      ...goals,
      daily_kcal_goal: tdeeResult.recommended_kcal,
      water_goal_ml: tdeeResult.water_goal_ml || goals.water_goal_ml || 2500,
      ...nextMacros,
    })
    setGoalFeedback({
      ok: true,
      text: 'Valores da calculadora aplicados abaixo. Clique em "Salvar metas" para confirmar.',
    })
  }

  function handleCaloriesChange(rawValue) {
    if (!goals) return
    const num = Number(rawValue)
    if (autoRestructure && rawValue !== '' && num >= 1000 && num <= 8000) {
      const nextMacros = computeMacrosForCalories(
        num,
        goals.weight_kg,
        goals.goal_mode,
        macroPreset
      )
      setGoals({ ...goals, daily_kcal_goal: rawValue, ...nextMacros })
      return
    }
    setGoals({ ...goals, daily_kcal_goal: rawValue })
  }

  async function handleRestructureViaApi(nextPreset = macroPreset) {
    if (!goals) return
    const kcal = Math.max(1000, Number(goals.daily_kcal_goal) || 2000)
    try {
      const { data } = await api.post('/goals/recalculate-macros', {
        daily_kcal_goal: kcal,
        weight_kg: Math.max(30, Number(goals.weight_kg) || 75),
        goal_mode: goals.goal_mode,
        preset: nextPreset,
      })
      setGoals({
        ...goals,
        daily_kcal_goal: data.daily_kcal_goal,
        protein_goal_g: data.protein_goal_g,
        carbs_goal_g: data.carbs_goal_g,
        fat_goal_g: data.fat_goal_g,
        fiber_goal_g: data.fiber_goal_g,
      })
    } catch (err) {
      setGoalFeedback({ ok: false, text: extractErrorMessage(err) })
    }
  }

  async function handleSaveGoals(e) {
    e.preventDefault()
    setSavingGoals(true)
    setGoalFeedback(null)
    try {
      const { data } = await api.put('/goals', {
        sex: goals.sex,
        age: Number(goals.age),
        weight_kg: Number(goals.weight_kg),
        height_cm: Number(goals.height_cm),
        activity_level: goals.activity_level,
        goal_mode: goals.goal_mode,
        daily_kcal_goal: Number(goals.daily_kcal_goal),
        protein_goal_g: Number(goals.protein_goal_g),
        carbs_goal_g: Number(goals.carbs_goal_g),
        fat_goal_g: Number(goals.fat_goal_g),
        fiber_goal_g: Number(goals.fiber_goal_g),
        water_goal_ml: Number(goals.water_goal_ml || 2500),
      })
      setGoals(data)
      setGoalFeedback({ ok: true, text: 'Metas diárias salvas com sucesso!' })
    } catch (err) {
      setGoalFeedback({ ok: false, text: extractErrorMessage(err) })
    } finally {
      setSavingGoals(false)
    }
  }

  async function handleTestAiKey() {
    setTestingKey(true)
    setAiFeedback(null)
    try {
      const { data } = await api.post('/settings/ai/test', { gemini_api_key: newKey.trim() })
      setAiFeedback({ ok: data.ok, text: data.message })
    } catch (err) {
      setAiFeedback({ ok: false, text: extractErrorMessage(err) })
    } finally {
      setTestingKey(false)
    }
  }

  async function handleSaveAiSettings(e) {
    e.preventDefault()
    setSavingAi(true)
    setAiFeedback(null)
    try {
      const payload = {
        vision_provider: provider,
        gemini_model: geminiModel,
        gemini_fallback_model: fallbackModel,
        ollama_base_url: ollamaUrl,
        ollama_model: ollamaModel,
        onboarding_dismissed: true,
      }
      if (newKey.trim()) {
        payload.gemini_api_key = newKey.trim()
      }
      const { data } = await api.put('/settings/ai', payload)
      setNewKey('')
      onAiStatusUpdated(data)
      setAiFeedback({ ok: true, text: 'Configurações de IA atualizadas!' })
    } catch (err) {
      setAiFeedback({ ok: false, text: extractErrorMessage(err) })
    } finally {
      setSavingAi(false)
    }
  }

  async function handleClearKey() {
    setSavingAi(true)
    setAiFeedback(null)
    try {
      const { data } = await api.put('/settings/ai', { clear_gemini_api_key: true })
      onAiStatusUpdated(data)
      setAiFeedback({ ok: true, text: 'Chave salva na interface removida.' })
    } catch (err) {
      setAiFeedback({ ok: false, text: extractErrorMessage(err) })
    } finally {
      setSavingAi(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Calculadora TMB / TDEE + Metas */}
      {goals && (
        <form
          onSubmit={handleSaveGoals}
          className="rounded-2xl border border-slate-800 bg-slate-900/90 p-5 space-y-4"
        >
          <div className="flex items-center gap-2.5">
            <Calculator className="h-5 w-5 text-emerald-400" />
            <div>
              <h2 className="text-base font-semibold text-white">
                Calculadora de Meta Calórica (TMB / TDEE)
              </h2>
              <p className="text-xs text-slate-400">
                Estimativa educativa baseada na fórmula Mifflin-St Jeor. Não substitui nutricionista.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div>
              <label className="mb-1 block text-xs text-slate-400">Sexo biológico</label>
              <select
                value={goals.sex}
                onChange={(e) => setGoals({ ...goals, sex: e.target.value })}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"
              >
                <option value="M">Masculino</option>
                <option value="F">Feminino</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">Idade (anos)</label>
              <input
                type="number"
                min="14"
                max="110"
                value={goals.age}
                onChange={(e) => setGoals({ ...goals, age: e.target.value })}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">Peso (kg)</label>
              <input
                type="number"
                step="0.1"
                value={goals.weight_kg}
                onChange={(e) => setGoals({ ...goals, weight_kg: e.target.value })}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">Altura (cm)</label>
              <input
                type="number"
                value={goals.height_cm}
                onChange={(e) => setGoals({ ...goals, height_cm: e.target.value })}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"
              />
            </div>
            <div className="col-span-2">
              <label className="mb-1 block text-xs text-slate-400">Nível de atividade</label>
              <select
                value={goals.activity_level}
                onChange={(e) => setGoals({ ...goals, activity_level: e.target.value })}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"
              >
                {ACTIVITY_LEVELS.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="col-span-2">
              <label className="mb-1 block text-xs text-slate-400">Objetivo</label>
              <select
                value={goals.goal_mode}
                onChange={(e) => setGoals({ ...goals, goal_mode: e.target.value })}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"
              >
                {GOAL_MODES.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={handleCalculateTdee}
              className="rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-2 text-xs font-semibold text-emerald-300 hover:bg-emerald-500/20"
            >
              Calcular TMB e TDEE
            </button>

            {tdeeResult && (
              <div className="flex flex-wrap items-center gap-3 rounded-xl bg-slate-950 px-3.5 py-2 text-xs">
                <span>
                  TMB: <strong className="text-white">{tdeeResult.bmr_kcal} kcal</strong>
                </span>
                <span>
                  TDEE: <strong className="text-white">{tdeeResult.tdee_kcal} kcal</strong>
                </span>
                <span>
                  Sugestão: <strong className="text-emerald-400">{tdeeResult.recommended_kcal} kcal/dia</strong>
                </span>
                <button
                  type="button"
                  onClick={applyTdeeToGoals}
                  className="rounded-lg bg-emerald-500 px-2.5 py-1 text-[11px] font-semibold text-slate-950"
                >
                  Aplicar às metas
                </button>
              </div>
            )}
          </div>

          <hr className="border-slate-800" />

          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-white">Metas diárias ativas</h3>
            <label className="inline-flex cursor-pointer items-center gap-2 text-xs text-slate-300">
              <input
                type="checkbox"
                checked={autoRestructure}
                onChange={(e) => setAutoRestructure(e.target.checked)}
                className="rounded border-slate-700 bg-slate-950 text-emerald-500"
              />
              Reestruturar macros automaticamente ao alterar calorias
            </label>
          </div>

          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-[220px] flex-1">
              <label className="mb-1 block text-xs text-slate-400">
                Estratégia de distribuição dos macros
              </label>
              <select
                value={macroPreset}
                onChange={(e) => {
                  const next = e.target.value
                  setMacroPreset(next)
                  if (autoRestructure) {
                    handleRestructureViaApi(next)
                  }
                }}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"
              >
                {MACRO_PRESETS.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>
            <button
              type="button"
              onClick={() => handleRestructureViaApi(macroPreset)}
              className="rounded-xl border border-slate-700 bg-slate-800 px-3.5 py-2 text-xs font-medium text-slate-200 hover:bg-slate-700"
            >
              Recalcular macros pelas calorias
            </button>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-6">
            <div>
              <label className="mb-1 block text-xs text-slate-400">Calorias (kcal)</label>
              <input
                type="number"
                min="1000"
                max="8000"
                value={goals.daily_kcal_goal}
                onChange={(e) => handleCaloriesChange(e.target.value)}
                className="w-full rounded-xl border border-emerald-500/40 bg-slate-950 px-3 py-2 text-xs font-semibold text-white"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">Proteína (g)</label>
              <input
                type="number"
                value={goals.protein_goal_g}
                onChange={(e) => setGoals({ ...goals, protein_goal_g: e.target.value })}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">Carboidratos (g)</label>
              <input
                type="number"
                value={goals.carbs_goal_g}
                onChange={(e) => setGoals({ ...goals, carbs_goal_g: e.target.value })}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">Gorduras (g)</label>
              <input
                type="number"
                value={goals.fat_goal_g}
                onChange={(e) => setGoals({ ...goals, fat_goal_g: e.target.value })}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">Fibras (g)</label>
              <input
                type="number"
                value={goals.fiber_goal_g}
                onChange={(e) => setGoals({ ...goals, fiber_goal_g: e.target.value })}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">Água (ml)</label>
              <input
                type="number"
                min="500"
                max="10000"
                step="100"
                value={goals.water_goal_ml ?? 2500}
                onChange={(e) => setGoals({ ...goals, water_goal_ml: e.target.value })}
                className="w-full rounded-xl border border-cyan-500/40 bg-slate-950 px-3 py-2 text-xs text-white"
              />
            </div>
          </div>

          {(() => {
            const pKcal = (Number(goals.protein_goal_g) || 0) * 4
            const cKcal = (Number(goals.carbs_goal_g) || 0) * 4
            const fKcal = (Number(goals.fat_goal_g) || 0) * 9
            const sumKcal = Math.max(1, pKcal + cKcal + fKcal)
            return (
              <div className="rounded-xl bg-slate-950/80 px-3.5 py-2 text-[11px] text-slate-400 flex flex-wrap gap-3">
                <span>
                  Soma dos macros: <strong className="text-slate-200">{Math.round(pKcal + cKcal + fKcal)} kcal</strong>
                </span>
                <span className="text-sky-300">P: {Math.round((pKcal / sumKcal) * 100)}%</span>
                <span className="text-violet-300">C: {Math.round((cKcal / sumKcal) * 100)}%</span>
                <span className="text-amber-300">G: {Math.round((fKcal / sumKcal) * 100)}%</span>
              </div>
            )
          })()}

          {goalFeedback && (
            <div
              className={`flex items-center gap-2 rounded-xl px-3.5 py-2 text-xs ${
                goalFeedback.ok
                  ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                  : 'bg-rose-500/15 text-rose-300 border border-rose-500/30'
              }`}
            >
              {goalFeedback.ok ? <CheckCircle2 className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
              <span>{goalFeedback.text}</span>
            </div>
          )}

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={savingGoals}
              className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-500 px-4 py-2 text-xs font-semibold text-slate-950 hover:bg-emerald-400 disabled:opacity-50"
            >
              <Save className="h-4 w-4" />
              {savingGoals ? 'Salvando...' : 'Salvar metas'}
            </button>
          </div>
        </form>
      )}

      {/* Provedor de IA */}
      <form
        onSubmit={handleSaveAiSettings}
        className="rounded-2xl border border-slate-800 bg-slate-900/90 p-5 space-y-4"
      >
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2.5">
            <KeyRound className="h-5 w-5 text-emerald-400" />
            <div>
              <h2 className="text-base font-semibold text-white">Provedor de Visão (Fotos)</h2>
              <p className="text-xs text-slate-400">
                Status atual:{' '}
                {aiStatus?.ai_configured ? (
                  <span className="text-emerald-300 font-medium">
                    Configurado ({aiStatus.vision_provider} · {aiStatus.masked_key || 'LAN'})
                  </span>
                ) : (
                  <span className="text-amber-300 font-medium">Não configurado</span>
                )}
              </p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div>
            <label className="mb-1 block text-xs text-slate-400">Provedor</label>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"
            >
              <option value="gemini">Google AI Studio (Gemini)</option>
              <option value="ollama">Ollama (Rede Local / LAN)</option>
              <option value="disabled">Desativado (Somente TACO manual)</option>
            </select>
          </div>

          {provider === 'gemini' && (
            <>
              <div>
                <label className="mb-1 block text-xs text-slate-400">Modelo principal</label>
                <select
                  value={geminiModel}
                  onChange={(e) => setGeminiModel(e.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"
                >
                  <option value="gemini-3.6-flash">gemini-3.6-flash (20 RPD)</option>
                  <option value="gemini-3.5-flash-lite">gemini-3.5-flash-lite (500 RPD)</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs text-slate-400">Fallback automático (429)</label>
                <select
                  value={fallbackModel}
                  onChange={(e) => setFallbackModel(e.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"
                >
                  <option value="gemini-3.5-flash-lite">gemini-3.5-flash-lite</option>
                  <option value="gemini-3.6-flash">gemini-3.6-flash</option>
                </select>
              </div>
            </>
          )}
        </div>

        {provider === 'gemini' && (
          <div className="space-y-2">
            <label className="block text-xs text-slate-400">
              Nova chave da Gemini API {aiStatus?.masked_key ? `(atual: ${aiStatus.masked_key})` : ''}
            </label>
            <div className="flex flex-wrap gap-2">
              <input
                type="password"
                value={newKey}
                onChange={(e) => setNewKey(e.target.value)}
                placeholder="Cole AIza... para definir ou substituir a chave"
                className="min-w-[220px] flex-1 rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2 text-xs text-white"
              />
              <button
                type="button"
                onClick={handleTestAiKey}
                disabled={testingKey}
                className="rounded-xl border border-slate-700 bg-slate-800 px-3.5 py-2 text-xs text-slate-200 hover:bg-slate-700"
              >
                {testingKey ? 'Testando...' : 'Testar chave'}
              </button>
              {aiStatus?.key_source === 'database' && (
                <button
                  type="button"
                  onClick={handleClearKey}
                  className="inline-flex items-center gap-1 rounded-xl border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-300 hover:bg-rose-500/20"
                >
                  <Trash2 className="h-3.5 w-3.5" /> Remover chave
                </button>
              )}
            </div>
          </div>
        )}

        {provider === 'ollama' && (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs text-slate-400">URL do Ollama na LAN</label>
              <input
                type="text"
                value={ollamaUrl}
                onChange={(e) => setOllamaUrl(e.target.value)}
                placeholder="http://192.168.1.50:11434"
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">Modelo multimodal</label>
              <input
                type="text"
                value={ollamaModel}
                onChange={(e) => setOllamaModel(e.target.value)}
                placeholder="qwen2.5vl:3b"
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"
              />
            </div>
          </div>
        )}

        {aiFeedback && (
          <div
            className={`flex items-center gap-2 rounded-xl px-3.5 py-2 text-xs ${
              aiFeedback.ok
                ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                : 'bg-rose-500/15 text-rose-300 border border-rose-500/30'
            }`}
          >
            {aiFeedback.ok ? <CheckCircle2 className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
            <span>{aiFeedback.text}</span>
          </div>
        )}

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={savingAi}
            className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-500 px-4 py-2 text-xs font-semibold text-slate-950 hover:bg-emerald-400 disabled:opacity-50"
          >
            <Save className="h-4 w-4" />
            {savingAi ? 'Salvando...' : 'Salvar configurações de IA'}
          </button>
        </div>
      </form>
    </div>
  )
}
