export type PlanIcon = 'gym' | 'yoga' | 'pilates' | 'wallet'

export type Plan = {
  id: string
  name: string
  price: number
  description: string
  icon: PlanIcon
  /** Día del mes en que se cobra. */
  chargeDay: number
  interval?: string
  isActive?: boolean
  created_at?: string
  active_subscribers?: number
  expected?: number
  collected?: number
  pending?: number
  late_count?: number
}

/** atrasado: venció sin pagar · por_vencer: vence este mes, aún sin pagar · al_corriente: ya pagó este mes */
export type SubStatus = 'atrasado' | 'por_vencer' | 'al_corriente'

export type Subscriber = {
  id: string
  name: string
  phone: string
  planId: string
  status: SubStatus
  /** Texto corto: "Venció 28 oct", "Vence 30 nov", "Pagó 1 nov" */
  note: string
  next_due_date?: string
  last_paid_at?: string | null
  start_date?: string
  plan_name?: string
  is_active?: boolean
  created_at?: string
}

export type PaymentStatus = 'pagado' | 'pendiente' | 'vencido' | 'fallido'
export type PaymentMethod = 'codi' | 'efectivo'

export type Payment = {
  id: string
  subscriberId: string
  planId: string
  amount: number
  status: PaymentStatus
  method: PaymentMethod
  when: string
  subscriber_name?: string
  plan_name?: string
  concept?: string
  codi_qr_id?: string | null
  qr_payload?: string | null
  qr_image?: string | null
  payment_link_id?: string | null
  payment_link_url?: string | null
  created_at?: string
  paid_at?: string | null
  subscriber_next_due_date?: string | null
  subscriber_status?: string | null
}

export const MONTH = 'Noviembre'

export const seedPlans: Plan[] = [
  {
    id: 'gym',
    name: 'Gym Fit',
    price: 350,
    description: 'Acceso a pesas, máquinas y área cardiovascular.',
    icon: 'gym',
    chargeDay: 28,
  },
  {
    id: 'yoga',
    name: 'Yoga',
    price: 250,
    description: 'Clases matutinas y vespertinas.',
    icon: 'yoga',
    chargeDay: 30,
  },
  {
    id: 'pilates',
    name: 'Pilates',
    price: 400,
    description: 'Sesiones grupales con reformador.',
    icon: 'pilates',
    chargeDay: 5,
  },
]

const s = (id: string, name: string, phone: string, planId: string, status: SubStatus, note: string): Subscriber => ({
  id,
  name,
  phone,
  planId,
  status,
  note,
})

export const seedSubscribers: Subscriber[] = [
  s('roberto', 'Roberto Gómez', '5512348912', 'gym', 'atrasado', 'Venció 28 oct'),
  s('luis', 'Luis Morales', '5598762231', 'gym', 'atrasado', 'Venció 2 nov'),
  s('mariana', 'Mariana Ortiz', '5523454410', 'gym', 'por_vencer', 'Vence 30 nov'),
  s('carlos', 'Carlos Mendoza', '5534561234', 'gym', 'al_corriente', 'Pagó 1 nov'),
  s('sofia', 'Sofía Castro', '5545677721', 'gym', 'al_corriente', 'Pagó 3 nov'),
  s('jorge', 'Jorge Ramírez', '5556783390', 'gym', 'al_corriente', 'Pagó 4 nov'),
  s('fernanda', 'Fernanda López', '5567891045', 'gym', 'al_corriente', 'Pagó 5 nov'),
  s('diego', 'Diego Herrera', '5578902276', 'gym', 'al_corriente', 'Pagó 6 nov'),
  s('ana', 'Ana Torres', '5587013318', 'yoga', 'atrasado', 'Venció 30 oct'),
  s('lucia', 'Lucía Vega', '5590124467', 'yoga', 'al_corriente', 'Pagó 2 nov'),
  s('paula', 'Paula Núñez', '5501235589', 'yoga', 'al_corriente', 'Pagó 3 nov'),
  s('elena', 'Elena Cruz', '5512346602', 'yoga', 'al_corriente', 'Pagó 5 nov'),
  s('daniela', 'Daniela Soto', '5523457734', 'yoga', 'al_corriente', 'Pagó 7 nov'),
  s('valeria', 'Valeria Rivas', '5534568815', 'pilates', 'al_corriente', 'Pagó 5 nov'),
  s('camila', 'Camila Reyes', '5545679927', 'pilates', 'al_corriente', 'Pagó 5 nov'),
]

export const seedPayments: Payment[] = [
  { id: 'p4', subscriberId: 'carlos', planId: 'gym', amount: 350, status: 'pagado', method: 'codi', when: 'Hoy, 10:45 AM' },
  { id: 'p3', subscriberId: 'mariana', planId: 'gym', amount: 350, status: 'pendiente', method: 'codi', when: 'Ayer, 4:20 PM' },
  { id: 'p2', subscriberId: 'roberto', planId: 'gym', amount: 350, status: 'vencido', method: 'codi', when: '28 oct' },
  { id: 'p1', subscriberId: 'valeria', planId: 'pilates', amount: 400, status: 'fallido', method: 'codi', when: '27 oct' },
]

export const money = (n: number) => {
  if (typeof n !== 'number' || isNaN(n)) return '$0'
  return `$${n.toLocaleString('es-MX', {
    minimumFractionDigits: Number.isInteger(n) ? 0 : 2,
    maximumFractionDigits: 2,
  })}`
}

export const initials = (name: string) =>
  name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase())
    .join('')

export const maskPhone = (phone: string) => `+52 ${phone.slice(0, 2)} •••• ${phone.slice(-4)}`

export const statusLabel: Record<SubStatus, string> = {
  atrasado: 'Atrasado',
  por_vencer: 'Por vencer',
  al_corriente: 'Al corriente',
}

export const paymentLabel: Record<PaymentStatus, string> = {
  pagado: 'Pagado',
  pendiente: 'Pendiente',
  vencido: 'Vencido',
  fallido: 'Fallido',
}

export const nowLabel = () => {
  const d = new Date()
  return `Hoy, ${d.toLocaleTimeString('es-MX', { hour: 'numeric', minute: '2-digit' })}`
}
