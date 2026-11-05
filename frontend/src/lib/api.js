async function request(method, path, body) {
  const opts = {
    method,
    credentials: 'same-origin',
    headers: {}
  }
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  }
  let res
  try {
    res = await fetch(`/api${path}`, opts)
  } catch {
    throw new Error('Нет связи с сервером')
  }
  let data = null
  const text = await res.text()
  if (text) {
    try { data = JSON.parse(text) } catch { data = text }
  }
  if (!res.ok) {
    const err = new Error(errorText(data) || `Ошибка запроса (${res.status})`)
    err.status = res.status
    throw err
  }
  return data
}

// FastAPI отдаёт detail строкой, а ошибки валидации — списком объектов.
// Разворачиваем список, иначе вместо причины пользователь видит «Ошибка запроса».
function errorText(data) {
  const detail = data && data.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((d) => [d.loc?.filter((p) => p !== 'body').join('.'), d.msg].filter(Boolean).join(': '))
      .join('; ')
  }
  return typeof data === 'string' ? data : ''
}

export const api = {
  get: (p) => request('GET', p),
  post: (p, b) => request('POST', p, b ?? {}),
  patch: (p, b) => request('PATCH', p, b ?? {}),
  del: (p) => request('DELETE', p)
}
