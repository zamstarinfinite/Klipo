import type { ReactNode } from 'react'
import { money, type Payment, type Subscriber } from './data'
import { useNav } from './nav'
import { useStore } from './store'
import { Avatar, Button, Icon, PaymentBadge, StatusBadge } from './ui'

export function PaymentRow({ payment }: { payment: Payment }) {
  const store = useStore()
  const nav = useNav()
  const sub = store.subscriber(payment.subscriberId)
  const plan = store.plan(payment.planId)
  const resumable = payment.status === 'pendiente'
  const subName = sub?.name || payment.subscriber_name || 'Suscriptor'
  const planName = plan?.name || payment.plan_name || 'Suscripción'
  const content = (
    <>
      <div className="min-w-0 flex-1">
        <p className="truncate text-[16px] font-bold">{subName}</p>
        <p className="text-[16px] text-ink/60">
          {planName} · {payment.when}
          {payment.method === 'efectivo' && ' · Efectivo'}
        </p>
      </div>
      <div className="flex flex-col items-end gap-1">
        <p className={`text-[16px] font-bold ${payment.status === 'pagado' ? 'text-leaf' : ''}`}>
          {payment.status === 'pagado' ? '+' : ''}
          {money(payment.amount)}
        </p>
        <PaymentBadge status={payment.status} />
      </div>
    </>
  )
  return resumable ? (
    <button
      type="button"
      onClick={() => nav.go({ name: 'result', paymentId: payment.id })}
      className="flex w-full items-center gap-3 py-3.5 text-left"
    >
      {content}
    </button>
  ) : (
    <div className="flex items-center gap-3 py-3.5">{content}</div>
  )
}

export function SubscriberRow({ sub, showPlan = false }: { sub: Subscriber; showPlan?: boolean }) {
  const store = useStore()
  const nav = useNav()
  const plan = store.plan(sub.planId)
  const paid = sub.status === 'al_corriente'
  return (
    <div className="flex items-center gap-3 py-3.5">
      <Avatar name={sub.name} status={sub.status} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-[16px] font-bold">{sub.name}</p>
        <p className="text-[16px] text-ink/60">
          {showPlan && plan ? `${plan.name} · ` : ''}
          {sub.note}
        </p>
        {!paid && (
          <div className="mt-1">
            <StatusBadge status={sub.status} />
          </div>
        )}
      </div>
      {paid ? (
        <span className="flex items-center gap-1 text-[16px] font-bold text-leaf">
          <Icon name="check" size={12} />
          Al día
        </span>
      ) : (
        <Button
          size="sm"
          variant={sub.status === 'atrasado' ? 'charge' : 'outline'}
          onClick={() => nav.go({ name: 'summary', subscriberId: sub.id })}
        >
          Cobrar {plan && money(plan.price)}
        </Button>
      )}
    </div>
  )
}

export function Divided({ children }: { children: ReactNode }) {
  return <div className="divide-y divide-sand/80 px-4">{children}</div>
}
