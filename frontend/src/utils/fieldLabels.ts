// Plain-language labels for the field keys inside saved records. The keys are fixed by the backend's format rules
// (backend/app/prompts/*.py FORMAT_RULES); a few older or alternative
// spellings the model used before that are mapped too. Anything unknown
// falls back to the key with underscores turned into spaces.

type Translate = (key: string) => string
type HasKey = (key: string) => boolean

const ALIASES: Record<string, string> = {
  emotions: 'emotion',
  feeling: 'emotion',
  feelings: 'emotion',
  coping: 'behavior',
  reaction: 'behavior',
  first_action: 'action',
  timing: 'when',
  time: 'when',
  help: 'support',
  help_needed: 'support',
  fallback: 'backup',
  plan_b: 'backup',
  alternative: 'backup',
  content: 'text',
}

export function fieldLabel(t: Translate, te: HasKey, key: string): string {
  const normalized = ALIASES[key.toLowerCase()] ?? key.toLowerCase()
  const path = `fields.${normalized}`
  return te(path) ? t(path) : key.replace(/_/g, ' ')
}

export function recordTypeLabel(t: Translate, te: HasKey, type: string): string {
  const path = `records.types.${type}`
  return te(path) ? t(path) : t('records.types.other')
}

/** A field value as readable text: lists joined, nested objects flattened. */
export function fieldText(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (Array.isArray(value)) return value.map(fieldText).filter(Boolean).join('、')
  if (typeof value === 'object') {
    return Object.values(value as Record<string, unknown>).map(fieldText).filter(Boolean).join('；')
  }
  return String(value)
}
