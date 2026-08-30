# Módulo Reportes — Brisas de Pacandé

Archivo de seguimiento de sesiones para el módulo `reportes/`.

---

## Estado general

| Vista | URL | Estado |
|---|---|---|
| Dashboard | `/reportes/` | ✅ operativo — bug pendiente (ver abajo) |
| Ventas consolidadas | `/reportes/ventas/` | ✅ operativo |
| Exportar Excel | `/reportes/ventas/exportar/` | ✅ operativo |
| Descuadres | `/reportes/descuadres/` | ✅ operativo |
| Créditos pendientes | `/reportes/creditos/` | ✅ operativo |
| **PDF export** | `/reportes/ventas/pdf/` | ✅ implementado — sesión 2026-06-10 |

---

## Archivos principales

```
reportes/
  views.py              — ReportesDashboardView, VentasConsolidadasView,
                          ExportarVentasExcelView, Descuadre*, Credito*
  urls.py               — app_name='reportes', 9 rutas
  forms.py              — DescuadreForm, FiltroVentasForm
  models.py             — Descuadre (TipoDescuadre choices)
  templates/reportes/
    dashboard.html      — 4 tarjetas + accesos rápidos + exportaciones
    ventas.html         — filtros + tablas por producto/dist/pago + botón Excel
    descuadres.html
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

## Backlog futuro

- Gráficas Chart.js en ventas (barras por producto, línea por semana)
- PDF resumen mensual ejecutivo (1 página con KPIs)
- PDF descuadres para archivo físico
- Filtro de ventas por producto en la vista consolidada
