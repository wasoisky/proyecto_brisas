# Módulo Reportes — Brisas de Pacandé

Archivo de seguimiento de sesiones para el módulo `reportes/`.

---

## Estado general

| Vista | URL | Estado |
|---|---|---|
| Dashboard | `/reportes/` | ✅ operativo |
| Ventas consolidadas | `/reportes/ventas/` | ✅ operativo |
| Exportar Excel | `/reportes/ventas/exportar/` | ✅ operativo |
| Descuadres (manual + automático) | `/reportes/descuadres/` | ✅ operativo — detección automática HU-13, sesión 2026-08-30 |
| Créditos pendientes | `/reportes/creditos/` | ✅ operativo |
| **PDF export** | `/reportes/ventas/pdf/` | ✅ implementado — sesión 2026-06-10 |

---

## Archivos principales

```
reportes/
  views.py              — ReportesDashboardView, VentasConsolidadasView,
                          ExportarVentasExcelView, ExportarVentasPDFView,
                          Descuadre* (incl. DetectarDescuadresView), Credito*
  urls.py               — app_name='reportes', 10 rutas
  forms.py              — DescuadreForm, FiltroVentasForm
  models.py             — Descuadre (TipoDescuadre choices, es_automatico)
  detector.py            — detectar_pv/vi/ac + ejecutar_deteccion (HU-13)
  management/commands/
    detectar_descuadres.py — wrapper de ejecutar_deteccion para cron/manual
  tests.py               — 25 tests (detector, vista, command, B-01, exports)
  templates/reportes/
    dashboard.html      — 6 tarjetas + accesos rápidos + exportaciones + botón "Detectar descuadres"
    ventas.html         — filtros + tablas por producto/dist/pago + botón Excel/PDF
    descuadres.html     — badge "Automático" para hallazgos de HU-13
    creditos.html
```

---

## Sesión 2026-06-10 — Bug dashboard + PDF export

### Bug dashboard identificado

**Síntoma:** `alertas_insumos` se calcula en `ReportesDashboardView.get_context_data()`
(línea 47–50 de `views.py`) pero **nunca se renderiza** en `dashboard.html`.
El template solo muestra 4 tarjetas: producción, ventas, créditos, descuadres.
La variable `planillas_pendientes` tampoco tiene tarjeta propia (solo aparece en la lista de accesos rápidos).

**Fix propuesto:** Agregar tarjeta de alertas de insumos (stock ≤ 0) y opcionalmente
una de planillas pendientes de validación al dashboard.

### PDF export — plan

- Ruta: `GET /reportes/ventas/pdf/?fecha_desde=…&fecha_hasta=…`
- Vista: `ExportarVentasPDFView` en `views.py`
- Librería: **ReportLab** (ya en stack aprobado; no requiere wkhtmltopdf)
- Contenido del PDF:
  - Encabezado: logo texto "Brisas de Pacandé", período, fecha de generación
  - Tabla: igual que Excel (Fecha, Distribuidor, Cliente, Producto, Cant, Dev, P.Unit, Subtotal, Pago)
  - Pie: totales por producto y gran total
- Botón en `ventas.html` junto al botón Excel
- Botón en `dashboard.html` sección Exportaciones

### Tareas sesión actual

- [x] Bug 1 — `views.py:49`: `stock_actual__lte=0` → `stock_actual__lte=F('stock_minimo')` + import F
- [x] Bug 2 — `dashboard.html`: añadir tarjeta `alertas_insumos` (era fantasma en contexto)
- [x] Dashboard: añadir tarjeta `planillas_pendientes` + refactor a 6 tarjetas col-md-4
- [x] Instalar ReportLab 4.5.1
- [x] `ExportarVentasPDFView` en `views.py` (ReportLab, A4 horizontal, tabla + resumen)
- [x] URL `ventas/pdf/` en `urls.py`
- [x] Botón PDF en `ventas.html` junto a botón Excel
- [x] Botón PDF en `dashboard.html` sección Exportaciones
- [x] `manage.py check` — 0 errores

---

## Sesión 2026-08-30 — B-02, HU-13 (detección automática) y primeros tests

### B-02 — URL hardcodeada en `creditos.html`

Corregido. El JS ahora arma la acción del form con
`{% url 'reportes:credito_pagar' pk=999999 %}` y reemplaza ese placeholder
por el pk real (`urlPagarBase.replace('999999', pk)`), en vez de tener
`` `/reportes/creditos/${pk}/pagar/` `` escrito a mano.

### HU-13 — Detección automática de descuadres

El documento de tesis (§11.2, Tabla 17) exige que el sistema "compare las
cantidades producidas, vendidas y disponibles, y alerte cuando exista una
diferencia" e "indique la magnitud y el origen probable". Antes de esta
sesión, `Descuadre` era 100% registro manual (`DescuadreCreateView` +
`DescuadreForm`) — no cumplía el criterio de aceptación literal.

**Diseño (`reportes/detector.py`):**

| Función | Compara | Umbral / criterio |
|---|---|---|
| `detectar_pv(desde, hasta)` | Producción vs ventas netas del periodo, por producto | `vendido > producido` → siempre CRÍTICO (imposible físicamente). `producido > vendido`: <5% no genera nada (inventario en tránsito normal), 5–15% LEVE, >15% MODERADO |
| `detectar_vi(fecha_corte)` | "Disponible" = producido acumulado histórico − vendido acumulado histórico, por producto, hasta la fecha de corte | Si es negativo → CRÍTICO. No existe modelo de stock de producto terminado; se calcula al vuelo en vez de leerse de una tabla |
| `detectar_ac(desde, hasta)` | Conservación del conteo físico de activos retornables (BOT/CAN): total (`MovimientoActivo.total`) al INI de `desde` vs al FIN de `hasta` | Cualquier diferencia ≠ 0 genera hallazgo (MODERADO si ≤5 unidades, CRÍTICO si mayor) |

**Importante para la sustentación:** `detectar_pv` y `detectar_vi` cubren
literalmente los 3 términos de HU-13 (producidas, vendidas, disponibles).
`detectar_ac` **no es un requisito textual de HU-13** — reutiliza la
categoría `Descuadre.tipo = 'AC'` que ya existía en el modelo desde antes de
esta sesión, y es una verificación de calidad adicional sobre la
consistencia interna del módulo de activos. No se cruza contra `Entrega`
porque el intercambio de botellones es mano a mano por entrega individual
(regla de negocio §9.7) sin registro por evento — solo hay conteos
agregados diarios en `MovimientoActivo`, así que un cruce con ventas sería
una suposición, no una comparación de datos reales.

**Disparo (sin Celery/cron nuevo):**
- Botón "Detectar descuadres (mes en curso)" en `dashboard.html` → POST a
  `reportes:descuadre_detectar` (`DetectarDescuadresView`, SOLO_ADMIN),
  `detectado_por=request.user`.
- `python manage.py detectar_descuadres [--fecha-desde] [--fecha-hasta]
  [--usuario]` — mismo servicio (`ejecutar_deteccion`), pensado para un cron
  del hosting a futuro sin tocar código. Sin `--usuario`, usa el primer
  ADMIN activo; falla con `CommandError` si no hay ninguno.

**Modelo:** se agregó `Descuadre.es_automatico` (bool, default False,
migración `0002_descuadre_es_automatico`) para distinguir los detectados
del sistema en la lista (badge "Automático" en `descuadres.html`). Se crean
directo (no hay estado "propuesto" separado) — el admin los revisa y
resuelve igual que los manuales.

**Deduplicación:** `ejecutar_deteccion` no repite un hallazgo automático sin
resolver que ya describe el mismo problema (mismo tipo, fecha y
descripción exacta); si ese descuadre anterior ya fue resuelto, sí se
vuelve a crear ante el mismo problema (puede ser recurrente).

### Tests — primera cobertura real del módulo

`reportes/tests.py` no tenía ningún test real (solo el boilerplate de
Django). Esta sesión agregó 25 tests:

- `DetectarPVTests` (7), `DetectarVITests` (3), `DetectarACTests` (3),
  `EjecutarDeteccionTests` (3) — lógica pura de `detector.py`.
- `DetectarDescuadresViewTests` (2), `DetectarDescuadresCommandTests` (3) —
  integración de la vista y el management command.
- `AlertasInsumosDashboardTests` (2) — regresión de B-01 (ya corregido en
  sesión anterior, sin cobertura hasta ahora).
- `ExportarVentasSmokeTests` (2) — export Excel/PDF ya funcionaban
  (verificado manualmente en 2026-06-10) pero no tenían prueba
  automatizada; ahora hay un smoke test de status/content-type para cada
  uno.

`python manage.py test reportes` → 25/25 en verde. Suite completa del
proyecto (`python manage.py test`) → 90/90 en verde.

### Tareas de esta sesión

- [x] B-02 — URL hardcodeada corregida con `{% url %}`
- [x] `Descuadre.es_automatico` + migración
- [x] `reportes/detector.py` — `detectar_pv`, `detectar_vi`, `detectar_ac`, `ejecutar_deteccion`
- [x] `DetectarDescuadresView` + URL + botón en dashboard
- [x] `management/commands/detectar_descuadres.py`
- [x] Badge "Automático" en `descuadres.html`
- [x] 25 tests nuevos (detector, vista, command, B-01, export Excel/PDF)
- [x] `manage.py check` y suite completa del proyecto en verde

---

## Backlog futuro

- Gráficas Chart.js en ventas (barras por producto, línea por semana)
- PDF resumen mensual ejecutivo (1 página con KPIs)
- PDF descuadres para archivo físico
- Filtro de ventas por producto en la vista consolidada
- Si en el futuro se agrega un vínculo real entre `Entrega` y
  `ActivoRetornable` (registro de intercambio de botellón por entrega),
  reconsiderar `detectar_ac` para cruzar contra clientes en vez de solo
  verificar conservación interna del conteo
