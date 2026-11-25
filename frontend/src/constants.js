export const MEAL_TYPES = [
  { id: 'cafe', label: 'Café da Manhã', defaultTime: '08:00' },
  { id: 'almoco', label: 'Almoço', defaultTime: '12:30' },
  { id: 'jantar', label: 'Jantar', defaultTime: '20:00' },
  { id: 'lanche', label: 'Lanches', defaultTime: '16:00' },
]

export const MEAL_TYPE_LABELS = Object.fromEntries(MEAL_TYPES.map((m) => [m.id, m.label]))

export const ACTIVITY_LEVELS = [
  { id: 'sedentary', label: 'Sedentário (pouco ou nenhum exercício)' },
  { id: 'light', label: 'Leve (1–3 dias/semana)' },
  { id: 'moderate', label: 'Moderado (3–5 dias/semana)' },
  { id: 'active', label: 'Intenso (6–7 dias/semana)' },
  { id: 'very_active', label: 'Muito intenso (2x/dia ou trabalho físico)' },
]

export const GOAL_MODES = [
  { id: 'lose', label: 'Déficit (Perder peso · -400 kcal)' },
  { id: 'maintain', label: 'Manutenção (Manter peso)' },
  { id: 'gain', label: 'Superávit leve (Ganhar massa · +300 kcal)' },
]

export const MACRO_PRESETS = [
  { id: 'balanced', label: 'Equilibrado (por peso · 27% gordura)' },
  { id: 'high_protein', label: 'Alta Proteína (2,1 g/kg · 25% gordura)' },
  { id: 'low_carb', label: 'Low Carb (20% carbo · 1,8 g/kg proteína)' },
  { id: 'zone_30_40_30', label: 'Clássico 30% P / 40% C / 30% G' },
]

export function todayIsoDate() {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function currentTimeHHMM() {
  const d = new Date()
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

export function formatDateBR(isoDate) {
  if (!isoDate || isoDate.length < 10) return isoDate || ''
  const [y, m, d] = isoDate.split('-')
  return `${d}/${m}/${y}`
}

export function shiftIsoDate(isoDate, deltaDays) {
  const [y, m, d] = isoDate.split('-').map(Number)
  const dt = new Date(y, m - 1, d)
  dt.setDate(dt.getDate() + deltaDays)
  const yy = dt.getFullYear()
  const mm = String(dt.getMonth() + 1).padStart(2, '0')
  const dd = String(dt.getDate()).padStart(2, '0')
  return `${yy}-${mm}-${dd}`
}

export function guessMealTypeByHour() {
  const h = new Date().getHours()
  if (h < 10) return 'cafe'
  if (h < 15) return 'almoco'
  if (h < 18) return 'lanche'
  return 'jantar'
}
