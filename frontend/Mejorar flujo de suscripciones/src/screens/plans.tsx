import { useState, type ReactNode } from 'react'
import { MONTH, money, type Plan, type PlanIcon } from '../data'
import { useNav, type SubFilter } from '../nav'
import { Divided, SubscriberRow } from '../rows'
import { useStore } from '../store'
import {
  BottomAction,
  BottomNav,
  Button,
  Card,
  Chips,
  Icon,
  Page,
  PlanTile,
  Progress,
  SearchField,
  TabHeader,
  TopBar,
} from '../ui'

export function Plans() {
  const store = useStore()
  const nav = useNav()
  const [q, setQ] = useState('')
  const ratio = store.expected ? store.collected / store.expected : 0
  const list = store.planStats.filter((p) => p.plan.name.toLowerCase().includes(q.trim().toLowerCase()))

  return (
    <>
      <TabHeader
        title="Planes"
        right={
          <Button size="sm" variant="primary" icon="plus" onClick={() => nav.go({ name: 'planForm' })}>
            Nuevo plan
          </Button>
        }
      />
      <Page wide className="pt-2 pb-32">
        <Card className="p-5">
          <p className="text-[16px] text-ink/60">{MONTH}</p>
          <div className="mt-3 grid grid-cols-3 gap-2">
            <Stat label="Cobrado" value={money(store.collected)} tone="text-leaf" />
            <Stat label="Esperado" value={money(store.expected)} />
            <Stat label="Por cobrar" value={money(store.pending)} />
          </div>
          <div className="mt-4">
            <Progress value={ratio} />
          </div>
        </Card>

        <div className="mt-4">
          <SearchField value={q} onChange={setQ} placeholder="Buscar plan" />
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {list.map(({ plan, subs, collected, expected, late }) => (
            <button
              key={plan.id}
              type="button"
              onClick={() => nav.go({ name: 'plan', planId: plan.id })}
              className="flex flex-col rounded-3xl bg-paper p-5 text-left ring-[1.5px] ring-sand transition-shadow hover:ring-petrol/30"
            >
              <div className="flex items-start gap-3.5">
                <PlanTile icon={plan.icon} />
                <div className="min-w-0 flex-1">
                  <p className="text-[19px] leading-tight font-bold">{plan.name}</p>
                  <p className="text-[16px] text-ink/60">{subs.length} suscriptores</p>
                </div>
                <p className="text-[19px] font-bold">
                  {money(plan.price)}
                  <span className="text-[16px] font-normal text-ink/55"> / mes</span>
                </p>
              </div>
              <div className="mt-5 mb-2 flex justify-between text-[16px]">
                <span>
                  <b className="text-leaf">{money(collected)}</b> <span className="text-ink/60">de {money(expected)}</span>
                </span>
                <span className="text-ink/60">Cobra el {plan.chargeDay}</span>
              </div>
              <Progress value={expected ? collected / expected : 0} />
              <div className="mt-4">
                {late > 0 ? (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-honey px-2.5 py-1 text-[16px] font-bold">
                    <Icon name="warning" size={12} />
                    {late} {late === 1 ? 'atrasado' : 'atrasados'}
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-leaf-50 px-2.5 py-1 text-[16px] font-bold text-leaf">
                    <Icon name="check" size={11} />
                    Todos al corriente
                  </span>
                )}
              </div>
            </button>
          ))}
          {list.length === 0 && <p className="py-10 text-center text-[16px] text-ink/60">No hay planes con ese nombre.</p>}
        </div>
      </Page>
      <BottomNav active="plans" />
    </>
  )
}

function Stat({ label, value, tone = '' }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-2xl bg-sand-100/70 px-3 py-2.5">
      <p className="text-[16px] text-ink/60">{label}</p>
      <p className={`text-[19px] font-bold tracking-[-0.01em] ${tone}`}>{value}</p>
    </div>
  )
}

export function PlanDetail({ planId }: { planId: string }) {
  const store = useStore()
  const nav = useNav()
  const [q, setQ] = useState('')
  const [filter, setFilter] = useState<SubFilter>('todos')
  const stats = store.planStats.find((p) => p.plan.id === planId)
  if (!stats) return null
  const { plan, subs, collected, expected, pending } = stats

  const order = { atrasado: 0, por_vencer: 1, al_corriente: 2 }
  const count = (f: SubFilter) => (f === 'todos' ? subs.length : subs.filter((s) => s.status === f).length)
  const list = subs
    .filter((s) => filter === 'todos' || s.status === filter)
    .filter((s) => s.name.toLowerCase().includes(q.trim().toLowerCase()))
    .sort((a, b) => order[a.status] - order[b.status])

  return (
    <>
      <TopBar
        title={plan.name}
        right={
          <Button size="sm" variant="soft" icon="edit" onClick={() => nav.go({ name: 'planForm', planId })}>
            Editar
          </Button>
        }
      />
      <Page className="pt-1 pb-32">
        <Card className="p-5">
          <div className="flex items-start gap-4">
            <PlanTile icon={plan.icon} size={56} />
            <div className="min-w-0 flex-1">
              <p className="flex items-baseline gap-1">
                <span className="text-[34px] leading-none font-extrabold tracking-[-0.02em] text-ink">{money(plan.price)}</span>
                <span className="text-[16px] text-ink/60">/ mes</span>
              </p>
              <p className="mt-1.5 text-[16px] text-ink/70">{plan.description}</p>
            </div>
          </div>
          <div className="mt-5 grid grid-cols-2 gap-2">
            <div className="rounded-2xl bg-leaf-50 px-4 py-3">
              <p className="text-[16px] text-leaf">Cobrado</p>
              <p className="text-[22px] font-bold text-leaf">{money(collected)}</p>
            </div>
            <div className="rounded-2xl bg-sand-100 px-4 py-3">
              <p className="text-[16px] text-ink/60">Falta cobrar</p>
              <p className="text-[22px] font-bold">{money(pending)}</p>
            </div>
          </div>
          <div className="mt-4">
            <Progress value={expected ? collected / expected : 0} />
          </div>
          <p className="mt-2 text-[16px] text-ink/60">Se cobra el día {plan.chargeDay} de cada mes</p>
        </Card>

        <h2 className="mt-8 mb-3 text-[20px] font-bold">
          Suscriptores <span className="text-ink/45">{subs.length}</span>
        </h2>
        <SearchField value={q} onChange={setQ} placeholder="Buscar suscriptor" />
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
        <Card className="mt-3">
          <Divided>
            {list.map((s) => (
              <SubscriberRow key={s.id} sub={s} />
            ))}
          </Divided>
          {list.length === 0 && <p className="px-4 py-8 text-center text-[16px] text-ink/60">Nadie en esta lista.</p>}
        </Card>
      </Page>
      <BottomAction>
        <Button variant="outline" icon="userPlus" onClick={() => nav.go({ name: 'newSub', planId })}>
          Agregar suscriptor
        </Button>
      </BottomAction>
    </>
  )
}

const iconOptions: { value: PlanIcon; label: string }[] = [
  { value: 'gym', label: 'Gimnasio' },
  { value: 'yoga', label: 'Yoga' },
  { value: 'pilates', label: 'Clases' },
  { value: 'wallet', label: 'Otro' },
]

export function PlanForm({ planId }: { planId?: string }) {
  const store = useStore()
  const nav = useNav()
  const existing = planId ? store.plan(planId) : undefined
  const [name, setName] = useState(existing?.name ?? '')
  const [price, setPrice] = useState(existing ? String(existing.price) : '')
  const [description, setDescription] = useState(existing?.description ?? '')
  const [chargeDay, setChargeDay] = useState(String(existing?.chargeDay ?? 1))
  const [icon, setIcon] = useState<PlanIcon>(existing?.icon ?? 'wallet')
  const [isSaving, setIsSaving] = useState(false)

  const priceN = Number(price)
  const dayN = Number(chargeDay)
  const valid = name.trim().length > 1 && priceN > 0 && dayN >= 1 && dayN <= 28

  const save = async () => {
    if (!valid || isSaving) return
    setIsSaving(true)
    try {
      const plan: Plan = {
        id: existing?.id ?? `plan-${Date.now()}`,
        name: name.trim(),
        price: Number(priceN.toFixed(2)),
        description: description.trim(),
        chargeDay: dayN,
        icon,
      }
      await store.savePlan(plan)
      nav.toast(existing ? 'Plan actualizado' : 'Plan creado')
      if (existing) nav.back()
      else nav.replace({ name: 'plan', planId: plan.id })
    } catch (err: any) {
      nav.toast(err?.message || 'Error al guardar el plan')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <>
      <TopBar title={existing ? 'Editar plan' : 'Nuevo plan'} />
      <Page className="pt-2 pb-36">
        <form
          className="flex flex-col gap-5"
          onSubmit={(e) => {
            e.preventDefault()
            save()
          }}
        >
          <Field label="Nombre">
            <input className={inputCls} value={name} onChange={(e) => setName(e.target.value)} placeholder="Ej. Spinning" />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Precio al mes">
              <div className={`${inputCls} flex items-center gap-1`}>
                <span className="text-ink/50">$</span>
                <input
                  inputMode="decimal"
                  className="w-full bg-transparent outline-none"
                  value={price}
                  onChange={(e) => {
                    const raw = e.target.value.replace(/[^0-9.]/g, '')
                    const parts = raw.split('.')
                    const clean = parts[0] + (parts.length > 1 ? '.' + parts.slice(1).join('') : '')
                    setPrice(clean)
                  }}
                  placeholder="300"
                />
              </div>
            </Field>
            <Field label="Día de cobro">
              <select className={inputCls} value={chargeDay} onChange={(e) => setChargeDay(e.target.value)}>
                {Array.from({ length: 28 }, (_, i) => (
                  <option key={i + 1} value={i + 1}>
                    Día {i + 1}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <Field label="Qué incluye">
            <textarea
              rows={2}
              className={`${inputCls} h-auto py-3`}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Ej. 3 clases por semana"
            />
          </Field>
          <Field label="Ícono" group>
            <div className="grid grid-cols-4 gap-2">
              {iconOptions.map((o) => (
                <button
                  key={o.value}
                  type="button"
                  onClick={() => setIcon(o.value)}
                  aria-pressed={icon === o.value}
                  className={`flex flex-col items-center gap-1.5 rounded-2xl py-3 text-[16px] font-bold ring-[1.5px] transition-colors ${
                    icon === o.value ? 'bg-petrol-50 text-petrol ring-petrol' : 'bg-paper text-ink/60 ring-sand'
                  }`}
                >
                  <Icon name={o.value} size={22} />
                  {o.label}
                </button>
              ))}
            </div>
          </Field>
          <button type="submit" hidden />
        </form>
      </Page>
      <BottomAction>
        <Button variant="primary" disabled={!valid} onClick={save}>
          {existing ? 'Guardar cambios' : 'Crear plan'}
        </Button>
      </BottomAction>
    </>
  )
}

export const inputCls =
  'h-13 w-full rounded-2xl bg-paper px-4 text-[17px] ring-[1.5px] ring-sand outline-none placeholder:text-ink/35 focus-within:ring-petrol/60 focus:ring-petrol/60'

export function Field({ label, children, group = false }: { label: string; children: ReactNode; group?: boolean }) {
  const Tag = group ? 'div' : 'label'
  return (
    <Tag className="flex flex-col gap-2" role={group ? 'group' : undefined} aria-label={group ? label : undefined}>
      <span className="text-[16px] font-bold">{label}</span>
      {children}
    </Tag>
  )
}
