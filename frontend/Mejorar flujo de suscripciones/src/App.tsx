import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { NavContext, type Nav, type Route } from './nav'
import { ChargePlan, ChargeResult, ChargeSubscriber, ChargeSummary } from './screens/charge'
import { Home } from './screens/home'
import { Payments } from './screens/payments'
import { NewSubscriber, Subscribers } from './screens/people'
import { PlanDetail, PlanForm, Plans } from './screens/plans'
import { StoreProvider } from './store'

function Screen({ route }: { route: Route }) {
  switch (route.name) {
    case 'home':
      return <Home />
    case 'plans':
      return <Plans />
    case 'subscribers':
      return <Subscribers initialFilter={route.filter} />
    case 'payments':
      return <Payments />
    case 'plan':
      return <PlanDetail planId={route.planId} />
    case 'planForm':
      return <PlanForm planId={route.planId} />
    case 'chargePlan':
      return <ChargePlan />
    case 'chargeSub':
      return <ChargeSubscriber planId={route.planId} />
    case 'summary':
      return <ChargeSummary subscriberId={route.subscriberId} />
    case 'result':
      return <ChargeResult paymentId={route.paymentId} />
    case 'newSub':
      return <NewSubscriber planId={route.planId} charge={route.charge} />
  }
}

export default function App() {
  const [stack, setStack] = useState<Route[]>([{ name: 'home' }])
  const [toast, setToast] = useState<string | null>(null)
  const toastTimer = useRef<ReturnType<typeof setTimeout>>(undefined)
  const route = stack[stack.length - 1]

  const showToast = useCallback((message: string) => {
    clearTimeout(toastTimer.current)
    setToast(message)
    toastTimer.current = setTimeout(() => setToast(null), 2400)
  }, [])

  const nav = useMemo<Nav>(
    () => ({
      route,
      go: (r) => setStack((s) => [...s, r]),
      replace: (r) => setStack((s) => [...s.slice(0, -1), r]),
      back: () => setStack((s) => (s.length > 1 ? s.slice(0, -1) : s)),
      tab: (r) => setStack([r]),
      toast: showToast,
    }),
    [route, showToast],
  )

  useEffect(() => {
    window.scrollTo({ top: 0 })
  }, [stack.length, route])

  return (
    <StoreProvider>
      <NavContext.Provider value={nav}>
        <div className="min-h-dvh w-full bg-cream text-ink">
          <Screen key={`${stack.length}-${JSON.stringify(route)}`} route={route} />
        </div>
        <div
          role="status"
          aria-live="polite"
          className={`pointer-events-none fixed inset-x-0 top-4 z-50 flex justify-center px-4 transition-all duration-300 ${
            toast ? 'translate-y-0 opacity-100' : '-translate-y-4 opacity-0'
          }`}
        >
          {toast && <span className="rounded-full bg-ink px-4 py-2.5 text-[16px] font-bold text-cream shadow-lg">{toast}</span>}
        </div>
      </NavContext.Provider>
    </StoreProvider>
  )
}
