import type { Payment, PaymentMethod, PaymentStatus, Plan, PlanIcon, SubStatus, Subscriber } from './data'

export interface ApiDashboard {
  total_subscribers: number
  active_subscribers: number
  overdue_count: number
  due_soon_count: number
  current_count: number
  expected_monthly: number
  collected_month: number
  recent_movements: ApiCharge[]
}

export interface ApiPlan {
  id: string
  name: string
  price: number
  interval?: string
  description?: string | null
  icon: string
  charge_day?: number
  chargeDay?: number
  is_active?: boolean
  created_at?: string
  active_subscribers?: number
  expected?: number
  collected?: number
  pending?: number
  late_count?: number
}

export interface ApiSubscriber {
  id: string
  name: string
  phone: string
  plan_id?: string
  planId?: string
  start_date?: string
  next_due_date?: string
  last_paid_at?: string | null
  note?: string | null
  is_active?: boolean
  created_at?: string
  status: string
  plan_name?: string | null
}

export interface ApiCharge {
  id: string
  subscriber_id?: string
  subscriberId?: string
  subscriber_name?: string | null
  plan_id?: string
  planId?: string
  plan_name?: string | null
  amount: number
  concept?: string | null
  method: string
  status: string
  codi_qr_id?: string | null
  qr_payload?: string | null
  qr_image?: string | null
  payment_link_id?: string | null
  payment_link_url?: string | null
  pey_transaction_id?: string | null
  num_ref?: string | null
  created_at: string
  paid_at?: string | null
  when?: string | null
  subscriber_next_due_date?: string | null
  subscriber_status?: string | null
  pagado?: boolean
}

export interface ApiHealth {
  status: string
  database: string
  pey_api: string
}

export function normalizeSubStatus(status?: string): SubStatus {
  if (!status) return 'al_corriente'
  const s = status.toLowerCase()
  if (s === 'atrasado' || s === 'overdue') return 'atrasado'
  if (s === 'por_vencer' || s === 'due_soon') return 'por_vencer'
  return 'al_corriente'
}

export function normalizePaymentStatus(status?: string): PaymentStatus {
  if (!status) return 'pendiente'
  const s = status.toLowerCase()
  if (s === 'paid' || s === 'pagado') return 'pagado'
  if (s === 'pending' || s === 'pendiente') return 'pendiente'
  if (s === 'expired' || s === 'vencido') return 'vencido'
  if (s === 'failed' || s === 'fallido') return 'fallido'
  return 'pendiente'
}

export function normalizePaymentMethod(method?: string): PaymentMethod {
  if (!method) return 'codi'
  const m = method.toLowerCase()
  if (m === 'cash' || m === 'efectivo') return 'efectivo'
  return 'codi'
}

export function mapPlanFromApi(p: ApiPlan): Plan {
  const validIcons: PlanIcon[] = ['gym', 'yoga', 'pilates', 'wallet']
  const icon = validIcons.includes(p.icon as PlanIcon) ? (p.icon as PlanIcon) : 'wallet'
  return {
    id: p.id,
    name: p.name,
    price: Number(p.price),
    description: p.description || '',
    icon,
    chargeDay: p.chargeDay ?? p.charge_day ?? 1,
    interval: p.interval || 'monthly',
    isActive: p.is_active ?? true,
    created_at: p.created_at,
    active_subscribers: p.active_subscribers,
    expected: p.expected,
    collected: p.collected,
    pending: p.pending,
    late_count: p.late_count,
  }
}

export function mapSubscriberFromApi(s: ApiSubscriber): Subscriber {
  return {
    id: s.id,
    name: s.name,
    phone: s.phone,
    planId: s.planId || s.plan_id || '',
    status: normalizeSubStatus(s.status),
    note: s.note || '',
    next_due_date: s.next_due_date,
    last_paid_at: s.last_paid_at,
    start_date: s.start_date,
    plan_name: s.plan_name || undefined,
    is_active: s.is_active ?? true,
    created_at: s.created_at,
  }
}

export function mapPaymentFromApi(c: ApiCharge): Payment {
  return {
    id: c.id,
    subscriberId: c.subscriberId || c.subscriber_id || '',
    planId: c.planId || c.plan_id || '',
    amount: Number(c.amount),
    status: normalizePaymentStatus(c.status),
    method: normalizePaymentMethod(c.method),
    when: c.when || '',
    subscriber_name: c.subscriber_name || undefined,
    plan_name: c.plan_name || undefined,
    concept: c.concept || undefined,
    codi_qr_id: c.codi_qr_id,
    qr_payload: c.qr_payload,
    qr_image: c.qr_image,
    payment_link_id: c.payment_link_id,
    payment_link_url: c.payment_link_url,
    created_at: c.created_at,
    paid_at: c.paid_at,
    subscriber_next_due_date: c.subscriber_next_due_date,
    subscriber_status: c.subscriber_status,
  }
}

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`
  const headers = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
    ...(options.headers || {}),
  }
  const res = await fetch(url, { ...options, headers })
  if (!res.ok) {
    let errorDetail = `HTTP ${res.status} ${res.statusText}`
    try {
      const errJson = await res.json()
      if (errJson?.detail) {
        errorDetail = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail)
      }
    } catch {
      // ignore
    }
    throw new Error(errorDetail)
  }
  return res.json()
}

export const api = {
  async getDashboard(): Promise<ApiDashboard> {
    return request<ApiDashboard>('/api/dashboard')
  },

  async getPlans(): Promise<Plan[]> {
    const list = await request<ApiPlan[]>('/api/plans')
    return list.map(mapPlanFromApi)
  },

  async createPlan(plan: Partial<Plan>): Promise<Plan> {
    const payload = {
      id: plan.id,
      name: plan.name,
      price: plan.price,
      interval: plan.interval || 'monthly',
      description: plan.description,
      icon: plan.icon || 'wallet',
      charge_day: plan.chargeDay ?? 1,
      chargeDay: plan.chargeDay ?? 1,
      is_active: plan.isActive ?? true,
    }
    const res = await request<ApiPlan>('/api/plans', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
    return mapPlanFromApi(res)
  },

  async getSubscribers(params?: { status?: string; plan_id?: string; search?: string }): Promise<Subscriber[]> {
    const query = new URLSearchParams()
    if (params?.status) query.set('status', params.status)
    if (params?.plan_id) query.set('plan_id', params.plan_id)
    if (params?.search) query.set('search', params.search)
    const qs = query.toString() ? `?${query.toString()}` : ''
    const list = await request<ApiSubscriber[]>(`/api/subscribers${qs}`)
    return list.map(mapSubscriberFromApi)
  },

  async getSubscriber(id: string): Promise<Subscriber> {
    const res = await request<ApiSubscriber>(`/api/subscribers/${id}`)
    return mapSubscriberFromApi(res)
  },

  async createSubscriber(sub: {
    id?: string
    name: string
    phone: string
    plan_id: string
    start_date?: string
    next_due_date?: string
    note?: string
    instant_charge?: boolean
  }): Promise<Subscriber> {
    const payload = {
      ...sub,
      planId: sub.plan_id,
    }
    const res = await request<ApiSubscriber>('/api/subscribers', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
    return mapSubscriberFromApi(res)
  },

  async getCharges(): Promise<Payment[]> {
    const list = await request<ApiCharge[]>('/api/charges')
    return list.map(mapPaymentFromApi)
  },

  async getCharge(id: string): Promise<Payment> {
    const res = await request<ApiCharge>(`/api/charges/${id}`)
    return mapPaymentFromApi(res)
  },

  async createCharge(charge: {
    subscriber_id: string
    plan_id?: string
    amount?: number
    concept?: string
    method?: string
  }): Promise<Payment> {
    const payload = {
      subscriber_id: charge.subscriber_id,
      subscriberId: charge.subscriber_id,
      plan_id: charge.plan_id,
      planId: charge.plan_id,
      amount: charge.amount,
      concept: charge.concept,
      method: charge.method || 'codi',
    }
    const res = await request<ApiCharge>('/api/charges', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
    return mapPaymentFromApi(res)
  },

  async getChargeStatus(id: string): Promise<Payment> {
    const res = await request<ApiCharge>(`/api/charges/${id}/status`)
    return mapPaymentFromApi(res)
  },

  async markCashPayment(id: string): Promise<Payment> {
    const res = await request<ApiCharge>(`/api/charges/${id}/mark-cash`, {
      method: 'POST',
    })
    return mapPaymentFromApi(res)
  },

  async getHealth(): Promise<ApiHealth> {
    return request<ApiHealth>('/api/health')
  },
}
