import { useEffect, useState } from 'react'
import {
  AlertTriangle,
  Camera,
  Check,
  ImagePlus,
  KeyRound,
  Minus,
  Pencil,
  Plus,
  Search,
  Sparkles,
  Star,
  Trash2,
} from 'lucide-react'
import { api, extractErrorMessage } from '../api'
import TacoSearchModal from '../components/TacoSearchModal'
import {
  MEAL_TYPES,
  currentTimeHHMM,
  guessMealTypeByHour,
  todayIsoDate,
} from '../constants'

export default function LogMealPage({
  selectedDate,
  aiStatus,
  onOpenKeyModal,
  onSavedMeal,
}) {
  const [tab, setTab] = useState('photo') // 'photo' | 'manual' | 'favorites'
  const [file, setFile] = useState(null)
  const [previewUrl, setPreviewUrl] = useState('')
  const [contextHint, setContextHint] = useState('')
  const [plateSize, setPlateSize] = useState('normal')
  const [modelMode, setModelMode] = useState('precise')

  const [analyzing, setAnalyzing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  // Estado do rascunho da refeição (tanto foto quanto manual)
  const [draftTitle, setDraftTitle] = useState('')
  const [mealType, setMealType] = useState(guessMealTypeByHour())
  const [eatenDate, setEatenDate] = useState(selectedDate || todayIsoDate())
  const [eatenTime, setEatenTime] = useState(currentTimeHHMM())
  const [notes, setNotes] = useState('')
  const [photoFilename, setPhotoFilename] = useState(null)
  const [aiMeta, setAiMeta] = useState({ provider: 'manual', model: '' })
  const [warnings, setWarnings] = useState([])
  const [items, setItems] = useState([])
  const [totals, setTotals] = useState(null)
  const [isFavorite, setIsFavorite] = useState(false)

  const [showTacoModal, setShowTacoModal] = useState(false)
  const [favorites, setFavorites] = useState([])
  const [loadingFavs, setLoadingFavs] = useState(false)

  // Cadastro / edição de alimento personalizado
  const [showCustomForm, setShowCustomForm] = useState(false)
  const [editingFoodId, setEditingFoodId] = useState(null)
  const [customFoods, setCustomFoods] = useState([])
  const [customFood, setCustomFood] = useState({
    name: '',
    kcal_per_100g: '',
    protein_g: '',
    carbs_g: '',
    fat_g: '',
    fiber_g: '',
    household_unit_label: '1 porção',
    household_unit_grams: '100',
  })

  async function loadCustomFoods() {
    try {
      const { data } = await api.get('/foods/custom')
      setCustomFoods(data)
    } catch {
      // ignora silenciosamente se offline
    }
  }

  useEffect(() => {
    setEatenDate(selectedDate || todayIsoDate())
  }, [selectedDate])

  useEffect(() => {
    if (!file) {
      setPreviewUrl('')
      return
    }
    const url = URL.createObjectURL(file)
    setPreviewUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [file])

  useEffect(() => {
    if (tab === 'favorites') {
      setLoadingFavs(true)
      api
        .get('/meals/favorites')
        .then((res) => setFavorites(res.data))
        .finally(() => setLoadingFavs(false))
    } else if (tab === 'manual') {
      loadCustomFoods()
    }
  }, [tab])

  async function recalculateItems(nextItems) {
    if (nextItems.length === 0) {
      setItems([])
      setTotals(null)
      return
    }
    try {
      const payload = {
        items: nextItems.map((it) => ({
          taco_food_id: it.taco_food_id,
          label: it.label,
          grams: Math.max(1, Number(it.grams) || 1),
          per_100g: it.per_100g,
          confidence: it.confidence ?? 1.0,
          source: it.source || 'taco',
        })),
      }
      const { data } = await api.post('/meals/recalculate', payload)
      setItems(data.items)
      setTotals(data.totals)
    } catch (err) {
      setError(extractErrorMessage(err))
    }
  }

  async function handleAnalyzePhoto(e) {
    e.preventDefault()
    if (!file) {
      setError('Tire ou selecione uma foto do prato primeiro.')
      return
    }
    setAnalyzing(true)
    setError('')
    try {
      const form = new FormData()
      form.append('file', file)
      form.append('meal_context', contextHint)
      form.append('plate_size', plateSize)
      form.append('model_mode', modelMode)

      const { data } = await api.post('/meals/analyze', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setDraftTitle(data.plate_summary || 'Refeição analisada')
      setPhotoFilename(data.photo_filename)
      setAiMeta({ provider: data.ai_provider_used, model: data.ai_model_used })
      setWarnings(data.warnings || [])
      setItems(data.items || [])
      setTotals(data.totals)
    } catch (err) {
      if (err?.response?.status === 428) {
        onOpenKeyModal()
      }
      setError(extractErrorMessage(err, 'Falha ao analisar a foto.'))
    } finally {
      setAnalyzing(false)
    }
  }

  async function handleAdjustGrams(idx, nextGrams) {
    const clamped = Math.max(1, Math.min(5000, Math.round(nextGrams)))
    const updated = items.map((it, i) => (i === idx ? { ...it, grams: clamped } : it))
    await recalculateItems(updated)
  }

  async function handleRemoveItem(idx) {
    const updated = items.filter((_, i) => i !== idx)
    await recalculateItems(updated)
  }

  async function handleAddTacoFood(food) {
    setShowTacoModal(false)
    const defaultGrams = food.household_unit_grams || 100
    const nextItem = {
      taco_food_id: food.id,
      label: food.name,
      grams: defaultGrams,
      per_100g: {
        kcal: food.kcal_per_100g,
        protein_g: food.protein_g,
        carbs_g: food.carbs_g,
        fat_g: food.fat_g,
        fiber_g: food.fiber_g,
      },
      confidence: 1.0,
      source: items.length > 0 ? 'taco' : 'manual',
    }
    if (!draftTitle) {
      setDraftTitle(food.name)
    }
    await recalculateItems([...items, nextItem])
  }

  function resetCustomForm() {
    setEditingFoodId(null)
    setShowCustomForm(false)
    setCustomFood({
      name: '',
      kcal_per_100g: '',
      protein_g: '',
      carbs_g: '',
      fat_g: '',
      fiber_g: '',
      household_unit_label: '1 porção',
      household_unit_grams: '100',
    })
  }

  function startEditCustomFood(food) {
    setEditingFoodId(food.id)
    setCustomFood({
      name: food.name,
      kcal_per_100g: String(food.kcal_per_100g),
      protein_g: String(food.protein_g),
      carbs_g: String(food.carbs_g),
      fat_g: String(food.fat_g),
      fiber_g: String(food.fiber_g ?? 0),
      household_unit_label: food.household_unit_label || '1 porção',
      household_unit_grams: String(food.household_unit_grams || 100),
    })
    setShowCustomForm(true)
  }

  async function handleDeleteCustomFood(foodId) {
    setError('')
    try {
      await api.delete(`/foods/${foodId}`)
      if (editingFoodId === foodId) {
        resetCustomForm()
      }
      await loadCustomFoods()
    } catch (err) {
      setError(extractErrorMessage(err))
    }
  }

  async function handleSaveCustomFood(e) {
    e.preventDefault()
    setError('')
    const payload = {
      name: customFood.name,
      kcal_per_100g: Number(customFood.kcal_per_100g),
      protein_g: Number(customFood.protein_g || 0),
      carbs_g: Number(customFood.carbs_g || 0),
      fat_g: Number(customFood.fat_g || 0),
      fiber_g: Number(customFood.fiber_g || 0),
      household_unit_label: customFood.household_unit_label || '1 porção',
      household_unit_grams: Number(customFood.household_unit_grams || 100),
    }
    try {
      if (editingFoodId !== null) {
        await api.put(`/foods/${editingFoodId}`, payload)
        resetCustomForm()
        await loadCustomFoods()
      } else {
        const { data } = await api.post('/foods', payload)
        resetCustomForm()
        await loadCustomFoods()
        await handleAddTacoFood(data)
      }
    } catch (err) {
      setError(extractErrorMessage(err))
    }
  }

  async function handleSaveMeal() {
    if (items.length === 0) {
      setError('Adicione ao menos um alimento antes de salvar.')
      return
    }
    setSaving(true)
    setError('')
    try {
      await api.post('/meals', {
        eaten_date: eatenDate,
        eaten_time: eatenTime,
        meal_type: mealType,
        title: draftTitle.trim() || items[0].label,
        photo_filename: photoFilename,
        notes,
        ai_provider_used: aiMeta.provider,
        ai_model_used: aiMeta.model,
        warnings,
        is_favorite: isFavorite,
        items: items.map((it) => ({
          taco_food_id: it.taco_food_id,
          label: it.label,
          grams: it.grams,
          per_100g: it.per_100g,
          confidence: it.confidence,
          source: it.source,
        })),
      })
      onSavedMeal(eatenDate)
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  async function handleRepeatFavorite(fav) {
    setSaving(true)
    setError('')
    try {
      await api.post(`/meals/${fav.id}/repeat`, null, {
        params: { eaten_date: eatenDate, meal_type: mealType },
      })
      onSavedMeal(eatenDate)
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  function resetDraft() {
    setFile(null)
    setPhotoFilename(null)
    setItems([])
    setTotals(null)
    setWarnings([])
    setDraftTitle('')
    setNotes('')
    setAiMeta({ provider: 'manual', model: '' })
  }

  return (
    <div className="space-y-5">
      {/* Seletor de Modo */}
      <div className="grid grid-cols-3 gap-2 rounded-2xl border border-slate-800 bg-slate-900 p-1.5">
        <button
          type="button"
          onClick={() => setTab('photo')}
          className={`flex items-center justify-center gap-1.5 rounded-xl py-2 text-xs font-semibold transition ${
            tab === 'photo' ? 'bg-emerald-500 text-slate-950' : 'text-slate-300 hover:bg-slate-800'
          }`}
        >
          <Camera className="h-4 w-4" /> Foto (IA)
        </button>
        <button
          type="button"
          onClick={() => setTab('manual')}
          className={`flex items-center justify-center gap-1.5 rounded-xl py-2 text-xs font-semibold transition ${
            tab === 'manual' ? 'bg-emerald-500 text-slate-950' : 'text-slate-300 hover:bg-slate-800'
          }`}
        >
          <Search className="h-4 w-4" /> Tabela TACO
        </button>
        <button
          type="button"
          onClick={() => setTab('favorites')}
          className={`flex items-center justify-center gap-1.5 rounded-xl py-2 text-xs font-semibold transition ${
            tab === 'favorites' ? 'bg-emerald-500 text-slate-950' : 'text-slate-300 hover:bg-slate-800'
          }`}
        >
          <Star className="h-4 w-4" /> Favoritas
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-xs text-rose-300">
          {error}
        </div>
      )}

      {/* ABA FOTO */}
      {tab === 'photo' && (
        <div className="space-y-4">
          {aiStatus?.needs_setup && (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4">
              <div className="flex items-start gap-2.5 text-xs text-amber-200">
                <KeyRound className="h-4 w-4 shrink-0 mt-0.5 text-amber-300" />
                <div>
                  <p className="font-semibold">Chave da Gemini API ainda não configurada</p>
                  <p className="text-amber-200/80">
                    Para analisar fotos automaticamente, informe sua chave do Google AI Studio.
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={onOpenKeyModal}
                className="rounded-xl bg-amber-400 px-3.5 py-2 text-xs font-semibold text-slate-950 hover:bg-amber-300"
              >
                Configurar API Key
              </button>
            </div>
          )}

          <form
            onSubmit={handleAnalyzePhoto}
            className="rounded-2xl border border-slate-800 bg-slate-900/90 p-5 space-y-4"
          >
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <label className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-emerald-500/40 bg-emerald-500/5 p-5 text-center transition hover:border-emerald-400 hover:bg-emerald-500/10">
                <Camera className="h-8 w-8 text-emerald-400" />
                <span className="text-sm font-semibold text-white">Tirar foto com a câmera</span>
                <span className="text-[11px] text-slate-400">Abre câmera traseira no celular</span>
                <input
                  type="file"
                  accept="image/*"
                  capture="environment"
                  className="hidden"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                />
              </label>

              <label className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-slate-700 bg-slate-950/60 p-5 text-center transition hover:border-slate-500">
                <ImagePlus className="h-8 w-8 text-slate-300" />
                <span className="text-sm font-semibold text-white">Escolher da galeria</span>
                <span className="text-[11px] text-slate-400">JPG, PNG ou WEBP até 15 MB</span>
                <input
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                />
              </label>
            </div>

            {previewUrl && (
              <div className="overflow-hidden rounded-xl border border-slate-700 bg-slate-950">
                <img
                  src={previewUrl}
                  alt="Prévia do prato"
                  className="max-h-64 w-full object-contain"
                />
              </div>
            )}

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div className="sm:col-span-1">
                <label className="mb-1 block text-xs text-slate-400">Tamanho do prato</label>
                <select
                  value={plateSize}
                  onChange={(e) => setPlateSize(e.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"
                >
                  <option value="pequeno">Prato pequeno / sobremesa</option>
                  <option value="normal">Prato raso normal</option>
                  <option value="grande">Prato fundo / grande</option>
                </select>
              </div>
              <div className="sm:col-span-2">
                <label className="mb-1 block text-xs text-slate-400">Modo de análise (Gemini)</label>
                <select
                  value={modelMode}
                  onChange={(e) => setModelMode(e.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"
                >
                  <option value="precise">Preciso (3.6 Flash · fallback automático 429)</option>
                  <option value="lite">Econômico (3.5 Flash-Lite · 500 req/dia)</option>
                </select>
              </div>
            </div>

            <div>
              <label className="mb-1 block text-xs text-slate-400">
                Dica opcional (ajuda com óleos, molhos ou preparo)
              </label>
              <input
                type="text"
                value={contextHint}
                onChange={(e) => setContextHint(e.target.value)}
                placeholder="Ex: frango grelhado no azeite, feijão sem linguiça, café sem açúcar..."
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2.5 text-sm text-white placeholder-slate-500 focus:border-emerald-500 focus:outline-none"
              />
            </div>

            <button
              type="submit"
              disabled={!file || analyzing}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-500 py-3 text-sm font-semibold text-slate-950 hover:bg-emerald-400 disabled:opacity-50"
            >
              <Sparkles className="h-4 w-4" />
              {analyzing ? 'Analisando prato e cruzando Tabela TACO...' : 'Analisar Prato'}
            </button>
          </form>
        </div>
      )}

      {/* ABA MANUAL (TACO) */}
      {tab === 'manual' && (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-5 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="text-sm font-semibold text-white">Montar refeição pela Tabela TACO</h3>
              <p className="text-xs text-slate-400">Funciona 100% offline sem consumir cota de IA.</p>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => {
                  if (showCustomForm && editingFoodId === null) {
                    resetCustomForm()
                  } else {
                    setEditingFoodId(null)
                    setShowCustomForm(true)
                  }
                }}
                className="rounded-xl border border-slate-700 bg-slate-800 px-3 py-2 text-xs font-medium text-slate-200 hover:bg-slate-700"
              >
                + Alimento próprio
              </button>
              <button
                type="button"
                onClick={() => setShowTacoModal(true)}
                className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-500 px-3.5 py-2 text-xs font-semibold text-slate-950 hover:bg-emerald-400"
              >
                <Search className="h-3.5 w-3.5" /> Buscar na TACO
              </button>
            </div>
          </div>

          {showCustomForm && (
            <form
              onSubmit={handleSaveCustomFood}
              className="rounded-xl border border-slate-700 bg-slate-950 p-4 space-y-3"
            >
              <p className="text-xs font-semibold text-emerald-300">
                {editingFoodId !== null
                  ? 'Editar alimento personalizado (por 100g)'
                  : 'Novo alimento personalizado (por 100g)'}
              </p>
              <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
                <input
                  required
                  placeholder="Nome do alimento"
                  value={customFood.name}
                  onChange={(e) => setCustomFood({ ...customFood, name: e.target.value })}
                  className="col-span-2 sm:col-span-3 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-white"
                />
                <input
                  required
                  type="number"
                  step="0.1"
                  placeholder="Kcal / 100g"
                  value={customFood.kcal_per_100g}
                  onChange={(e) => setCustomFood({ ...customFood, kcal_per_100g: e.target.value })}
                  className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-white"
                />
                <input
                  type="number"
                  step="0.1"
                  placeholder="Proteína (g)"
                  value={customFood.protein_g}
                  onChange={(e) => setCustomFood({ ...customFood, protein_g: e.target.value })}
                  className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-white"
                />
                <input
                  type="number"
                  step="0.1"
                  placeholder="Carbo (g)"
                  value={customFood.carbs_g}
                  onChange={(e) => setCustomFood({ ...customFood, carbs_g: e.target.value })}
                  className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-white"
                />
                <input
                  type="number"
                  step="0.1"
                  placeholder="Gordura (g)"
                  value={customFood.fat_g}
                  onChange={(e) => setCustomFood({ ...customFood, fat_g: e.target.value })}
                  className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-white"
                />
                <input
                  type="number"
                  step="0.1"
                  placeholder="Fibra (g)"
                  value={customFood.fiber_g}
                  onChange={(e) => setCustomFood({ ...customFood, fiber_g: e.target.value })}
                  className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-white"
                />
                <input
                  placeholder="Medida (ex: 1 unidade)"
                  value={customFood.household_unit_label}
                  onChange={(e) => setCustomFood({ ...customFood, household_unit_label: e.target.value })}
                  className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-white"
                />
                <input
                  type="number"
                  step="1"
                  placeholder="Gramas da medida"
                  value={customFood.household_unit_grams}
                  onChange={(e) => setCustomFood({ ...customFood, household_unit_grams: e.target.value })}
                  className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-white"
                />
              </div>
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={resetCustomForm}
                  className="rounded-lg px-3 py-1.5 text-xs text-slate-400 hover:bg-slate-800"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="rounded-lg bg-emerald-500 px-3 py-1.5 text-xs font-semibold text-slate-950"
                >
                  {editingFoodId !== null ? 'Salvar alterações' : 'Cadastrar e adicionar'}
                </button>
              </div>
            </form>
          )}

          {customFoods.length > 0 && (
            <div className="space-y-2 border-t border-slate-800 pt-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                Meus alimentos cadastrados ({customFoods.length})
              </p>
              <div className="space-y-1.5">
                {customFoods.map((cf) => (
                  <div
                    key={cf.id}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-xs font-semibold text-slate-100">{cf.name}</p>
                      <p className="text-[11px] text-slate-400">
                        {Math.round(cf.kcal_per_100g)} kcal · P {cf.protein_g}g · C {cf.carbs_g}g · G {cf.fat_g}g ({cf.household_unit_label}: {cf.household_unit_grams}g)
                      </p>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => handleAddTacoFood(cf)}
                        className="rounded-lg bg-emerald-500/15 px-2.5 py-1 text-[11px] font-semibold text-emerald-300 hover:bg-emerald-500/25"
                      >
                        + Usar
                      </button>
                      <button
                        type="button"
                        onClick={() => startEditCustomFood(cf)}
                        className="rounded-lg bg-slate-800 p-1.5 text-slate-300 hover:bg-slate-700 hover:text-white"
                        aria-label={`Editar ${cf.name}`}
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDeleteCustomFood(cf.id)}
                        className="rounded-lg bg-rose-500/10 p-1.5 text-rose-400 hover:bg-rose-500/20"
                        aria-label={`Excluir ${cf.name}`}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ABA FAVORITAS */}
      {tab === 'favorites' && (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-5 space-y-3">
          <h3 className="text-sm font-semibold text-white">Refeições favoritas e recentes</h3>
          {loadingFavs ? (
            <p className="text-xs text-slate-400">Carregando...</p>
          ) : favorites.length === 0 ? (
            <p className="text-xs text-slate-400">
              Nenhuma refeição salva ainda. Marque a estrela em qualquer refeição do diário!
            </p>
          ) : (
            <div className="space-y-2">
              {favorites.map((fav) => (
                <div
                  key={fav.id}
                  className="flex items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-950/60 p-3"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-white">{fav.title}</p>
                    <p className="text-xs text-slate-400">
                      {Math.round(fav.total_kcal)} kcal · P {fav.total_protein_g}g · C {fav.total_carbs_g}g · G {fav.total_fat_g}g
                    </p>
                  </div>
                  <button
                    type="button"
                    disabled={saving}
                    onClick={() => handleRepeatFavorite(fav)}
                    className="shrink-0 rounded-xl bg-emerald-500/15 px-3 py-2 text-xs font-semibold text-emerald-300 hover:bg-emerald-500/25"
                  >
                    Lançar agora
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* REVISÃO INTERATIVA DO PRATO (aparece sempre que houver itens) */}
      {items.length > 0 && tab !== 'favorites' && (
        <div className="rounded-2xl border border-emerald-500/30 bg-slate-900 p-5 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="text-base font-semibold text-white">Revisar porções & Salvar</h3>
              <p className="text-xs text-slate-400">
                Ajuste os gramas abaixo — os macros recalculam instantaneamente na Tabela TACO.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setShowTacoModal(true)}
              className="inline-flex items-center gap-1 rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-3 py-1.5 text-xs font-semibold text-emerald-300 hover:bg-emerald-500/20"
            >
              <Plus className="h-3.5 w-3.5" /> Add item (azeite, molho...)
            </button>
          </div>

          {warnings.length > 0 && (
            <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-200 space-y-1">
              <div className="flex items-center gap-1.5 font-semibold text-amber-300">
                <AlertTriangle className="h-4 w-4" /> Pontos de atenção da estimativa:
              </div>
              {warnings.map((w, idx) => (
                <p key={idx}>• {w}</p>
              ))}
            </div>
          )}

          {totals && (
            <div className="grid grid-cols-2 gap-2 rounded-xl bg-slate-950 p-3.5 sm:grid-cols-5">
              <div className="col-span-2 sm:col-span-1">
                <p className="text-[11px] text-slate-400">Total estimado</p>
                <p className="text-lg font-bold text-emerald-400">{Math.round(totals.total_kcal)} kcal</p>
                <p className="text-[10px] text-slate-500">
                  {Math.round(totals.total_kcal_min)}–{Math.round(totals.total_kcal_max)} kcal
                </p>
              </div>
              <div>
                <p className="text-[11px] text-slate-400">Proteínas</p>
                <p className="text-sm font-semibold text-sky-300">{totals.total_protein_g}g</p>
              </div>
              <div>
                <p className="text-[11px] text-slate-400">Carboidratos</p>
                <p className="text-sm font-semibold text-violet-300">{totals.total_carbs_g}g</p>
              </div>
              <div>
                <p className="text-[11px] text-slate-400">Gorduras</p>
                <p className="text-sm font-semibold text-amber-300">{totals.total_fat_g}g</p>
              </div>
              <div>
                <p className="text-[11px] text-slate-400">Fibras</p>
                <p className="text-sm font-semibold text-emerald-300">{totals.total_fiber_g}g</p>
              </div>
            </div>
          )}

          <div className="space-y-2.5">
            {items.map((item, idx) => (
              <div
                key={`${item.label}-${idx}`}
                className="rounded-xl border border-slate-800 bg-slate-950/70 p-3 space-y-2"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="text-sm font-medium text-white">{item.label}</span>
                      <span
                        className={`rounded-md px-1.5 py-0.5 text-[10px] font-semibold ${
                          item.source === 'ai_fallback'
                            ? 'bg-amber-500/15 text-amber-300'
                            : 'bg-emerald-500/15 text-emerald-300'
                        }`}
                      >
                        {item.source === 'ai_fallback' ? 'Estimativa IA' : 'Tabela TACO'}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-400">
                      {Math.round(item.kcal)} kcal · P {item.protein_g}g · C {item.carbs_g}g · G {item.fat_g}g
                      {item.portion_label ? ` · ${item.portion_label}` : ''}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleRemoveItem(idx)}
                    className="rounded-lg p-1 text-slate-400 hover:bg-rose-500/15 hover:text-rose-400"
                    aria-label="Remover item"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>

                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={() => handleAdjustGrams(idx, item.grams - 25)}
                      className="rounded-lg border border-slate-700 bg-slate-900 p-1.5 text-slate-300 hover:bg-slate-800"
                    >
                      <Minus className="h-3.5 w-3.5" />
                    </button>
                    <input
                      type="number"
                      min="1"
                      max="5000"
                      value={Math.round(item.grams)}
                      onChange={(e) => handleAdjustGrams(idx, Number(e.target.value))}
                      className="w-20 rounded-lg border border-slate-700 bg-slate-900 px-2 py-1 text-center text-xs font-semibold text-white"
                    />
                    <span className="text-xs text-slate-400">g</span>
                    <button
                      type="button"
                      onClick={() => handleAdjustGrams(idx, item.grams + 25)}
                      className="rounded-lg border border-slate-700 bg-slate-900 p-1.5 text-slate-300 hover:bg-slate-800"
                    >
                      <Plus className="h-3.5 w-3.5" />
                    </button>
                  </div>

                  {item.household_unit_label && item.household_unit_grams && (
                    <button
                      type="button"
                      onClick={() => handleAdjustGrams(idx, item.household_unit_grams)}
                      className="rounded-lg bg-slate-800 px-2.5 py-1 text-[11px] text-slate-300 hover:bg-slate-700"
                    >
                      {item.household_unit_label} ({item.household_unit_grams}g)
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 pt-1">
            <input
              type="text"
              value={draftTitle}
              onChange={(e) => setDraftTitle(e.target.value)}
              placeholder="Título da refeição"
              className="sm:col-span-3 rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2 text-sm text-white"
            />
            <select
              value={mealType}
              onChange={(e) => setMealType(e.target.value)}
              className="rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"
            >
              {MEAL_TYPES.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
            </select>
            <input
              type="date"
              value={eatenDate}
              onChange={(e) => setEatenDate(e.target.value)}
              className="rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"
            />
            <input
              type="time"
              value={eatenTime}
              onChange={(e) => setEatenTime(e.target.value)}
              className="rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"
            />
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Observações (opcional)"
              className="sm:col-span-3 rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2 text-xs text-white"
            />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2 pt-2">
            <label className="inline-flex cursor-pointer items-center gap-2 text-xs text-slate-300">
              <input
                type="checkbox"
                checked={isFavorite}
                onChange={(e) => setIsFavorite(e.target.checked)}
                className="rounded border-slate-700 bg-slate-950 text-emerald-500"
              />
              Salvar também nas favoritas
            </label>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={resetDraft}
                className="rounded-xl px-3.5 py-2.5 text-xs text-slate-400 hover:bg-slate-800"
              >
                Limpar
              </button>
              <button
                type="button"
                disabled={saving}
                onClick={handleSaveMeal}
                className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-slate-950 hover:bg-emerald-400 disabled:opacity-50"
              >
                <Check className="h-4 w-4" />
                {saving ? 'Salvando...' : 'Salvar no Diário'}
              </button>
            </div>
          </div>
        </div>
      )}

      {showTacoModal && (
        <TacoSearchModal
          onSelect={handleAddTacoFood}
          onClose={() => setShowTacoModal(false)}
        />
      )}
    </div>
  )
}
