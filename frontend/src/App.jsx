import { useEffect, useState } from 'react'
import { BarChart3, BookOpen, Camera, KeyRound, Settings, UtensilsCrossed } from 'lucide-react'
import { api } from './api'
import ApiKeyModal from './components/ApiKeyModal'
import { todayIsoDate } from './constants'
import DiaryPage from './pages/DiaryPage'
import GoalsSettingsPage from './pages/GoalsSettingsPage'
import LogMealPage from './pages/LogMealPage'
import StatsPage from './pages/StatsPage'

const NAV_ITEMS = [
  { id: 'diary', label: 'Diário', icon: BookOpen },
  { id: 'log', label: 'Registrar', icon: Camera },
  { id: 'stats', label: 'Evolução', icon: BarChart3 },
  { id: 'goals', label: 'Metas & IA', icon: Settings },
]

export default function App() {
  const [page, setPage] = useState('diary')
  const [selectedDate, setSelectedDate] = useState(todayIsoDate())
  const [aiStatus, setAiStatus] = useState(null)
  const [showKeyModal, setShowKeyModal] = useState(false)

  async function refreshAiStatus() {
    try {
      const { data } = await api.get('/settings/ai')
      setAiStatus(data)
      if (data.needs_setup && !data.onboarding_dismissed) {
        setShowKeyModal(true)
      }
    } catch {
      // Backend ainda inicializando ou indisponível
    }
  }

  useEffect(() => {
    refreshAiStatus()
  }, [])

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 pb-24 sm:pb-10">
      {/* Header */}
      <header className="sticky top-0 z-30 border-b border-slate-800/80 bg-slate-950/90 backdrop-blur">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-500 text-slate-950">
              <UtensilsCrossed className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-base font-bold leading-tight text-white">PlateLens</h1>
              <p className="text-[11px] text-slate-400">Diário Alimentar · Tabela TACO</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {aiStatus && (
              <button
                type="button"
                onClick={() => setShowKeyModal(true)}
                className={`inline-flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-medium border ${
                  aiStatus.ai_configured
                    ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                    : 'border-amber-500/40 bg-amber-500/10 text-amber-300'
                }`}
              >
                <KeyRound className="h-3.5 w-3.5" />
                {aiStatus.ai_configured ? aiStatus.gemini_model : 'Configurar API'}
              </button>
            )}
          </div>
        </div>

        {/* Navegação Desktop */}
        <nav className="mx-auto hidden max-w-4xl gap-2 px-4 pb-2.5 sm:flex">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon
            const active = page === item.id
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => setPage(item.id)}
                className={`inline-flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-semibold transition ${
                  active
                    ? 'bg-emerald-500 text-slate-950'
                    : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                }`}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </button>
            )
          })}
        </nav>
      </header>

      {/* Conteúdo */}
      <main className="mx-auto max-w-4xl px-4 py-5">
        {page === 'diary' && (
          <DiaryPage
            selectedDate={selectedDate}
            onChangeDate={setSelectedDate}
            onGoToLog={() => setPage('log')}
          />
        )}
        {page === 'log' && (
          <LogMealPage
            selectedDate={selectedDate}
            aiStatus={aiStatus}
            onOpenKeyModal={() => setShowKeyModal(true)}
            onSavedMeal={(savedDate) => {
              setSelectedDate(savedDate)
              setPage('diary')
            }}
          />
        )}
        {page === 'stats' && <StatsPage />}
        {page === 'goals' && (
          <GoalsSettingsPage
            aiStatus={aiStatus}
            onAiStatusUpdated={(updated) => setAiStatus(updated)}
          />
        )}

        <footer className="mt-8 border-t border-slate-900 pt-4 text-center text-[11px] text-slate-500">
          As calorias estimadas por foto são aproximações educativas com base na Tabela TACO e não substituem acompanhamento profissional.
        </footer>
      </main>

      {/* Navegação Mobile */}
      <nav className="fixed bottom-0 inset-x-0 z-30 grid grid-cols-4 border-t border-slate-800 bg-slate-950/95 backdrop-blur sm:hidden">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon
          const active = page === item.id
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => setPage(item.id)}
              className={`flex flex-col items-center justify-center gap-1 py-2.5 text-[11px] font-medium ${
                active ? 'text-emerald-400' : 'text-slate-400'
              }`}
            >
              <Icon className="h-5 w-5" />
              {item.label}
            </button>
          )
        })}
      </nav>

      {showKeyModal && (
        <ApiKeyModal
          aiStatus={aiStatus}
          onSaved={(updated) => {
            setAiStatus(updated)
            setShowKeyModal(false)
          }}
          onDismiss={(updated) => {
            if (updated) setAiStatus(updated)
            setShowKeyModal(false)
          }}
        />
      )}
    </div>
  )
}
