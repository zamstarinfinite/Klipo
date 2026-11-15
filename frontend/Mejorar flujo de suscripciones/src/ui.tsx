import type { ButtonHTMLAttributes, CSSProperties, ReactNode } from 'react'
import { initials, paymentLabel, statusLabel, type PaymentStatus, type PlanIcon, type SubStatus } from './data'
import { useNav, type Tab } from './nav'

const asset = (file: string) => `${import.meta.env.BASE_URL}assets/${file}`

/** Íconos del archivo de Figma. Se pintan con `currentColor` vía máscara para poder cambiar la paleta. */
const icons = {
  logo: '2e211.svg',
  bell: 'b0367.svg',
  home: 'e28fc.svg',
  plans: '5f565.svg',
  users: '7de3c.svg',
  register: '7aa25.svg',
  plus: '9c644.svg',
  back: '58f12.svg',
  arrow: '11c42.svg',
  chevron: 'cdf25.svg',
  search: '0cc49.svg',
  check: '3c5fc.svg',
  checkCircle: '091a4.svg',
  warning: '1ba5a.svg',
  alert: '220af.svg',
  userPlus: '9d646.svg',
  qr: '40683.svg',
  cash: '60b0b.svg',
  send: '868e9.svg',
  copy: '83197.svg',
  close: '97d2b.svg',
  edit: '56bff.svg',
  shield: 'c21be.svg',
  receipt: 'd34c7.svg',
  gym: 'dfd84.svg',
  yoga: '2b7b6.svg',
  pilates: 'e8782.svg',
  wallet: 'f89d3.svg',
} as const

export type IconName = keyof typeof icons

export function Icon({ name, size = 18, className = '' }: { name: IconName; size?: number; className?: string }) {
  const url = `url(${asset(icons[name])})`
  const style: CSSProperties = {
    width: size,
    height: size,
    maskImage: url,
    WebkitMaskImage: url,
    maskSize: 'contain',
    WebkitMaskSize: 'contain',
    maskRepeat: 'no-repeat',
    WebkitMaskRepeat: 'no-repeat',
    maskPosition: 'center',
    WebkitMaskPosition: 'center',
  }
  return <span aria-hidden className={`inline-block shrink-0 bg-current ${className}`} style={style} />
}

export const qrImage = asset('fced4.svg')

type Variant = 'charge' | 'primary' | 'outline' | 'soft' | 'ghost'

const variants: Record<Variant, string> = {
  charge: 'bg-wine text-cream hover:bg-wine-700 shadow-[0_6px_16px_-8px_rgba(122,30,43,0.7)]',
  primary: 'bg-petrol text-cream hover:bg-petrol-700 shadow-[0_6px_16px_-8px_rgba(23,65,79,0.7)]',
  outline: 'bg-paper text-petrol ring-[1.5px] ring-inset ring-petrol/25 hover:ring-petrol/60',
  soft: 'bg-sand-100 text-ink hover:bg-sand',
  ghost: 'text-petrol hover:bg-petrol-50',
}

export function Button({
  variant = 'primary',
  icon,
  trailing,
  size = 'lg',
  className = '',
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant
  icon?: IconName
  trailing?: IconName
  size?: 'lg' | 'sm'
}) {
  const sizing = size === 'lg' ? 'h-13 px-5 text-[16px] rounded-2xl gap-2.5' : 'min-h-10 px-3.5 text-[16px] rounded-full gap-1.5'
  return (
    <button
      type="button"
      {...rest}
      className={`inline-flex items-center justify-center font-bold transition-colors active:scale-[0.98] disabled:opacity-40 disabled:shadow-none ${sizing} ${variants[variant]} ${className}`}
    >
      {icon && <Icon name={icon} size={size === 'lg' ? 18 : 14} />}
      {children}
      {trailing && <Icon name={trailing} size={size === 'lg' ? 16 : 13} />}
    </button>
  )
}

const subTone: Record<SubStatus, string> = {
  atrasado: 'bg-honey text-ink',
  por_vencer: 'bg-honey-50 text-ink',
  al_corriente: 'bg-leaf-50 text-leaf',
}

export function StatusBadge({ status }: { status: SubStatus }) {
  return (
    <span className={`inline-flex min-h-7 items-center rounded-full px-2.5 text-[16px] font-bold ${subTone[status]}`}>
      {statusLabel[status]}
    </span>
  )
}

const payTone: Record<PaymentStatus, string> = {
  pagado: 'bg-leaf text-cream',
  pendiente: 'bg-sand text-ink',
  vencido: 'bg-honey text-ink',
  fallido: 'bg-wine-50 text-wine',
}

export function PaymentBadge({ status }: { status: PaymentStatus }) {
  return (
    <span className={`inline-flex min-h-7 items-center rounded-full px-2.5 text-[16px] font-bold ${payTone[status]}`}>
      {paymentLabel[status]}
    </span>
  )
}

const dotTone: Record<SubStatus, string> = {
  atrasado: 'bg-honey',
  por_vencer: 'bg-honey-50 ring-1 ring-honey',
  al_corriente: 'bg-leaf',
}

export function Avatar({ name, status, size = 44 }: { name: string; status?: SubStatus; size?: number }) {
  return (
    <span
      className="relative inline-flex shrink-0 items-center justify-center rounded-full bg-sand-100 font-bold text-petrol"
      style={{ width: size, height: size, fontSize: Math.max(16, size * 0.36) }}
    >
      {initials(name)}
      {status && (
        <span className={`absolute right-0 bottom-0 size-3 rounded-full ring-2 ring-paper ${dotTone[status]}`} />
      )}
    </span>
  )
}

export function PlanTile({ icon, size = 48 }: { icon: PlanIcon; size?: number }) {
  return (
    <span
      className="inline-flex shrink-0 items-center justify-center rounded-2xl bg-petrol-50 text-petrol"
      style={{ width: size, height: size }}
    >
      <Icon name={icon} size={size * 0.46} />
    </span>
  )
}

export function Progress({ value, tone = 'leaf', track = 'bg-sand' }: { value: number; tone?: 'leaf' | 'mint'; track?: string }) {
  const pct = Math.max(0, Math.min(100, value * 100))
  return (
    <div className={`h-2 w-full overflow-hidden rounded-full ${track}`}>
      <div
        className={`h-full rounded-full transition-[width] duration-700 ${tone === 'mint' ? 'bg-mint' : 'bg-leaf'}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-3xl bg-paper ring-[1.5px] ring-sand ${className}`}>{children}</div>
}

export function SectionTitle({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <div className="mb-3 flex items-end justify-between">
      <h2 className="text-[20px] leading-tight font-bold">{title}</h2>
      {action}
    </div>
  )
}

export function LinkButton({ children, onClick }: { children: ReactNode; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="inline-flex items-center gap-1 py-1 text-[16px] font-bold text-petrol hover:underline">
      {children}
      <Icon name="arrow" size={13} />
    </button>
  )
}

export function SearchField({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder: string }) {
  return (
    <label className="flex h-12 items-center gap-3 rounded-2xl bg-paper px-4 ring-[1.5px] ring-sand focus-within:ring-petrol/50">
      <Icon name="search" size={16} className="text-ink/45" />
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-transparent text-[16px] outline-none placeholder:text-ink/40"
      />
    </label>
  )
}

export function Chips<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string; count?: number }[]
  value: T
  onChange: (v: T) => void
}) {
  return (
    <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 [scrollbar-width:none]">
      {options.map((o) => {
        const active = o.value === value
        return (
          <button
            key={o.value}
            type="button"
            onClick={() => onChange(o.value)}
            aria-pressed={active}
            className={`min-h-10 shrink-0 rounded-full px-3.5 text-[16px] font-bold transition-colors ${
              active ? 'bg-petrol text-cream' : 'bg-paper text-ink/75 ring-[1.5px] ring-sand hover:ring-petrol/30'
            }`}
          >
            {o.label}
            {o.count !== undefined && <span className={active ? 'ml-1.5 text-cream/70' : 'ml-1.5 text-ink/45'}>{o.count}</span>}
          </button>
        )
      })}
    </div>
  )
}

/** Barra superior de pantallas internas. */
export function TopBar({ title, step, right, onBack }: { title?: string; step?: string; right?: ReactNode; onBack?: () => void }) {
  const nav = useNav()
  return (
    <header className="sticky top-0 z-20 bg-cream/90 backdrop-blur-xl">
      <div className="mx-auto flex h-16 w-full max-w-xl items-center gap-2 px-2 md:max-w-3xl">
        <button
          type="button"
          onClick={onBack ?? nav.back}
          aria-label="Volver"
          className="flex size-11 items-center justify-center rounded-full text-ink hover:bg-sand-100"
        >
          <Icon name="back" size={18} />
        </button>
        <div className="min-w-0 flex-1">
          {step && <p className="text-[16px] font-bold tracking-wide text-petrol">{step}</p>}
          {title && <h1 className="truncate text-[20px] leading-tight font-bold">{title}</h1>}
        </div>
        {right && <div className="pr-2">{right}</div>}
      </div>
    </header>
  )
}

export function Page({ children, wide = false, className = '' }: { children: ReactNode; wide?: boolean; className?: string }) {
  return (
    <main className={`mx-auto w-full max-w-xl animate-rise px-4 ${wide ? 'md:max-w-3xl' : ''} ${className}`}>{children}</main>
  )
}

/** Acción principal fija al fondo en los flujos. */
export function BottomAction({ children }: { children: ReactNode }) {
  return (
    <div className="fixed inset-x-0 bottom-0 z-20 bg-linear-to-t from-cream via-cream to-cream/0 pt-6 pb-[max(16px,env(safe-area-inset-bottom))]">
      <div className="mx-auto flex w-full max-w-xl flex-col gap-2 px-4">{children}</div>
    </div>
  )
}

const tabs: { tab: Tab; label: string; icon: IconName }[] = [
  { tab: 'home', label: 'Inicio', icon: 'home' },
  { tab: 'plans', label: 'Planes', icon: 'plans' },
  { tab: 'subscribers', label: 'Suscriptores', icon: 'users' },
  { tab: 'payments', label: 'Cobros', icon: 'register' },
]

export function BottomNav({ active }: { active?: Tab }) {
  const nav = useNav()
  const item = (t: (typeof tabs)[number]) => {
    const on = t.tab === active
    return (
      <button
        key={t.tab}
        type="button"
        onClick={() => nav.tab({ name: t.tab })}
        aria-current={on ? 'page' : undefined}
        className={`flex min-w-0 flex-1 flex-col items-center justify-center gap-1 py-2 text-[16px] font-bold tracking-[-0.01em] transition-colors ${
          on ? 'text-petrol' : 'text-ink/50 hover:text-ink/80'
        }`}
      >
        <span className={`flex h-7 w-12 items-center justify-center rounded-full ${on ? 'bg-petrol-50' : ''}`}>
          <Icon name={t.icon} size={18} />
        </span>
        <span className={on ? 'block' : 'hidden min-[480px]:block'}>{t.label}</span>
      </button>
    )
  }
  return (
    <nav className="fixed inset-x-0 bottom-0 z-30 bg-cream/95 pb-[env(safe-area-inset-bottom)] shadow-[0_-1px_0_var(--color-sand)] backdrop-blur-xl">
      <div className="mx-auto flex h-[72px] w-full max-w-xl items-center px-1">
        {tabs.slice(0, 2).map(item)}
        <div className="flex shrink-0 justify-center px-1">
          <button
            type="button"
            onClick={() => nav.go({ name: 'chargePlan' })}
            className="-mt-7 flex h-14 items-center gap-2 rounded-full bg-wine px-4 text-[16px] font-bold text-cream shadow-[0_10px_24px_-10px_rgba(122,30,43,0.9)] ring-4 ring-cream transition-colors hover:bg-wine-700 active:scale-95"
          >
            <Icon name="plus" size={14} />
            Cobrar
          </button>
        </div>
        {tabs.slice(2).map(item)}
      </div>
    </nav>
  )
}

export function Wordmark() {
  return (
    <span className="flex items-center gap-2.5">
      <span className="flex size-9 items-center justify-center rounded-full bg-wine text-cream">
        <Icon name="logo" size={16} />
      </span>
      <span className="flex items-baseline gap-0.5 text-[26px] leading-none font-extrabold tracking-[-0.03em] text-wine">
        klipo
        <span className="size-1.5 rounded-full bg-leaf" />
      </span>
    </span>
  )
}

/** Encabezado de las pestañas principales. */
export function TabHeader({ title, right }: { title?: string; right?: ReactNode }) {
  return (
    <header className="sticky top-0 z-20 bg-cream/90 backdrop-blur-xl">
      <div className="mx-auto flex h-16 w-full max-w-xl items-center justify-between px-4 md:max-w-3xl">
        {title ? <h1 className="text-[26px] leading-none font-bold tracking-[-0.02em]">{title}</h1> : <Wordmark />}
        {right}
      </div>
    </header>
  )
}
