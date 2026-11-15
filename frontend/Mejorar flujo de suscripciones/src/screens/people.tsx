import { useState } from 'react'
import { money } from '../data'
import { useNav, type SubFilter } from '../nav'
import { Divided, SubscriberRow } from '../rows'
import { useStore } from '../store'
import { BottomAction, BottomNav, Button, Card, Chips, Icon, Page, PlanTile, SearchField, TabHeader, TopBar } from '../ui'
import { Field, inputCls } from './plans'

const order = { atrasado: 0, por_vencer: 1, al_corriente: 2 }

export function Subscribers({ initialFilter = 'todos' }: { initialFilter?: SubFilter }) {
  const store = useStore()
  const nav = useNav()
  const [q, setQ] = useState('')
  const [filter, setFilter] = useState<SubFilter>(initialFilter)
  const all = store.subscribers
  const count = (f: SubFilter) => (f === 'todos' ? all.length : all.filter((s) => s.status === f).length)
  const list = all
    .filter((s) => filter === 'todos' || s.status === filter)
    .filter((s) => s.name.toLowerCase().includes(q.trim().toLowerCase()))
    .sort((a, b) => order[a.status] - order[b.status] || a.name.localeCompare(b.name))

  return (
    <>
      <TabHeader
        title="Suscriptores"
        right={
          <Button size="sm" variant="primary" icon="plus" onClick={() => nav.go({ name: 'newSub' })}>
            Nuevo
          </Button>
        }
      />
      <Page wide className="pt-2 pb-32">
        <SearchField value={q} onChange={setQ} placeholder="Buscar por nombre" />
        <div className="mt-3">
          <Chips
            value={filter}
            onChange={setFilter}
            options={[
              { value: 'todos', label: 'Todos', count: count('todos') },
              { value: 'atrasado', label: 'Atrasados', count: count('atrasado') },
              { value: 'por_vencer', label: 'Por vencer', count: count('por_vencer') },
              { value: 'al_corriente', label: 'Al corriente', count: count('al_corriente') },
            ]}
          />
        </div>
        {filter === 'atrasado' && store.lateSubs.length > 0 && (
          <p className="mt-4 text-[16px] text-ink/70">
            Tienes <b className="text-ink">{money(store.lateAmount)}</b> sin cobrar de meses pasados.
          </p>
        )}
        <Card className="mt-3">
          <Divided>
            {list.map((s) => (
              <SubscriberRow key={s.id} sub={s} showPlan />
            ))}
          </Divided>
          {list.length === 0 && (
            <p className="px-4 py-10 text-center text-[16px] text-ink/60">
              {filter === 'atrasado' ? 'Nadie atrasado. Todo al corriente.' : 'Nadie coincide con tu búsqueda.'}
            </p>
          )}
        </Card>
      </Page>
      <BottomNav active="subscribers" />
    </>
  )
}

export function NewSubscriber({ planId, charge = false }: { planId?: string; charge?: boolean }) {
  const store = useStore()
  const nav = useNav()
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [plan, setPlan] = useState(planId ?? store.plans[0]?.id ?? '')
  const [chargeNow, setChargeNow] = useState(true)
  const [touched, setTouched] = useState(false)
  const [isSaving, setIsSaving] = useState(false)

  const selectedPlan = store.plan(plan)
  const nameOk = name.trim().length > 2
  const phoneOk = phone.length === 10
  const valid = nameOk && phoneOk && !!selectedPlan

  const save = async () => {
    setTouched(true)
    if (!valid || isSaving) return
    setIsSaving(true)
    try {
      const created = await store.addSubscriber({
        name: name.trim().replace(/\s+/g, ' '),
        phone,
        planId: plan,
        status: 'por_vencer',
        note: 'Nuevo · sin cobrar',
        instant_charge: chargeNow,
      })
      if (chargeNow) {
        nav.replace({ name: 'summary', subscriberId: created.id })
      } else {
        nav.toast(`${name.trim().split(' ')[0]} agregado a ${selectedPlan?.name}`)
        nav.back()
      }
    } catch (err: any) {
      nav.toast(err?.message || 'Error al guardar suscriptor')
    } finally {
      setIsSaving(false)
    }
  }

  const formatted = phone.replace(/^(\d{2})(\d{0,4})(\d{0,4}).*/, (_, a, b, c) => [a, b, c].filter(Boolean).join(' '))

  return (
    <>
      <TopBar title="Nuevo suscriptor" step={charge ? 'Cobrar' : undefined} />
      <Page className="pt-2 pb-36">
        <form
          className="flex flex-col gap-5"
          onSubmit={(e) => {
            e.preventDefault()
            save()
          }}
        >
          <Field label="Nombre completo">
            <input
              autoFocus
              className={inputCls}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Ej. Andrea Morales"
              autoComplete="name"
            />
            {touched && !nameOk && <span className="text-[16px] text-wine">Escribe su nombre.</span>}
          </Field>
          <Field label="WhatsApp">
            <div className={`${inputCls} flex items-center gap-3`}>
              <span className="font-bold text-ink/70">+52</span>
              <span className="h-6 w-px bg-sand" />
              <input
                inputMode="tel"
                className="w-full bg-transparent outline-none placeholder:text-ink/35"
                value={formatted}
                onChange={(e) => setPhone(e.target.value.replace(/\D/g, '').slice(0, 10))}
                placeholder="55 1234 5678"
                autoComplete="tel-national"
              />
            </div>
            {touched && !phoneOk && <span className="text-[16px] text-wine">Son 10 dígitos.</span>}
          </Field>
          <Field label="Plan" group>
            <div className="flex flex-col gap-2">
              {store.plans.map((p) => {
                const on = p.id === plan
                return (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => setPlan(p.id)}
                    aria-pressed={on}
                    className={`flex items-center gap-3 rounded-2xl p-3 text-left ring-[1.5px] transition-colors ${
                      on ? 'bg-petrol-50 ring-petrol' : 'bg-paper ring-sand hover:ring-petrol/30'
                    }`}
                  >
                    <PlanTile icon={p.icon} size={40} />
                    <span className="flex-1 text-[16px] font-bold">{p.name}</span>
                    <span className="text-[16px] text-ink/70">{money(p.price)} / mes</span>
                    <Radio on={on} />
                  </button>
                )
              })}
            </div>
          </Field>
          <button
            type="button"
            role="switch"
            aria-checked={chargeNow}
            onClick={() => setChargeNow((v) => !v)}
            className="flex items-center gap-4 rounded-2xl bg-paper p-4 text-left ring-[1.5px] ring-sand"
          >
            <span className="flex-1">
              <span className="block text-[16px] font-bold">Cobrar el primer mes ahora</span>
              <span className="block text-[16px] text-ink/60">
                {selectedPlan ? `${money(selectedPlan.price)} con QR o en efectivo` : 'Elige un plan'}
              </span>
            </span>
            <span className={`relative h-7 w-12 rounded-full transition-colors ${chargeNow ? 'bg-petrol' : 'bg-sand'}`}>
              <span
                className={`absolute top-1 size-5 rounded-full bg-cream shadow transition-[left] ${chargeNow ? 'left-6' : 'left-1'}`}
              />
            </span>
          </button>
          <button type="submit" hidden />
        </form>
      </Page>
      <BottomAction>
        <Button variant={chargeNow ? 'charge' : 'primary'} trailing="arrow" onClick={save}>
          {chargeNow ? 'Guardar y cobrar' : 'Guardar'}
        </Button>
      </BottomAction>
    </>
  )
}

export function Radio({ on }: { on: boolean }) {
  return (
    <span
      className={`flex size-7 shrink-0 items-center justify-center rounded-full transition-colors ${
        on ? 'bg-petrol text-cream' : 'ring-[1.5px] ring-sand ring-inset'
      }`}
    >
      {on && <Icon name="check" size={12} />}
    </span>
  )
}
