// A step's text in three parts (目标 / 问法 / 示例), stored as one string —
// must match backend app/prompts/parts.py. Plain text is the "goal" part
// alone, so older text and code defaults read unchanged.

export const PARTS = ['goal', 'ask', 'example'] as const
export type Part = (typeof PARTS)[number]
export type Parts = Record<Part, string>

const MARK = '⟦step-parts⟧\n'

export function splitParts(content: string): Parts {
  if (content.startsWith(MARK)) {
    try {
      const v = JSON.parse(content.slice(MARK.length)) as Partial<Parts>
      return { goal: v.goal ?? '', ask: v.ask ?? '', example: v.example ?? '' }
    } catch {
      // fall through: treat as plain text
    }
  }
  return { goal: content, ask: '', example: '' }
}

export function joinParts(p: Parts): string {
  if (!p.ask.trim() && !p.example.trim()) return p.goal
  return MARK + JSON.stringify(p)
}

export function partsEmpty(content: string): boolean {
  const p = splitParts(content)
  return !p.goal.trim() && !p.ask.trim() && !p.example.trim()
}
