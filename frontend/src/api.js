import axios from 'axios'

export const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

export function extractErrorMessage(err, fallback = 'Ocorreu um erro inesperado.') {
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (detail && typeof detail === 'object' && detail.message) return detail.message
  return err?.message || fallback
}
