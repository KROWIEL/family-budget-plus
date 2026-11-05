const SYMBOLS = { BYN: 'Br', USD: '$' }

export function fmtAmount(value, currency = 'BYN', opts = {}) {
  const num = Number(value || 0)
  const sign = opts.sign && num > 0 ? '+' : ''
  const formatted = num.toLocaleString('ru-RU', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })
  const symbol = SYMBOLS[currency] || currency
  return `${sign}${formatted}\u00A0${symbol}`
}

export function currencySymbol(currency) {
  return SYMBOLS[currency] || currency
}

export function fmtDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
}

export function todayISO() {
  return new Date().toISOString().slice(0, 10)
}

// Принимает и точку, и запятую как десятичный разделитель (важно для мобильных клавиатур).
// Возвращает число либо NaN.
export function parseAmount(value) {
  if (typeof value === 'number') return value
  if (value == null || value === '') return NaN
  const normalized = String(value).replace(/\s/g, '').replace(',', '.')
  return parseFloat(normalized)
}

export function convertAmount(amount, from, to, rate) {
  if (from === to) return Math.round(amount * 100) / 100
  if (!rate) return null
  if (from === 'USD' && to === 'BYN') return Math.round(amount * rate * 100) / 100
  if (from === 'BYN' && to === 'USD') return Math.round((amount / rate) * 100) / 100
  return null
}

export function payDayHint(day) {
  const d = Number(day)
  if (!d) return ''
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const at = (y, m) => new Date(y, m, Math.min(d, new Date(y, m + 1, 0).getDate()))
  let target = at(today.getFullYear(), today.getMonth())
  if (target < today) target = at(today.getFullYear(), today.getMonth() + 1)
  const diff = Math.round((target - today) / 86400000)
  if (diff === 0) return 'платёж сегодня'
  if (diff === 1) return 'платёж завтра'
  return `платёж через ${diff} дн.`
}
