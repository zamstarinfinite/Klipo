import { useState } from 'react'
import { MONTH, money } from '../data'
import { Divided, PaymentRow } from '../rows'
import { useStore } from '../store'
import { BottomNav, Card, Chips, Page, TabHeader } from '../ui'

type Filter = 'todos' | 'pagado' | 'pendiente'

export function Payments() {
  const store = useStore()
  const [filter, setFilter] = useState<Filter>('todos')
  const list = store.payments.filter((p) => filter === 'todos' || p.status === filter)
  const pendingCount = store.payments.filter((p) => p.status === 'pendiente').length

  return (
    <>
      <TabHeader title="Cobros" />
      <Page className="pt-2 pb-32">
        <Card className="flex items-center justify-between p-5">
          <div>
            <p className="text-[16px] text-ink/60">Cobrado en {MONTH.toLowerCase()}</p>
            <p className="text-[30px] leading-tight font-extrabold text-leaf">{money(store.collected)}</p>
          </div>
          <div className="text-right">
            <p className="text-[16px] text-ink/60">Pagos</p>
            <p className="text-[30px] leading-tight font-bold">{store.paidCount}</p>
          </div>
        </Card>
        <div className="mt-4">
          <Chips
            value={filter}
            onChange={setFilter}
            options={[
              { value: 'todos', label: 'Todos' },
              { value: 'pagado', label: 'Pagados' },
              { value: 'pendiente', label: 'Esperando pago', count: pendingCount },
            ]}
          />
        </div>
        <Card className="mt-3">
          <Divided>
            {list.map((p) => (
              <PaymentRow key={p.id} payment={p} />
            ))}
          </Divided>
          {list.length === 0 && <p className="px-4 py-10 text-center text-[16px] text-ink/60">Sin cobros aquí.</p>}
        </Card>
      </Page>
      <BottomNav active="payments" />
    </>
  )
}
