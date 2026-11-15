import { useEffect, useState } from 'react'
import { MONTH, maskPhone, money } from '../data'
import { useNav } from '../nav'
import { useStore } from '../store'
import { Avatar, BottomAction, Button, Card, Icon, Page, PlanTile, SearchField, StatusBadge, TopBar, qrImage } from '../ui'
import { Radio } from './people'

export function ChargePlan() {
  const store = useStore()
  const nav = useNav()
  const [selected, setSelected] = useState(store.plans[0]?.id ?? '')

  return (
    <>
      <TopBar step="Paso 1 de 3" title="Elige el plan" />
      <Page className="pt-3 pb-32">
        <div className="flex flex-col gap-2.5" role="radiogroup" aria-label="Plan">
          {store.planStats.map(({ plan, subs, late }) => {
            const on = plan.id === selected
            return (
              <button
                key={plan.id}
                type="button"
                role="radio"
                aria-checked={on}
                onClick={() => setSelected(plan.id)}
                className={`flex items-center gap-4 rounded-3xl p-4 text-left ring-[1.5px] transition-colors ${
                  on ? 'bg-petrol-50 ring-petrol' : 'bg-paper ring-sand hover:ring-petrol/30'
                }`}
              >
                <PlanTile icon={plan.icon} size={52} />
                <div className="min-w-0 flex-1">
                  <p className="text-[18px] font-bold">{plan.name}</p>
                  <p className="text-[16px] text-ink/65">
                    <b className="text-ink">{money(plan.price)}</b> / mes · {subs.length} suscriptores
                  </p>
                  {late > 0 && <p className="mt-0.5 text-[16px] font-bold text-honey-700">{late} con pago atrasado</p>}
                </div>
                <Radio on={on} />
              </button>
            )
          })}
        </div>
      </Page>
      <BottomAction>
        <Button disabled={!selected} trailing="arrow" onClick={() => nav.go({ name: 'chargeSub', planId: selected })}>
          Continuar
        </Button>
      </BottomAction>
    </>
  )
}

const order = { atrasado: 0, por_vencer: 1, al_corriente: 2 }

export function ChargeSubscriber({ planId }: { planId: string }) {
  const store = useStore()
  const nav = useNav()
  const plan = store.plan(planId)
  const subs = store.subscribers.filter((s) => s.planId === planId).sort((a, b) => order[a.status] - order[b.status])
  const [selected, setSelected] = useState(subs.find((s) => s.status !== 'al_corriente')?.id ?? '')
  const [q, setQ] = useState('')
  const list = subs.filter((s) => s.name.toLowerCase().includes(q.trim().toLowerCase()))
  if (!plan) return null

  return (
    <>
      <TopBar step={`Paso 2 de 3 · ${plan.name}`} title="¿A quién le cobras?" />
      <Page className="pt-3 pb-32">
        <SearchField value={q} onChange={setQ} placeholder="Buscar suscriptor" />
        <div className="mt-3 flex flex-col gap-2" role="radiogroup" aria-label="Suscriptor">
          {list.map((s, i) => {
            const on = s.id === selected
            const firstPaid = s.status === 'al_corriente' && list[i - 1]?.status !== 'al_corriente'
            return (
              <div key={s.id} className="contents">
              {firstPaid && <p className="mt-4 mb-1 px-1 text-[16px] font-bold text-ink/55">Ya pagaron este mes</p>}
              <button
                type="button"
                role="radio"
                aria-checked={on}
                onClick={() => setSelected(s.id)}
                className={`flex items-center gap-3 rounded-2xl p-3.5 text-left ring-[1.5px] transition-colors ${
                  on ? 'bg-petrol-50 ring-petrol' : 'bg-paper ring-sand hover:ring-petrol/30'
                }`}
              >
                <Avatar name={s.name} status={s.status} />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <p className="text-[16px] font-bold">{s.name}</p>
                    {s.status !== 'al_corriente' && <StatusBadge status={s.status} />}
                  </div>
                  <p className="text-[16px] text-ink/60">{s.note}</p>
                </div>
                <Radio on={on} />
              </button>
              </div>
            )
          })}
          {list.length === 0 && <p className="py-8 text-center text-[16px] text-ink/60">Nadie con ese nombre.</p>}
          <button
            type="button"
            onClick={() => nav.go({ name: 'newSub', planId, charge: true })}
            className="flex items-center justify-center gap-2 rounded-2xl border-[1.5px] border-dashed border-petrol/35 py-4 text-[16px] font-bold text-petrol hover:bg-petrol-50"
          >
            <Icon name="userPlus" size={18} />
            Nuevo suscriptor
          </button>
        </div>
      </Page>
      <BottomAction>
        <Button disabled={!selected} trailing="arrow" onClick={() => nav.go({ name: 'summary', subscriberId: selected })}>
          Continuar
        </Button>
      </BottomAction>
    </>
  )
}

export function ChargeSummary({ subscriberId }: { subscriberId: string }) {
  const store = useStore()
  const nav = useNav()
  const sub = store.subscriber(subscriberId)
  const plan = sub && store.plan(sub.planId)
  const [isSubmitting, setIsSubmitting] = useState(false)
  if (!sub || !plan) return null

  const start = async (method: 'codi' | 'efectivo') => {
    if (isSubmitting) return
    setIsSubmitting(true)
    try {
      const charge = await store.startPayment(sub.id, method)
      if (charge) {
        nav.replace({ name: 'result', paymentId: charge.id })
      }
    } catch (err: any) {
      nav.toast(err?.message || 'Error al iniciar cobro')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <>
      <TopBar step="Paso 3 de 3" title="Confirma el cobro" />
      <Page className="pt-3 pb-48">
        <Card className="overflow-hidden">
          <div className="flex items-center gap-3.5 p-5">
            <Avatar name={sub.name} size={52} />
            <div className="min-w-0 flex-1">
              <p className="text-[19px] font-bold">{sub.name}</p>
              <p className="text-[16px] text-ink/60">{maskPhone(sub.phone)}</p>
              {sub.status !== 'al_corriente' && (
                <div className="mt-1.5">
                  <StatusBadge status={sub.status} />
                </div>
              )}
            </div>
          </div>
          <dl className="mx-5 border-t border-dashed border-sand py-3 text-[16px]">
            <Row label="Plan" value={`${plan.name} · Mensual`} />
            <Row label="Periodo" value={sub.status === 'atrasado' ? `${sub.note.replace('Venció', 'Desde el')}` : MONTH} />
          </dl>
          <div className="flex items-end justify-between bg-sand-100/70 px-5 py-5">
            <p className="pb-1 text-[16px] font-bold">Total</p>
            <p className="flex items-baseline gap-1.5">
              <span className="text-[44px] leading-none font-extrabold tracking-[-0.03em]">{money(plan.price)}</span>
              <span className="text-[16px] text-ink/60">MXN</span>
            </p>
          </div>
        </Card>
        <p className="mt-4 flex items-center justify-center gap-2 text-[16px] text-ink/60">
          <Icon name="shield" size={14} className="text-leaf" />
          Sin comisiones. El dinero llega directo a tu cuenta.
        </p>
      </Page>
      <BottomAction>
        <Button variant="charge" icon="qr" disabled={isSubmitting} onClick={() => start('codi')}>
          {isSubmitting ? 'Generando...' : 'Generar QR CoDi'}
        </Button>
        <Button variant="soft" icon="cash" disabled={isSubmitting} onClick={() => start('efectivo')}>
          Me pagó en efectivo
        </Button>
      </BottomAction>
    </>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4 py-1.5">
      <dt className="text-ink/60">{label}</dt>
      <dd className="text-right font-bold">{value}</dd>
    </div>
  )
}

export function ChargeResult({ paymentId }: { paymentId: string }) {
  const store = useStore()
  const nav = useNav()
  const payment = store.payment(paymentId)
  const sub = payment && store.subscriber(payment.subscriberId)
  const plan = payment && store.plan(payment.planId)
  const waiting = payment?.status === 'pendiente'
  const { pollPaymentStatus, markCash } = store
  const [isMarkingCash, setIsMarkingCash] = useState(false)

  // Live Polling every ~3 seconds for pending charges
  useEffect(() => {
    if (!waiting || !paymentId) return
    let isMounted = true

    const poll = async () => {
      try {
        const updated = await pollPaymentStatus(paymentId)
        if (!isMounted) return
        if (updated && updated.status === 'pagado') {
          nav.toast('¡Pago recibido!')
        }
      } catch (err) {
        console.error('Error polling payment status:', err)
      }
    }

    const interval = setInterval(poll, 3000)
    return () => {
      isMounted = false
      clearInterval(interval)
    }
  }, [waiting, paymentId, pollPaymentStatus, nav])

  if (!payment || !sub || !plan) return null
  const first = sub.name.split(' ')[0]
  const paymentLink = payment.payment_link_url || `https://klipo.mx/c/${payment.id.slice(-6)}`

  const sendWhatsApp = () => {
    const text = `Hola ${first}, te comparto tu cobro de ${plan.name} por ${money(payment.amount)}. Puedes pagar aquí: ${paymentLink}`
    window.open(`https://wa.me/52${sub.phone}?text=${encodeURIComponent(text)}`, '_blank', 'noopener')
  }
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(paymentLink)
      nav.toast('Enlace copiado')
    } catch {
      nav.toast(paymentLink)
    }
  }
  const handleMarkCash = async () => {
    if (isMarkingCash) return
    setIsMarkingCash(true)
    try {
      await markCash(paymentId)
      nav.toast('Pago en efectivo registrado')
    } catch (err: any) {
      nav.toast(err?.message || 'Error al registrar pago en efectivo')
    } finally {
      setIsMarkingCash(false)
    }
  }
  const close = () => nav.tab({ name: 'home' })

  if (!waiting) {
    return (
      <>
        <TopBar onBack={close} />
        <Page className="flex flex-col items-center pt-10 pb-48 text-center">
          <span className="flex size-24 animate-pop items-center justify-center rounded-full bg-leaf text-cream shadow-[0_16px_40px_-16px_rgba(46,125,91,0.9)]">
            <Icon name="check" size={40} />
          </span>
          <h1 className="mt-6 text-[30px] leading-tight font-bold tracking-[-0.02em]">¡Pago recibido!</h1>
          <p className="mt-2 text-[17px] text-ink/70">
            {first} ya está al corriente en {plan.name}.
          </p>
          <Card className="mt-8 w-full p-5 text-left">
            <div className="flex items-center gap-3.5">
              <Avatar name={sub.name} status="al_corriente" />
              <div className="flex-1">
                <p className="text-[16px] font-bold">{sub.name}</p>
                <p className="text-[16px] text-ink/60">
                  {payment.method === 'efectivo' ? 'Efectivo' : 'CoDi'} · {payment.when || 'Hoy'}
                </p>
              </div>
              <p className="text-[22px] font-bold text-leaf">+{money(payment.amount)}</p>
            </div>
          </Card>
        </Page>
        <BottomAction>
          <Button variant="primary" onClick={close}>
            Volver al inicio
          </Button>
          <Button variant="soft" onClick={() => nav.replace({ name: 'chargeSub', planId: plan.id })}>
            Cobrar a alguien más
          </Button>
        </BottomAction>
      </>
    )
  }

  const qrSource = payment.qr_image
    ? payment.qr_image.startsWith('data:')
      ? payment.qr_image
      : `data:image/png;base64,${payment.qr_image}`
    : qrImage

  return (
    <>
      <TopBar title="Cobro generado" onBack={close} />
      <Page className="pt-2 pb-56">
        <Card className="flex flex-col items-center px-6 pt-5 pb-6">
          <span className="mb-5 inline-flex items-center gap-2 rounded-full bg-honey-50 px-3 py-1.5 text-[16px] font-bold ring-1 ring-honey/60">
            <span className="relative flex size-2">
              <span className="absolute inset-0 animate-ping rounded-full bg-honey" />
              <span className="relative size-2 rounded-full bg-honey" />
            </span>
            Esperando pago
          </span>
          <img
            src={qrSource}
            alt={`Código QR CoDi para cobrar ${money(payment.amount)} a ${sub.name}`}
            width={216}
            height={216}
            className="rounded-xl object-contain shadow-sm"
          />
          <p className="mt-5 text-[44px] leading-none font-extrabold tracking-[-0.03em]">
            {money(payment.amount)} <span className="text-[16px] font-normal tracking-normal text-ink/60">MXN</span>
          </p>
          <p className="mt-2 text-[16px] text-ink/70">
            {sub.name} · {plan.name}
          </p>
        </Card>
        <p className="mt-4 text-center text-[16px] text-ink/65">Pídele que lo escanee con la app de su banco.</p>
      </Page>
      <BottomAction>
        <Button variant="primary" icon="send" onClick={sendWhatsApp}>
          Enviar por WhatsApp
        </Button>
        <Button variant="soft" icon="copy" onClick={copy}>
          Copiar enlace de pago
        </Button>
        <Button variant="ghost" icon="cash" disabled={isMarkingCash} onClick={handleMarkCash}>
          {isMarkingCash ? 'Registrando...' : 'Marcar como pagado en efectivo'}
        </Button>
      </BottomAction>
    </>
  )
}
