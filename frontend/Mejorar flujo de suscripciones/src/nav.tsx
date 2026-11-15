import { createContext, useContext } from 'react'
import type { SubStatus } from './data'

export type SubFilter = 'todos' | SubStatus

export type Route =
  | { name: 'home' }
  | { name: 'plans' }
  | { name: 'subscribers'; filter?: SubFilter }
  | { name: 'payments' }
  | { name: 'plan'; planId: string }
  | { name: 'planForm'; planId?: string }
  | { name: 'chargePlan' }
  | { name: 'chargeSub'; planId: string }
  | { name: 'summary'; subscriberId: string }
  | { name: 'result'; paymentId: string }
  | { name: 'newSub'; planId?: string; charge?: boolean }

export type Tab = 'home' | 'plans' | 'subscribers' | 'payments'

export type Nav = {
  route: Route
  go: (route: Route) => void
  replace: (route: Route) => void
  back: () => void
  tab: (route: Route) => void
  toast: (message: string) => void
}

export const NavContext = createContext<Nav | null>(null)

export function useNav() {
  const nav = useContext(NavContext)
  if (!nav) throw new Error('useNav fuera de NavContext')
  return nav
}
