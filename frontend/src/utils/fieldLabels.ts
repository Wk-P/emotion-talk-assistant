// Plain-language labels for the field keys inside summary / plan cards and
// saved records. The keys are fixed by the backend's format rules
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

// ---- Saving a confirmed card as a record ----

export interface RecordDraft {
  recordType: string
  payload: Record<string, unknown>
}

interface ConfirmedCard {
  type: string
  items?: { id: string; label: string }[] | null
}

interface Confirmation {
  selected_labels?: string[]
  custom_text?: string
  fields?: Record<string, unknown>
}

/**
 * What a confirmed card would be saved as, or null if that kind of card
 * isn't worth keeping as a record (e.g. the opening intent choice). Option
 * cards may report ids rather than labels, so they're looked up here.
 */
export function recordFromConfirmation(card: ConfirmedCard, c: Confirmation): RecordDraft | null {
  const labels = (c.selected_labels ?? []).map((v) => card.items?.find((i) => i.id === v)?.label ?? v)
  const chosen = [...labels, ...(c.custom_text ? [c.custom_text] : [])].filter(Boolean)
  const hasFields = c.fields && Object.values(c.fields).some((v) => fieldText(v))

  switch (card.type) {
    case 'seb_summary':
      return hasFields ? { recordType: 'situation_emotion_behavior', payload: c.fields! } : null
    case 'plan_form':
      return hasFields ? { recordType: 'recovery_plan', payload: c.fields! } : null
    case 'self_kindness_options':
      return chosen.length ? { recordType: 'self_kindness', payload: { text: chosen.join('\n') } } : null
    case 'recovery_action_options':
      return chosen.length ? { recordType: 'recovery_plan', payload: { action: chosen } } : null
    default:
      return null
  }
}
