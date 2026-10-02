import type { RouteLocationNormalizedLoaded } from 'vue-router'

/**
 * Where to go after signing in: the page the user was sent away from
 * (`?redirect=`), if it's a path inside this site — never an outside URL.
 */
export function redirectTarget(route: RouteLocationNormalizedLoaded): string {
  const r = route.query.redirect
  return typeof r === 'string' && r.startsWith('/') && !r.startsWith('//') ? r : '/'
}
