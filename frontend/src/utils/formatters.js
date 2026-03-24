export const formatEuros = (amount) => {
  if (amount === null || amount === undefined) return '—'
  return `${amount >= 0 ? '+' : ''}${amount.toFixed(2)}€`
}

export const formatPct = (value) => {
  if (value === null || value === undefined) return '—'
  return `${(value * 100).toFixed(1)}%`
}

export const formatCote = (cote) => {
  if (!cote) return '—'
  return cote.toFixed(2)
}

export const formatDate = (timestamp) => {
  if (!timestamp) return '—'
  const date = new Date(timestamp * 1000)
  return date.toLocaleDateString('fr-FR', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  })
}

export const formatHeure = (timestamp) => {
  if (!timestamp) return '—'
  const date = new Date(timestamp * 1000)
  return date.toLocaleTimeString('fr-FR', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

export const formatROI = (roi) => {
  if (roi === null || roi === undefined) return '—'
  const pct = (roi * 100).toFixed(1)
  return `${roi >= 0 ? '+' : ''}${pct}%`
}
