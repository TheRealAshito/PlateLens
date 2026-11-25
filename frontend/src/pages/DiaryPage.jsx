import { useEffect, useState } from 'react'
import {
  ChevronLeft,
  ChevronRight,
  Copy,
  Droplets,
  Flame,
  Plus,
  Star,
  Trash2,
  Utensils,
  X,
} from 'lucide-react'
import { api, extractErrorMessage } from '../api'
import {
  MEAL_TYPES,
  MEAL_TYPE_LABELS,
  currentTimeHHMM,
  formatDateBR,
  shiftIsoDate,
  todayIsoDate,
} from '../constants'

function MacroBar({ label, current, goal, unit = 'g', colorClass }) {
  const pct = goal > 0 ? Math.min(100, Math.round((current / goal) * 100)) : 0
  const over = goal > 0 && current > goal
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="font-medium text-slate-300">{label}</span>
        <span className={over ? 'text-amber-300 font-semibold' : 'text-slate-400'}>
          {Math.round(current)}{unit} / {Math.round(goal)}{unit}
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-800">
        <div
          className={`h-full rounded-full transition-all ${over ? 'bg-amber-400' : colorClass}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

export default function DiaryPage({ selectedDate, onChangeDate, onGoToLog }) {
  const [data, setData] = useState(null)
  const [water, setWater] = useState({ total_ml: 0, goal_ml: 2500, entries: [] })
  const [customWaterMl, setCustomWaterMl] = useState('')
  const [waterBusy, setWaterBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(null)

  async function loadDay(dateStr) {
    setLoading(true)
    setError('')
    try {
      const [mealsRes, waterRes] = await Promise.all([
        api.get('/meals', { params: { date: dateStr } }),
        api.get('/water', { params: { date: dateStr } }),
      ])
      setData(mealsRes.data)
      setWater(waterRes.data)
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  async function handleAddWater(amountMl) {
    const ml = Math.round(Number(amountMl))
    if (!ml || ml <= 0 || ml > 5000) return
    setWaterBusy(true)
    setError('')
    try {
      await api.post('/water', {
        log_date: selectedDate,
        log_time: currentTimeHHMM(),
        amount_ml: ml,
      })
      setCustomWaterMl('')
      const { data: waterData } = await api.get('/water', { params: { date: selectedDate } })
      setWater(waterData)
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setWaterBusy(false)
    }
  }

  async function handleDeleteWater(entryId) {
    setWaterBusy(true)
    try {
      await api.delete(`/water/${entryId}`)
      const { data: waterData } = await api.get('/water', { params: { date: selectedDate } })
      setWater(waterData)
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setWaterBusy(false)
    }
  }

  useEffect(() => {
    loadDay(selectedDate)
  }, [selectedDate])

  async function handleToggleFavorite(meal) {
    setBusyId(meal.id)
    try {
      await api.patch(`/meals/${meal.id}`, { is_favorite: !meal.is_favorite })
      await loadDay(selectedDate)
    } finally {
      setBusyId(null)
    }
  }

  async function handleRepeatToday(meal) {
    setBusyId(meal.id)
    try {
      await api.post(`/meals/${meal.id}/repeat`, null, {
        params: { eaten_date: todayIsoDate(), meal_type: meal.meal_type },
      })
      if (selectedDate === todayIsoDate()) {
        await loadDay(selectedDate)
      } else {
        onChangeDate(todayIsoDate())
      }
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setBusyId(null)
    }
  }

  async function handleDelete(meal) {
    setBusyId(meal.id)
    try {
      await api.delete(`/meals/${meal.id}`)
      await loadDay(selectedDate)
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setBusyId(null)
    }
  }

  const goals = data?.goals
  const totals = data?.day_totals || {
    kcal: 0,
    kcal_min: 0,
    kcal_max: 0,
    protein_g: 0,
    carbs_g: 0,
    fat_g: 0,
    fiber_g: 0,
  }
  const kcalGoal = goals?.daily_kcal_goal || 2000
  const remainingKcal = Math.round(kcalGoal - totals.kcal)
  const kcalPct = Math.min(100, Math.round((totals.kcal / kcalGoal) * 100))

  const grouped = MEAL_TYPES.map((mt) => ({
    ...mt,
    meals: (data?.meals || []).filter((m) => m.meal_type === mt.id),
  }))

  return (
    <div className="space-y-5">
      {/* Navegação de Data */}
      <div className="flex items-center justify-between rounded-2xl border border-slate-800 bg-slate-900/90 px-3 py-2.5">
        <button
          type="button"
          onClick={() => onChangeDate(shiftIsoDate(selectedDate, -1))}
          className="rounded-xl p-2 text-slate-300 hover:bg-slate-800 hover:text-white"
          aria-label="Dia anterior"
        >
          <ChevronLeft className="h-5 w-5" />
        </button>
        <div className="text-center">
          <div className="text-sm font-semibold text-white">
            {selectedDate === todayIsoDate() ? 'Hoje' : formatDateBR(selectedDate)}
          </div>
          <div className="text-[11px] text-slate-400">{formatDateBR(selectedDate)}</div>
        </div>
        <button
          type="button"
          onClick={() => onChangeDate(shiftIsoDate(selectedDate, 1))}
          className="rounded-xl p-2 text-slate-300 hover:bg-slate-800 hover:text-white"
          aria-label="Próximo dia"
        >
          <ChevronRight className="h-5 w-5" />
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-xs text-rose-300">
          {error}
        </div>
      )}

      {/* Resumo Calórico e Macros */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-5 space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-500/15 text-emerald-400">
              <Flame className="h-6 w-6" />
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-400">Calorias do dia</p>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-bold text-white">{Math.round(totals.kcal)}</span>
                <span className="text-sm text-slate-400">/ {Math.round(kcalGoal)} kcal</span>
              </div>
              {totals.kcal > 0 && (
                <p className="text-[11px] text-slate-400">
                  Faixa estimada: {Math.round(totals.kcal_min)}–{Math.round(totals.kcal_max)} kcal
                </p>
              )}
            </div>
          </div>

          <div className="text-right">
            <span
              className={`inline-block rounded-xl px-3 py-1.5 text-xs font-semibold ${
                remainingKcal >= 0
                  ? 'bg-emerald-500/15 text-emerald-300'
                  : 'bg-amber-500/15 text-amber-300'
              }`}
            >
              {remainingKcal >= 0
                ? `Restam ${remainingKcal} kcal`
                : `Acima em ${Math.abs(remainingKcal)} kcal`}
            </span>
          </div>
        </div>

        <div className="h-3 w-full overflow-hidden rounded-full bg-slate-800">
          <div
            className={`h-full rounded-full transition-all ${
              remainingKcal < 0 ? 'bg-amber-400' : 'bg-emerald-500'
            }`}
            style={{ width: `${kcalPct}%` }}
          />
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <MacroBar
            label="Proteínas"
            current={totals.protein_g}
            goal={goals?.protein_goal_g || 140}
            colorClass="bg-sky-400"
          />
          <MacroBar
            label="Carboidratos"
            current={totals.carbs_g}
            goal={goals?.carbs_goal_g || 215}
            colorClass="bg-violet-400"
          />
          <MacroBar
            label="Gorduras"
            current={totals.fat_g}
            goal={goals?.fat_goal_g || 62}
            colorClass="bg-amber-400"
          />
          <MacroBar
            label="Fibras"
            current={totals.fiber_g}
            goal={goals?.fiber_goal_g || 28}
            colorClass="bg-emerald-400"
          />
        </div>
      </div>

      {/* Tracker de Água (Hidratação) */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-5 space-y-3.5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-500/15 text-cyan-400">
              <Droplets className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-400">Hidratação do dia</p>
              <div className="flex items-baseline gap-2">
                <span className="text-xl font-bold text-white">{water.total_ml} ml</span>
                <span className="text-xs text-slate-400">/ {water.goal_ml} ml</span>
              </div>
            </div>
          </div>

          <span className="rounded-xl bg-cyan-500/15 px-3 py-1 text-xs font-semibold text-cyan-300">
            {water.goal_ml > 0 ? Math.min(100, Math.round((water.total_ml / water.goal_ml) * 100)) : 0}% da meta
          </span>
        </div>

        <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-800">
          <div
            className="h-full rounded-full bg-cyan-400 transition-all"
            style={{
              width: `${water.goal_ml > 0 ? Math.min(100, Math.round((water.total_ml / water.goal_ml) * 100)) : 0}%`,
            }}
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {[200, 300, 500].map((ml) => (
            <button
              key={ml}
              type="button"
              disabled={waterBusy}
              onClick={() => handleAddWater(ml)}
              className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-3 py-1.5 text-xs font-semibold text-cyan-200 hover:bg-cyan-500/20 disabled:opacity-50"
            >
              +{ml} ml
            </button>
          ))}
          <div className="flex items-center gap-1.5 ml-auto">
            <input
              type="number"
              min="50"
              max="5000"
              step="50"
              value={customWaterMl}
              onChange={(e) => setCustomWaterMl(e.target.value)}
              placeholder="Outro (ml)"
              className="w-24 rounded-xl border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs text-white placeholder-slate-500"
            />
            <button
              type="button"
              disabled={waterBusy || !customWaterMl}
              onClick={() => handleAddWater(customWaterMl)}
              className="rounded-xl bg-cyan-500 px-3 py-1.5 text-xs font-semibold text-slate-950 hover:bg-cyan-400 disabled:opacity-40"
            >
              Add
            </button>
          </div>
        </div>

        {water.entries.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {water.entries.map((w) => (
              <span
                key={w.id}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-950 px-2.5 py-1 text-[11px] text-slate-300"
              >
                <span className="text-slate-500">{w.log_time}</span>
                <strong className="text-cyan-300">{w.amount_ml} ml</strong>
                <button
                  type="button"
                  disabled={waterBusy}
                  onClick={() => handleDeleteWater(w.id)}
                  className="text-slate-500 hover:text-rose-400"
                  aria-label="Remover registro de água"
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Lista de Refeições */}
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          Refeições registradas
        </h2>
        <button
          type="button"
          onClick={() => onGoToLog()}
          className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-500 px-3.5 py-2 text-xs font-semibold text-slate-950 hover:bg-emerald-400"
        >
          <Plus className="h-4 w-4" /> Nova refeição
        </button>
      </div>

      {loading ? (
        <div className="rounded-2xl border border-slate-800 bg-slate-900 p-8 text-center text-sm text-slate-400">
          Carregando diário...
        </div>
      ) : (data?.meals || []).length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-800 bg-slate-900/50 p-8 text-center space-y-3">
          <Utensils className="mx-auto h-9 w-9 text-slate-600" />
          <p className="text-sm text-slate-300">Nenhuma refeição registrada neste dia.</p>
          <button
            type="button"
            onClick={() => onGoToLog()}
            className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-500/15 px-4 py-2 text-xs font-semibold text-emerald-300 hover:bg-emerald-500/25"
          >
            <Plus className="h-4 w-4" /> Fotografar prato ou buscar na TACO
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {grouped
            .filter((g) => g.meals.length > 0)
            .map((group) => (
              <div key={group.id} className="space-y-2">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 px-1">
                  {MEAL_TYPE_LABELS[group.id]}
                </h3>
                {group.meals.map((meal) => (
                  <div
                    key={meal.id}
                    className="rounded-2xl border border-slate-800 bg-slate-900/90 p-4 space-y-3"
                  >
                    <div className="flex items-start gap-3">
                      {meal.photo_url ? (
                        <img
                          src={meal.photo_url}
                          alt={meal.title}
                          className="h-16 w-16 shrink-0 rounded-xl object-cover border border-slate-700"
                        />
                      ) : (
                        <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-xl bg-slate-800 text-slate-500">
                          <Utensils className="h-6 w-6" />
                        </div>
                      )}

                      <div className="min-w-0 flex-1">
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <h4 className="truncate text-sm font-semibold text-white">{meal.title}</h4>
                            <p className="text-xs text-slate-400">
                              {meal.eaten_time} ·{' '}
                              {meal.ai_provider_used !== 'manual'
                                ? `IA (${meal.ai_model_used || meal.ai_provider_used})`
                                : 'Manual (TACO)'}
                            </p>
                          </div>
                          <div className="text-right shrink-0">
                            <p className="text-base font-bold text-emerald-400">
                              {Math.round(meal.total_kcal)} kcal
                            </p>
                            <p className="text-[11px] text-slate-500">
                              {Math.round(meal.total_kcal_min)}–{Math.round(meal.total_kcal_max)}
                            </p>
                          </div>
                        </div>

                        <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-slate-300">
                          <span className="rounded-md bg-sky-500/10 px-2 py-0.5 text-sky-300">
                            P: {meal.total_protein_g}g
                          </span>
                          <span className="rounded-md bg-violet-500/10 px-2 py-0.5 text-violet-300">
                            C: {meal.total_carbs_g}g
                          </span>
                          <span className="rounded-md bg-amber-500/10 px-2 py-0.5 text-amber-300">
                            G: {meal.total_fat_g}g
                          </span>
                          <span className="rounded-md bg-emerald-500/10 px-2 py-0.5 text-emerald-300">
                            F: {meal.total_fiber_g}g
                          </span>
                        </div>
                      </div>
                    </div>

                    <ul className="divide-y divide-slate-800/70 rounded-xl bg-slate-950/50 px-3 text-xs">
                      {meal.items.map((item) => (
                        <li key={item.id} className="flex items-center justify-between py-1.5 gap-2">
                          <span className="text-slate-300 truncate">
                            {item.label}{' '}
                            <span className="text-slate-500">({Math.round(item.grams)}g)</span>
                          </span>
                          <span className="shrink-0 font-medium text-slate-200">
                            {Math.round(item.kcal)} kcal
                          </span>
                        </li>
                      ))}
                    </ul>

                    {meal.notes && (
                      <p className="text-xs italic text-slate-400">Obs.: {meal.notes}</p>
                    )}

                    <div className="flex items-center justify-end gap-2 pt-1">
                      <button
                        type="button"
                        disabled={busyId === meal.id}
                        onClick={() => handleToggleFavorite(meal)}
                        className={`inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs transition ${
                          meal.is_favorite
                            ? 'bg-amber-500/15 text-amber-300'
                            : 'text-slate-400 hover:bg-slate-800 hover:text-white'
                        }`}
                      >
                        <Star className={`h-3.5 w-3.5 ${meal.is_favorite ? 'fill-amber-300' : ''}`} />
                        Favorita
                      </button>
                      <button
                        type="button"
                        disabled={busyId === meal.id}
                        onClick={() => handleRepeatToday(meal)}
                        className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs text-slate-300 hover:bg-slate-800 hover:text-white"
                      >
                        <Copy className="h-3.5 w-3.5" /> Repetir hoje
                      </button>
                      <button
                        type="button"
                        disabled={busyId === meal.id}
                        onClick={() => handleDelete(meal)}
                        className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs text-rose-400 hover:bg-rose-500/15"
                      >
                        <Trash2 className="h-3.5 w-3.5" /> Excluir
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ))}
        </div>
      )}
    </div>
  )
}
