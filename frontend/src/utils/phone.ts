import { onBeforeUnmount, ref } from 'vue'

// Phone-sized screens (below tablet width). The admin AI settings are view-
// only there: long prompts and step settings are too easy to get wrong on a
// phone, so text editing is left to a tablet or computer.
const PHONE_QUERY = '(max-width: 767px)'

export function usePhone() {
  const mq = window.matchMedia(PHONE_QUERY)
  const phone = ref(mq.matches)
  const update = (e: MediaQueryListEvent) => (phone.value = e.matches)
  mq.addEventListener('change', update)
  onBeforeUnmount(() => mq.removeEventListener('change', update))
  return phone
}
