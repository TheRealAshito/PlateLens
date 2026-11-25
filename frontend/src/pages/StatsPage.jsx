import { useEffect, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { BarChart3 } from 'lucide-react'
import { api, extractErrorMessage } from '../api'

export default function StatsPage() {
  const [days, setDays] = useState(7)
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true)
    setError('')
    api
      .get('/stats/summary', { params: { days } })
      .then((res) => setStats(res.data))
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false))
  }, [days])

  const avg = stats?.averages

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <BarChart3 className="h-5 w-5 text-emerald-400" />
          <h2 className="text-base font-semibold text-white">Evolução Nutricional</h2>
        </div>

        <div className="flex rounded-xl border border-slate-800 bg-slate-900 p-1">
          {[7, 30].map((d) => (
            <button
              key={d}
              type="button"
              onClick={() => setDays(d)}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                days === d ? 'bg-emerald-500 text-slate-950' : 'text-slate-300 hover:text-white'
              }`}
            >
              {d} dias
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-xs text-rose-300">
          {error}
        </div>
      )}

      {loading ? (
        <div className="rounded-2xl border border-slate-800 bg-slate-900 p-8 text-center text-sm text-slate-400">
          Calculando histórico...
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
            <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-4">
              <p className="text-xs text-slate-400">Média diária</p>
              <p className="mt-1 text-xl font-bold text-emerald-400">
                {Math.round(avg?.avg_kcal || 0)} kcal
              </p>
              <p className="text-[11px] text-slate-500">
                {avg?.logged_days || 0} dia(s) registrado(s)
              </p>
            </div>
            <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-4">
              <p className="text-xs text-slate-400">Proteína média</p>
              <p className="mt-1 text-xl font-bold text-sky-300">{avg?.avg_protein_g || 0}g</p>
            </div>
            <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-4">
              <p className="text-xs text-slate-400">Carbo médio</p>
              <p className="mt-1 text-xl font-bold text-violet-300">{avg?.avg_carbs_g || 0}g</p>
            </div>
            <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-4">
              <p className="text-xs text-slate-400">Gordura média</p>
              <p className="mt-1 text-xl font-bold text-amber-300">{avg?.avg_fat_g || 0}g</p>
            </div>
            <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-4">
              <p className="text-xs text-slate-400">Água média</p>
              <p className="mt-1 text-xl font-bold text-cyan-300">
                {Math.round(avg?.avg_water_ml || 0)} ml
              </p>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-5 space-y-3">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>Calorias por dia vs. meta ({Math.round(stats?.goals?.daily_kcal_goal || 2000)} kcal)</span>
            </div>
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={stats?.series || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="label" stroke="#94a3b8" fontSize={11} />
                  <YAxis stroke="#94a3b8" fontSize={11} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      borderColor: '#334155',
                      borderRadius: '12px',
                      fontSize: '12px',
                    }}
                  />
                  <ReferenceLine
                    y={stats?.goals?.daily_kcal_goal || 2000}
                    stroke="#f59e0b"
                    strokeDasharray="4 4"
                  />
                  <Bar dataKey="kcal" name="Calorias (kcal)" fill="#10b981" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
