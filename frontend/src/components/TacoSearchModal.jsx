import { useEffect, useState } from 'react'
import { Search, Plus, X } from 'lucide-react'
import { api } from '../api'

export default function TacoSearchModal({
  onSelect,
  onClose,
  title = 'Adicionar alimento da Tabela TACO',
}) {
  const [query, setQuery] = useState('')
  const [foods, setFoods] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const timer = setTimeout(async () => {
      setLoading(true)
      try {
        const { data } = await api.get('/foods/search', { params: { q: query, limit: 30 } })
        setFoods(data)
      } finally {
        setLoading(false)
      }
    }, 180)
    return () => clearTimeout(timer)
  }, [query])

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-slate-950/80 p-0 sm:p-4 backdrop-blur-sm">
      <div className="flex max-h-[85vh] w-full max-w-xl flex-col rounded-t-2xl sm:rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-800 px-4 py-3">
          <h3 className="text-sm font-semibold text-white">{title}</h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-800 hover:text-white"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-3 border-b border-slate-800">
          <div className="relative">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              type="text"
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Buscar alimento (ex: arroz, azeite, feijao, ovo)..."
              className="w-full rounded-xl border border-slate-700 bg-slate-950 py-2 pl-9 pr-3 text-sm text-white placeholder-slate-500 focus:border-emerald-500 focus:outline-none"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
          {loading && <p className="p-4 text-center text-xs text-slate-400">Buscando...</p>}
          {!loading && foods.length === 0 && (
            <p className="p-4 text-center text-xs text-slate-400">Nenhum alimento encontrado na TACO.</p>
          )}
          {foods.map((food) => (
            <button
              key={food.id}
              type="button"
              onClick={() => onSelect(food)}
              className="flex w-full items-center justify-between rounded-xl border border-slate-800/80 bg-slate-950/60 px-3.5 py-2.5 text-left transition hover:border-emerald-500/50 hover:bg-slate-800/70"
            >
              <div>
                <div className="flex items-center gap-1.5">
                  <p className="text-sm font-medium text-slate-100">{food.name}</p>
                  {food.is_custom && (
                    <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-300">
                      Próprio
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-400">
                  {food.category} · {Math.round(food.kcal_per_100g)} kcal/100g · {food.household_unit_label} ({food.household_unit_grams}g)
                </p>
              </div>
              <span className="ml-3 flex items-center gap-1 rounded-lg bg-emerald-500/15 px-2.5 py-1 text-xs font-medium text-emerald-300">
                <Plus className="h-3.5 w-3.5" /> Add
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
