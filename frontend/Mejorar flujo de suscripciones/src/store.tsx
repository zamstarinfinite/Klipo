import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, type ReactNode } from 'react'
import {
  api,
  type ApiDashboard,
} from './api'
import {
  nowLabel,
  seedPayments,
  seedPlans,
  seedSubscribers,
  type Payment,
  type PaymentMethod,
  type Plan,
  type SubStatus,
  type Subscriber,
} from './data'

export type PlanStats = {
  plan: Plan
  subs: Subscriber[]
  expected: number
  collected: number
  pending: number
  late: number
}

type State = {
  plans: Plan[]
  subscribers: Subscriber[]
  payments: Payment[]
  dashboardMetrics: ApiDashboard | null
  loading: boolean
  error: string | null
}

type Action =
  | { type: 'setLoading'; loading: boolean }
  | { type: 'setError'; error: string | null }
  | {
      type: 'setInitialData'
      plans: Plan[]
      subscribers: Subscriber[]
      payments: Payment[]
      metrics?: ApiDashboard | null
    }
  | { type: 'setPlans'; plans: Plan[] }
  | { type: 'setSubscribers'; subscribers: Subscriber[] }
  | { type: 'setPayments'; payments: Payment[] }
  | { type: 'savePlan'; plan: Plan }
  | { type: 'addSubscriber'; subscriber: Subscriber }
  | { type: 'replaceSubscriber'; tempId: string; subscriber: Subscriber }
  | { type: 'addPayment'; payment: Payment }
  | { type: 'updatePayment'; payment: Payment }
  | { type: 'confirmPayment'; paymentId: string }
  | { type: 'payCash'; payment: Payment }
  | { type: 'markSubscriberPaid'; subscriberId: string }

const markSubscriberPaidHelper = (subs: Subscriber[], id: string): Subscriber[] =>
  subs.map((s) => (s.id === id ? { ...s, status: 'al_corriente' as const, note: 'Pagó hoy' } : s))

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'setLoading':
      return { ...state, loading: action.loading }

    case 'setError':
      return { ...state, error: action.error }

    case 'setInitialData':
      return {
        ...state,
        plans: action.plans.length > 0 ? action.plans : state.plans,
        subscribers: action.subscribers.length > 0 ? action.subscribers : state.subscribers,
        payments: action.payments.length > 0 ? action.payments : state.payments,
        dashboardMetrics: action.metrics ?? state.dashboardMetrics,
        loading: false,
        error: null,
      }

    case 'setPlans':
      return { ...state, plans: action.plans }

    case 'setSubscribers':
      return { ...state, subscribers: action.subscribers }

    case 'setPayments':
      return { ...state, payments: action.payments }

    case 'savePlan': {
      const exists = state.plans.some((p) => p.id === action.plan.id)
      return {
        ...state,
        plans: exists ? state.plans.map((p) => (p.id === action.plan.id ? action.plan : p)) : [...state.plans, action.plan],
      }
    }

    case 'addSubscriber':
      return { ...state, subscribers: [action.subscriber, ...state.subscribers.filter((s) => s.id !== action.subscriber.id)] }

    case 'replaceSubscriber':
      return {
        ...state,
        subscribers: state.subscribers.map((s) => (s.id === action.tempId ? action.subscriber : s)),
      }

    case 'addPayment':
      return {
        ...state,
        payments: [action.payment, ...state.payments.filter((p) => p.id !== action.payment.id)],
      }

    case 'updatePayment':
      return {
        ...state,
        payments: state.payments.some((p) => p.id === action.payment.id)
          ? state.payments.map((p) => (p.id === action.payment.id ? action.payment : p))
          : [action.payment, ...state.payments],
      }

    case 'confirmPayment': {
      const payment = state.payments.find((p) => p.id === action.paymentId)
      if (!payment || payment.status === 'pagado') return state
      return {
        ...state,
        payments: state.payments.map((p) =>
          p.id === action.paymentId ? { ...p, status: 'pagado', when: nowLabel() } : p,
        ),
        subscribers: markSubscriberPaidHelper(state.subscribers, payment.subscriberId),
      }
    }

    case 'payCash':
      return {
        ...state,
        payments: [action.payment, ...state.payments.filter((p) => p.id !== action.payment.id)],
        subscribers: markSubscriberPaidHelper(state.subscribers, action.payment.subscriberId),
      }

    case 'markSubscriberPaid':
      return {
        ...state,
        subscribers: markSubscriberPaidHelper(state.subscribers, action.subscriberId),
      }

    default:
      return state
  }
}

function useStoreValue() {
  const [state, dispatch] = useReducer(reducer, {
    plans: seedPlans,
    subscribers: seedSubscribers,
    payments: seedPayments,
    dashboardMetrics: null,
    loading: true,
    error: null,
  })

  // Full refresh from backend
  const refreshAll = useCallback(async () => {
    try {
      const [plansRes, subsRes, chargesRes, dashRes] = await Promise.allSettled([
        api.getPlans(),
        api.getSubscribers(),
        api.getCharges(),
        api.getDashboard(),
      ])

      const plans = plansRes.status === 'fulfilled' ? plansRes.value : []
      const subscribers = subsRes.status === 'fulfilled' ? subsRes.value : []
      const payments = chargesRes.status === 'fulfilled' ? chargesRes.value : []
      const metrics = dashRes.status === 'fulfilled' ? dashRes.value : null

      if (plans.length > 0 || subscribers.length > 0 || payments.length > 0 || metrics) {
        dispatch({
          type: 'setInitialData',
          plans,
          subscribers,
          payments,
          metrics,
        })
      } else {
        dispatch({ type: 'setLoading', loading: false })
      }
    } catch (err: any) {
      console.warn('Backend sync failed, falling back to local state:', err)
      dispatch({ type: 'setError', error: err?.message || 'Sync error' })
      dispatch({ type: 'setLoading', loading: false })
    }
  }, [])

  // Initial fetch on startup
  useEffect(() => {
    refreshAll()
  }, [refreshAll])

  const derived = useMemo(() => {
    const planStats: PlanStats[] = state.plans.map((plan) => {
      const subs = state.subscribers.filter((s) => s.planId === plan.id)
      const paid = subs.filter((s) => s.status === 'al_corriente').length
      const lateSubs = subs.filter((s) => s.status === 'atrasado')
      const expected = plan.expected ?? (subs.length * plan.price)
      const collected = plan.collected ?? (paid * plan.price)
      const pending = plan.pending ?? Math.max(0, expected - collected)
      const late = plan.late_count ?? lateSubs.length
      return {
        plan,
        subs,
        expected,
        collected,
        pending,
        late,
      }
    })

    const lateSubs = state.subscribers.filter((s) => s.status === 'atrasado')
    const lateAmount = lateSubs.reduce((a, s) => {
      const p = state.plans.find((pl) => pl.id === s.planId)
      return a + (p?.price ?? 0)
    }, 0)
    const paidCount = state.subscribers.filter((s) => s.status === 'al_corriente').length

    const expected = state.dashboardMetrics?.expected_monthly ?? planStats.reduce((a, p) => a + p.expected, 0)
    const collected = state.dashboardMetrics?.collected_month ?? planStats.reduce((a, p) => a + p.collected, 0)
    const pending = Math.max(0, expected - collected)

    return { planStats, expected, collected, pending, lateSubs, lateAmount, paidCount }
  }, [state])

  const savePlan = useCallback(
    async (plan: Plan) => {
      // Optimistic update
      dispatch({ type: 'savePlan', plan })
      try {
        const saved = await api.createPlan(plan)
        dispatch({ type: 'savePlan', plan: saved })
        // Refresh plans & dashboard
        api.getPlans().then((plans) => dispatch({ type: 'setPlans', plans })).catch(() => {})
        return saved
      } catch (err) {
        console.error('Error saving plan to backend:', err)
        return plan
      }
    },
    [],
  )

  const addSubscriber = useCallback(
    async (subscriberData: {
      id?: string
      name: string
      phone: string
      planId: string
      status?: SubStatus
      note?: string
      instant_charge?: boolean
    }) => {
      const tempId = subscriberData.id || `sub-${Date.now()}`
      const tempSub: Subscriber = {
        id: tempId,
        name: subscriberData.name,
        phone: subscriberData.phone,
        planId: subscriberData.planId,
        status: subscriberData.status || 'por_vencer',
        note: subscriberData.note || 'Nuevo · sin cobrar',
      }
      // Optimistic update
      dispatch({ type: 'addSubscriber', subscriber: tempSub })

      try {
        const created = await api.createSubscriber({
          id: subscriberData.id,
          name: subscriberData.name,
          phone: subscriberData.phone,
          plan_id: subscriberData.planId,
          note: subscriberData.note,
          instant_charge: subscriberData.instant_charge,
        })
        dispatch({ type: 'replaceSubscriber', tempId, subscriber: created })
        if (subscriberData.instant_charge) {
          api.getCharges().then((payments) => dispatch({ type: 'setPayments', payments })).catch(() => {})
        }
        return created
      } catch (err) {
        console.error('Error creating subscriber in backend:', err)
        return tempSub
      }
    },
    [],
  )

  const startPayment = useCallback(
    async (subscriberId: string, method: PaymentMethod): Promise<Payment | null> => {
      const sub = state.subscribers.find((s) => s.id === subscriberId)
      const plan = sub && state.plans.find((p) => p.id === sub.planId)
      if (!sub || !plan) return null

      try {
        const liveCharge = await api.createCharge({
          subscriber_id: subscriberId,
          plan_id: plan.id,
          amount: plan.price,
          method,
        })
        dispatch({ type: 'addPayment', payment: liveCharge })
        if (method === 'efectivo' || liveCharge.status === 'pagado') {
          dispatch({ type: 'markSubscriberPaid', subscriberId })
          refreshAll().catch(() => {})
        }
        return liveCharge
      } catch (err) {
        console.error('Error calling POST /api/charges, falling back to local payment:', err)
        const fallbackPayment: Payment = {
          id: `p${Date.now()}`,
          subscriberId,
          planId: plan.id,
          amount: plan.price,
          method,
          status: method === 'efectivo' ? 'pagado' : 'pendiente',
          when: nowLabel(),
        }
        dispatch(method === 'efectivo' ? { type: 'payCash', payment: fallbackPayment } : { type: 'addPayment', payment: fallbackPayment })
        return fallbackPayment
      }
    },
    [state.subscribers, state.plans, refreshAll],
  )

  const pollPaymentStatus = useCallback(
    async (paymentId: string): Promise<Payment | null> => {
      try {
        const statusResp = await api.getChargeStatus(paymentId)
        dispatch({ type: 'updatePayment', payment: statusResp })
        if (statusResp.status === 'pagado') {
          dispatch({ type: 'markSubscriberPaid', subscriberId: statusResp.subscriberId })
          // Refresh background lists
          api.getSubscribers().then((subscribers) => dispatch({ type: 'setSubscribers', subscribers })).catch(() => {})
          api.getDashboard().then((metrics) => dispatch({ type: 'setInitialData', plans: state.plans, subscribers: state.subscribers, payments: state.payments, metrics })).catch(() => {})
        }
        return statusResp
      } catch (err) {
        console.error('Error polling charge status:', err)
        return null
      }
    },
    [state.plans, state.subscribers, state.payments],
  )

  const markCash = useCallback(
    async (paymentId: string): Promise<Payment | null> => {
      try {
        const updated = await api.markCashPayment(paymentId)
        dispatch({ type: 'updatePayment', payment: updated })
        dispatch({ type: 'markSubscriberPaid', subscriberId: updated.subscriberId })
        refreshAll().catch(() => {})
        return updated
      } catch (err) {
        console.error('Error marking cash payment:', err)
        // Fallback local confirm
        dispatch({ type: 'confirmPayment', paymentId })
        return null
      }
    },
    [refreshAll],
  )

  const confirmPayment = useCallback(
    (paymentId: string) => dispatch({ type: 'confirmPayment', paymentId }),
    [],
  )

  const apiMethods = useMemo(
    () => ({
      plan: (id: string) => state.plans.find((p) => p.id === id),
      subscriber: (id: string) => state.subscribers.find((s) => s.id === id),
      payment: (id: string) => state.payments.find((p) => p.id === id),
      charge: (id: string) => state.payments.find((p) => p.id === id),
      savePlan,
      addSubscriber,
      startPayment,
      pollPaymentStatus,
      markCash,
      confirmPayment,
      refreshAll,
    }),
    [state.plans, state.subscribers, state.payments, savePlan, addSubscriber, startPayment, pollPaymentStatus, markCash, confirmPayment, refreshAll],
  )

  return { ...state, ...derived, ...apiMethods }
}

type Store = ReturnType<typeof useStoreValue>
const StoreContext = createContext<Store | null>(null)

export function StoreProvider({ children }: { children: ReactNode }) {
  const value = useStoreValue()
  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>
}

export function useStore() {
  const store = useContext(StoreContext)
  if (!store) throw new Error('useStore fuera de StoreProvider')
  return store
}
