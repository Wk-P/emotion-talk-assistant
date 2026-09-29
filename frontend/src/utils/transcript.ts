import type { HistoryMessageItem } from '@/api/client'

interface TranscriptLabels {
  title: string
  createdAt: string
  user: string
  assistant: string
}

export function buildTranscriptMarkdown(
  createdAt: string,
  messages: HistoryMessageItem[],
  labels: TranscriptLabels,
): string {
  const lines = [`# ${labels.title}`, '', `${labels.createdAt}: ${new Date(createdAt).toLocaleString()}`, '']
  for (const m of messages) {
    if (m.role !== 'user' && m.role !== 'assistant') continue
    const speaker = m.role === 'user' ? labels.user : labels.assistant
    lines.push(`**${speaker}**`, '', m.content, '')
  }
  return lines.join('\n')
}

export function downloadTextFile(filename: string, content: string) {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
