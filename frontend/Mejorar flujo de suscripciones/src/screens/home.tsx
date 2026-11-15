import { MONTH, money } from '../data'
import { useNav } from '../nav'
import { Divided, PaymentRow } from '../rows'
import { useStore } from '../store'
import { BottomNav, Card, Icon, LinkButton, Page, PlanTile, Progress, SectionTitle, TabHeader } from '../ui'

export function Home() {
  const store = useStore()
  const nav = useNav()
  const ratio = store.expected ? store.collected / store.expected : 0
  const late = store.lateSubs.length

  return (
    <>
      <TabHeader
        right={
          <button
            type="button"
            onClick={() => nav.tab({ name: 'subscribers', filter: 'atrasado' })}
            aria-label={late ? `${late} atrasados` : 'Avisos'}
            className="relative flex size-11 items-center justify-center rounded-full text-ink/80 hover:bg-sand-100"
          >
            <Icon name="bell" size={18} />
            {late > 0 && <span className="absolute top-2.5 right-2.5 size-2.5 rounded-full bg-honey ring-2 ring-cream" />}
          </button>
        }
      />
      <Page wide className="pt-2 pb-32">
        <section className="relative overflow-hidden rounded-[28px] bg-petrol p-6 text-cream">
          <div aria-hidden className="absolute -top-16 -right-12 size-48 rounded-full bg-cream/[0.06]" />
          <p className="text-[16px] text-cream/75">Cobrado en {MONTH.toLowerCase()}</p>
          <p className="mt-1 flex items-baseline gap-2">
            <span className="text-[44px] leading-none font-extrabold tracking-[-0.03em]">{money(store.collected)}</span>
            <span className="text-[16px] text-cream/60">MXN</span>
          </p>
          <div className="mt-5">
            <Progress value={ratio} tone="mint" track="bg-cream/15" />
          </div>
          <div className="mt-3 flex justify-between text-[16px]">
            <span className="text-cream/75">
              de <b className="text-cream">{money(store.expected)}</b> esperados
            </span>
            <b className="text-mint">{Math.round(ratio * 100)}%</b>
          </div>
        </section>

        {late > 0 && (
          <button
            type="button"
            onClick={() => nav.tab({ name: 'subscribers', filter: 'atrasado' })}
            className="mt-3 flex w-full items-center gap-3 rounded-2xl bg-honey-50 px-4 py-3.5 text-left ring-[1.5px] ring-honey/60 transition-colors hover:bg-honey/30"
          >
            <span className="flex size-9 items-center justify-center rounded-full bg-honey text-ink">
              <Icon name="alert" size={16} />
            </span>
            <span className="flex-1 text-[16px]">
              <b>
                {late} {late === 1 ? 'atrasado' : 'atrasados'}
              </b>{' '}
              · {money(store.lateAmount)} por cobrar
            </span>
            <Icon name="chevron" size={12} className="text-ink/60" />
          </button>
        )}

        <div className="mt-8 grid gap-8 md:grid-cols-2 md:gap-6">
          <section>
            <SectionTitle title="Mis planes" action={<LinkButton onClick={() => nav.tab({ name: 'plans' })}>Ver todos</LinkButton>} />
            <div className="flex flex-col gap-2.5">
              {store.planStats.length === 0 ? (
                <p className="py-6 text-center text-[16px] text-ink/60">No hay planes registrados.</p>
              ) : (
                store.planStats.slice(0, 3).map(({ plan, subs, late: planLate }) => (
                  <button
                    key={plan.id}
                    type="button"
                    onClick={() => nav.go({ name: 'plan', planId: plan.id })}
                    className="flex items-center gap-3.5 rounded-3xl bg-paper p-4 text-left ring-[1.5px] ring-sand transition-shadow hover:ring-petrol/30"
                  >
                    <PlanTile icon={plan.icon} />
                    <div className="min-w-0 flex-1">
                      <p className="text-[17px] font-bold">{plan.name}</p>
                      <p className="text-[16px] text-ink/60">
                        {money(plan.price)} / mes · {subs.length} suscriptores
                      </p>
                      {planLate > 0 && (
                        <p className="mt-0.5 text-[16px] font-bold text-honey-700">
                          {planLate} {planLate === 1 ? 'atrasado' : 'atrasados'}
                        </p>
                      )}
                    </div>
                    <Icon name="chevron" size={12} className="text-ink/40" />
                  </button>
                ))
              )}
            </div>
          </section>

          <section>
            <SectionTitle
              title="Últimos movimientos"
              action={<LinkButton onClick={() => nav.tab({ name: 'payments' })}>Ver todos</LinkButton>}
            />
            <Card>
              <Divided>
                {store.payments.length === 0 ? (
                  <p className="px-4 py-8 text-center text-[16px] text-ink/60">Sin movimientos aún.</p>
                ) : (
                  store.payments.slice(0, 4).map((p) => (
                    <PaymentRow key={p.id} payment={p} />
                  ))
                )}
              </Divided>
            </Card>
          </section>
        </div>
      </Page>
      <BottomNav active="home" />
    </>
  )
}
