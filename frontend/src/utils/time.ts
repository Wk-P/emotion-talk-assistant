// Every time on the site is shown in Korea time (UTC+9), whatever the
// viewer's own time zone — participants and the research team are in Korea.
//
// The backend stores UTC and sends some times without a zone suffix
// ("2026-10-02T09:47:50"); `new Date()` would read those as the viewer's
// local time, so they are parsed as UTC here.

export const DISPLAY_TIME_ZONE = 'Asia/Seoul'
/** As JS getTimezoneOffset() would give for UTC+9 ("UTC minus local"). */
export const DISPLAY_TZ_OFFSET = -540

export function toDate(value: string | Date): Date {
  if (value instanceof Date) return value
  const hasZone = /(Z|[+-]\d{2}:?\d{2})$/.test(value)
  return new Date(hasZone || !value.includes('T') ? value : `${value}Z`)
}

export function formatDateTime(value: string | Date): string {
  return toDate(value).toLocaleString(undefined, { timeZone: DISPLAY_TIME_ZONE })
}

export function formatDate(value: string | Date): string {
  return toDate(value).toLocaleDateString(undefined, { timeZone: DISPLAY_TIME_ZONE })
}

/** YYYY-MM-DD of the given moment in Korea time. */
export function displayDay(value: string | Date = new Date()): string {
  return toDate(value).toLocaleDateString('en-CA', { timeZone: DISPLAY_TIME_ZONE })
}

/** The instant a Korea-time day (YYYY-MM-DD) starts, `addDays` later, as ISO. */
export function displayDayStart(day: string, addDays = 0): string {
  const [y, m, d] = day.split('-').map(Number)
  return new Date(Date.UTC(y!, m! - 1, d! + addDays) + DISPLAY_TZ_OFFSET * 60_000).toISOString()
}
