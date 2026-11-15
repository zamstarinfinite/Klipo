---
name: "klipo"
description: "PWA mobile-first para PyMES enfocada exclusivamente en el cobro sencillo de suscripciones recurrentes con QR CoDi y recordatorios por WhatsApp."
version: "0.2.0"
platform: "Mobile-First PWA (390px viewport base, responsive hasta 440px centrado)"
colors:
  brand:
    primary: "#7A1E2B"
    hoverTitle: "#4E121C"
  surface:
    background: "#FDF6E3"
    cardBorder: "#E8DCC0"
  ink:
    primary: "#201914"
  semantic:
    paid: "#2E7D5B"
    overdue: "#D9A441"
typography:
  fonts:
    heading: "Nunito, sans-serif"
    body: "Nunito, sans-serif"
  weights:
    regular: 400
    bold: 700
    extrabold: 800
  sizes:
    heroAmount: "2.25rem"
    h1: "1.5rem"
    h2: "1.125rem"
    body: "0.9375rem"
    caption: "0.8125rem"
    micro: "0.75rem"
spacing:
  unit: "4px"
  scale:
    xs: "4px"
    sm: "8px"
    md: "16px"
    lg: "24px"
    xl: "32px"
radius:
  card: "16px"
  button: "14px"
  chip: "9999px"
  input: "12px"
---

# klipo — Design System & MVP Screen Flow

## 1. Visual Theme & Product Atmosphere
**klipo** es una PWA (*offline-first* en lectura y ultra simple) diseñada para dueños de PyMES que hoy llevan sus cobros recurrentes en libretas o mensajes sueltos.

- **Sensación visual:** Cálida, editorial, cercana y sin fricción bancaria fría. Cero gradientes, cero colores neón y cero sobrecarga visual.
- **Alcance estricto del MVP:** Únicamente **cobro de suscripciones** (planes, suscriptores, cobro en 2 pasos con QR CoDi / Pey, registro manual en efectivo y envío por WhatsApp). Quedan fuera del MVP: split de cuentas, apartados, abonos, lealtad y facturación.

---

## 2. Strict Color Palette (Única paleta autorizada)

No introducir colores adicionales fuera de estos **7 tokens exactos** (cualquier otra variación de gris, azul o blanco puro queda descartada para mantener la identidad de marca):

```yaml
colors:
  accent_primary: "#7A1E2B"   # Acento Principal · Botones · Logo · Selección activa · Estado Fallido
  hover_titles: "#4E121C"     # Hover de botones · Títulos de énfasis
  bg_secondary: "#FDF6E3"     # Fondo principal / Secundario (crema cálida)
  card_border: "#E8DCC0"      # Superficie suave de tarjetas · Bordes · Divisores · Estados inactivos/pendientes
  ink_text: "#201914"         # Texto principal · Montos · Íconos
  status_paid: "#2E7D5B"      # Pagado · Al corriente · Plan Activo
  status_overdue: "#D9A441"   # Atrasado · Vencido · Por vencer / Alerta
```

### Reglas estrictas de uso y contraste (WCAG)
- **Fondo y tarjetas:** El canvas base de todas las pantallas es `#FDF6E3`. Las tarjetas usan `#FDF6E3` con borde `1.5px solid #E8DCC0` (o relleno `#E8DCC0` al 35%–100% para diferenciar bloques de resumen/tarjetas elevadas e inputs). *(Excepción funcional única: el recuadro interior del código QR CoDi requiere contraste máximo para lectura de cámara).*
- **Vino (`#7A1E2B`) y Vino Oscuro (`#4E121C`):** Reservados para botones CTA principales (con texto en `#FDF6E3`, contraste `9.51:1`), logo `klipo`, borde de tarjeta seleccionada, estado `Fallido` y hover (`#4E121C`, contraste `13.64:1`). **Nunca** usar vino como fondo del Hero del Home.
- **Tinta (`#201914`):** Todo texto principal y montos (`16.08:1` sobre `#FDF6E3`). Para texto secundario o subtítulos (ej. fechas, etiquetas), usar `#201914` al `70%` de opacidad o en peso `Regular` más pequeño, sin introducir grises externos.
- **Ámbar (`#D9A441`):** Nunca usar `#D9A441` como texto pequeño directo sobre `#FDF6E3` (`2.09:1` de contraste). Usarlo como **relleno de chip/badge** con texto `#201914` (`7.71:1`), o como indicador acompañado de texto `#201914`.
- **Verde (`#2E7D5B`):** Exclusivo para `Pagado`, `Al corriente`, `Activo` y barra de progreso cobrado (`4.63:1` sobre `#FDF6E3`; texto `#FDF6E3` o `#FFFFFF` sobre fondo `#2E7D5B` si es badge sólido).
- **Estados siempre con texto + color:** Todo estado (`Pagado`, `Pendiente`, `Vencido`, `En mora`, `Fallido`) lleva etiqueta textual explícita, nunca solo un punto o color.

---

## 3. Typography

- **Familia única:** `Nunito` (Google Fonts).
  - `ExtraBold (800)`: Logo `klipo`, montos principales (`$4,800`), títulos `H1`.
  - `Bold (700)`: Títulos de sección (`H2`), nombres de planes/clientes, botones, badges de estado.
  - `Regular (400)`: Subtítulos, descripciones, fechas y notas informativas.
- **Números tabulares:** Usar `font-variant-numeric: tabular-nums` en todos los importes monetarios.

---

## 4. Layout & Core Components

- **Viewport base:** `390px` móvil (centrado hasta `440px` en pantallas grandes), padding horizontal `16px`.
- **Tarjetas:** `border: 1.5px solid #E8DCC0`, `border-radius: 16px`, fondo `#FDF6E3` o `#E8DCC0` (suave para tarjetas de resumen).
- **Botón primario:** Fondo `#7A1E2B`, hover `#4E121C`, texto `#FDF6E3` (`Nunito Bold`), altura `52px`, `border-radius: 14px`.
- **Botón secundario / cancelar:** Borde `1.5px solid #E8DCC0` (o `#7A1E2B` para acciones de respaldo), fondo `#FDF6E3`, texto `#201914` o `#7A1E2B`.
- **Navbar inferior fijo (siempre visible, no hace scroll):**
  - Fondo `#FDF6E3` con borde superior `1.5px solid #E8DCC0`.
  - Máximo **4 destinos + botón central destacado `+ Cobrar`**:
    - `Inicio` · `Planes` · **`+ Cobrar`** (botón circular/elevado `#7A1E2B`, texto/ícono `#FDF6E3`) · `Suscriptores` · `Cobros` *(según los destinos elegidos por el equipo dentro del límite de 4 + `Cobrar` al centro)*.

---

## 5. MVP Screen Flow (Pantallas Definidas)

```text
[1. Home Page]
   ├── Toca Hero / "Ver todos los movimientos..." ──▶ [Cobros / Movimientos] ──▶ [Detalle del Cobro]
   ├── Toca Chip Ámbar ("X atrasados") ───────────────▶ [Suscriptores (filtro: Atrasado)]
   ├── Toca "Ver más..." o Navbar "Planes" ───────────▶ [2. Suscripciones (Lista de planes)]
   │                                                          ├── Botón "+ Nuevo plan" ──▶ [Modal/Form Crear Plan]
   │                                                          └── Toca Plan ──▶ [3. Detalles de Plan]
   │                                                                                ├── "Editar" (inline)
   │                                                                                ├── Botón "Cobrar" en fila ──▶ [4. Cobrar (preseleccionado)]
   │                                                                                └── "+ Agregar suscriptor"
   └── Toca "+ Cobrar" (Navbar central) ──────────────▶ [4. Cobrar (Paso 1: Plan → Paso 2: Suscriptor)]
                                                              │ (Botón: Generar QR)
                                                              ▼
                                                        [5. QR Generado]
                                                              ├── Enviar por WhatsApp (CTA principal)
                                                              ├── Compartir / Copiar enlace
                                                              ├── Ver detalle del cobro
                                                              └── Volver al inicio ──▶ [1. Home Page]
```

### Pantalla 1: Home Page (`Inicio`)
1. **Encabezado:** Logo `klipo` (`Nunito ExtraBold`, `#7A1E2B`) a la izquierda, mes actual en texto (`Noviembre 2026`, sin selector en el MVP) e ícono de notificaciones/perfil a la derecha.
2. **Hero — Dinero cobrado este mes:** Tarjeta en `#FDF6E3` con borde `#E8DCC0` (sin vino). Monto grande cobrado (`$4,800`), subtítulo `de $7,200 esperados este mes` + barra de progreso (`#2E7D5B` sobre `#E8DCC0`), y fila inferior: `14 pagos cobrados · 6 por cobrar esta semana`.
   - *Estado vacío:* `$0` + `"Aún no hay cobros este mes. Genera tu primer cobro."` + botón a `Cobrar`.
3. **Alerta de atrasados (condicional):** Chip ámbar `#D9A441` con texto `#201914` (`3 suscriptores atrasados · $950 por cobrar`). Si hay 0 atrasados, **no mostrar nada**.
4. **Previsualización de planes (`Mis planes`):** Máximo 3 tarjetas ordenadas por ganancia del mes (mayor a menor). Muestran: nombre del plan, precio y periodicidad (`$350 / mes`), `8 suscriptores activos` y ganancia del mes a la derecha (`$2,800`). Si un plan tiene 0 suscriptores, se muestra con `$0` al final (no se oculta). Enlace final: `Ver más...`.
   - *Estado vacío:* Tarjeta `"Crea tu primer plan"` + botón para crear plan.
5. **Últimos movimientos:** Máximo 5 recientes (`Cliente`, `Plan · Periodicidad`, `Fecha y hora`, `Monto`, badge de estado: `Pagado` `#2E7D5B`, `Pendiente` `#201914`/`#E8DCC0`, `Fallido` `#7A1E2B`, `Vencido` `#D9A441` + `#201914`). Tocar abre detalle del cobro (`numRef`, reenviar WhatsApp, marcar pagado manualmente en efectivo). Al final: `Ver todos los movimientos...`.
6. **Navbar inferior fijo.**

### Pantalla 2: Suscripciones (Lista de planes)
*Se abre desde `Ver más...` en Home o `Planes` en el navbar.*
1. **Encabezado:** Botón `←` a Home a la izquierda, título `Suscripciones`, botón chico `+ Nuevo plan` a la derecha (`#7A1E2B`, texto `#FDF6E3`).
2. **Resumen del mes (arriba de la lista):** Tarjeta de resumen con `Total cobrado este mes: $X,XXX`, `Esperado este mes: $Y,YYY`, `Por cobrar: $Z,ZZZ`. *(Si esperado es `$0` por no haber planes, ocultar esta tarjeta).*
3. **Lista completa de planes:** Buscador `Buscar plan...` arriba + tarjetas ordenadas por ganancia del mes (mayor a menor). Cada tarjeta muestra:
   - Nombre del plan (grande), precio y periodicidad (`$350 / mes`), descripción corta opcional (`Acceso al gimnasio + clases`), `8 suscriptores activos` (y si hay, `2 inactivos`).
   - Desglose de dinero a la derecha: `Ganancia del mes: $1,200`, `Cobrado / Esperado: $1,200 de $1,500`, `Por cobrar: $300`.
   - Badge en ámbar `#D9A441` (texto `#201914`): `⚠ 2 atrasados` (solo si hay > 0) y `Próximo cobro: 28 nov`.
   - Al tocar una tarjeta abre **Detalles de Plan**.
4. **Estado vacío:** Si no hay planes, tarjeta centrada `"Aún no tienes planes."` + `"Crea tu primer plan para empezar a cobrar suscripciones."` + botón vino `Crear plan`.
5. **Navbar inferior fijo** (con `Planes` activo).

### Pantalla 3: Detalles de Plan
*Se abre al tocar un plan en `Suscripciones` o en el `Home`.*
1. **Encabezado:** Botón `←` a `Suscripciones`, título `Detalles de plan`, botón `Editar` a la derecha (en modo edición cambia a `Guardar` en `#7A1E2B` y `Cancelar` en `#E8DCC0`/`#201914`).
2. **Información del plan (modo lectura):**
   - Tarjeta principal: Nombre (`Gym Fit — Mensual`), Precio y periodicidad (`$350 / mes`), Descripción, `Creado el 10 nov 2026`, Estado `Activo` (`#2E7D5B`) o `Inactivo` (`#E8DCC0`/`#201914`).
   - Tarjeta de resumen económico del plan: `Ganancia de este mes`, `Cobrado / Esperado este mes`, `Por cobrar este mes`, `Suscriptores activos`, `Atrasados` (en ámbar, solo si hay).
3. **Modo edición (inline al tocar `Editar`):**
   - Editables: Nombre, Precio, Periodicidad, Descripción, Estado `Activo / Inactivo` (no se borran planes con historial).
   - Nota debajo de botones: *"Si cambias el precio, solo se aplicará a los próximos cobros."*
4. **Clientes suscritos a este plan (`Suscriptores (N)`):**
   - Buscador `Buscar suscriptor...`.
   - **Orden obligatorio:** primero **Atrasados**, luego **Por vencer**, luego **Al corriente**.
   - Cada fila muestra: Nombre del cliente, badge de estado (`Al corriente`, `Por vencer`, `Vencido`, `En mora`), último pago (`Pagó 1 nov · $350`), próximo vencimiento (`Vence 28 nov`), monto a la derecha, y botón chico **`Cobrar`** en clientes atrasados o por vencer (abre `Cobrar` preseleccionado).
   - Al final: botón `+ Agregar suscriptor` (nombre, teléfono/WhatsApp, fecha de inicio). Estado vacío si 0 suscriptores (`"Aún no hay suscriptores en este plan."` + botón `Agregar suscriptor`).

### Pantalla 4: Cobrar (Flujo en 2 pasos)
*Se abre desde el botón central `+ Cobrar` o desde el detalle de un plan/suscriptor (preseleccionado).*
1. **Paso 1 (`Paso 1 de 2 · Elige el plan`):** Lista de tarjetas por plan (no *dropdown*). La seleccionada usa borde `#7A1E2B` + palomita.
2. **Paso 2 (`Paso 2 de 2 · Elige al suscriptor`):** Campo `Buscar suscriptor...` + lista filtrada de suscriptores del plan con estado (`Al corriente`, `Por vencer`, `Vencido`, `En mora`) y fecha (`Vence 28 nov`).
3. **Resumen del cobro (siempre visible antes del CTA):** Cliente, Plan + periodicidad, Monto fijo (`$350` en `Nunito ExtraBold`), Concepto automático (`Suscripción {Plan} - {Mes}`), Método (`CoDi / Pey`).
4. **Botón CTA:** **`Generar QR`** (`#7A1E2B`, texto `#FDF6E3`). Deshabilitado en `#E8DCC0` con texto `#201914` mientras falte plan o suscriptor (`"Elige un plan y un suscriptor para continuar"`).

### Pantalla 5: QR Generado (`Cobro generado`)
1. **Encabezado:** Título `Cobro generado` o `QR de pago`, y botón `Cerrar` / `×` (vuelve a Home dejando el cobro como `Pendiente`).
2. **QR CoDi:** Tarjeta centrada con el código QR grande + texto `Sin vencimiento · El cliente lo aprueba en su app bancaria`. Sin cuenta regresiva.
3. **Datos del cobro y estado en vivo:** Monto grande, Cliente, Plan + periodicidad, Concepto, Método (`CoDi / Pey`), y estado reactivo: `Esperando pago...` → cambia automático vía webhook a `Pagado` (`#2E7D5B`) con fecha/hora, o `Fallido` (`#7A1E2B`) con `Reintentar`.
4. **Botones de acción en orden:**
   1. **`Enviar por WhatsApp`** (Principal `#7A1E2B`, texto `#FDF6E3`).
   2. **`Compartir / Copiar enlace`** (Secundario borde `#E8DCC0`).
   3. **`Ver detalle del cobro`** (Terciario — abre `numRef`, reenviar WhatsApp o marcar pagado en efectivo).
   4. **`Volver al inicio`** (Enlace/texto).
