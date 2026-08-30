# Módulo Producción — Brisas de Pacandé

Archivo de seguimiento de sesiones para el módulo `produccion/`.

---

## Estado general

| Vista | URL | Estado |
|---|---|---|
| Lista de productos | `/produccion/productos/` | ✅ operativo |
| Crear / editar producto | `/produccion/productos/nuevo/`, `/productos/<pk>/editar/` | ✅ operativo |
| Activar/desactivar producto | `/produccion/productos/<pk>/toggle/` | ✅ operativo |
| Lista de insumos | `/produccion/insumos/` | ✅ operativo — filtro de alertas de stock |
| Crear / editar insumo | `/produccion/insumos/nuevo/`, `/insumos/<pk>/editar/` | ✅ operativo |
| Activar/desactivar insumo | `/produccion/insumos/<pk>/toggle/` | ✅ operativo |
| Registro de producción | `/produccion/registro/` | ✅ operativo — formset de consumo + verificación de stock atómica |
| Detalle de producción | `/produccion/registro/<pk>/` | ✅ operativo |
| Compras de insumo | `/produccion/compras/` | ✅ operativo — incrementa stock atómicamente |
| Recetas por producto | `/produccion/recetas/`, `/recetas/<pk>/editar/` | ✅ operativo |
| API receta (JSON) | `/produccion/api/receta/<producto_id>/` | ✅ operativo — precarga del formset de consumo |
| Kardex de insumo | `/produccion/insumos/<pk>/kardex/` | ✅ operativo — **bug crítico corregido sesión 2026-08-30** (ver abajo) |
| Regalías (producto sin cobro) | `/produccion/regalias/`, `/regalias/nueva/` | ✅ implementado — sesión 2026-08-30 (ver abajo) |

---

## Archivos principales

```
produccion/
  models.py       — Producto, Insumo, Produccion, ConsumoInsumo, CompraInsumo,
                    RecetaProducto, Regalia
  views.py        — CRUD de Producto/Insumo/Produccion/CompraInsumo/RecetaProducto/Regalia,
                    InsumoKardexView, receta_api (JSON)
  forms.py        — ProductoForm, InsumoForm, ProduccionForm, CompraInsumoForm,
                    ConsumoInsumoFormSet, RecetaProductoFormSet, RegaliaForm
  urls.py         — app_name='produccion', 17 rutas
  admin.py
  tests.py        — 12 tests (VerificacionStockProduccionTests, CompraInsumoStockTests,
                    KardexInsumoTests, RecetaProductoTests, RegaliaTests)
  migrations/     — 0001_initial, 0002_quitar_unique_presentacion, 0003_receta_producto,
                    0004_regalia
  templates/produccion/
    producto_list.html, producto_form.html
    insumo_list.html, insumo_form.html
    produccion_list.html, produccion_form.html, produccion_detail.html
    compra_list.html, compra_form.html
    receta_list.html, receta_form.html
    insumo_kardex.html
    regalia_list.html, regalia_form.html
```

---

## Sesión 2026-08-30 — Tests reales + bug crítico en kardex

Antes de esta sesión, `produccion/tests.py` tenía solo el boilerplate de Django
(0 tests reales) — el único módulo junto con `activos`/`distribucion` sin
bitácora propia ni pruebas.

### Bug encontrado por TDD: kardex crasheaba con 500 para cualquier insumo

**Síntoma:** `InsumoKardexView.get()` (`views.py`, línea ~376) construye el
queryset de salidas así:

```python
consumos = (
    ConsumoInsumo.objects
    .filter(insumo=insumo)
    .values(
        fecha=F('produccion__fecha'),
        cantidad=F('cantidad'),   # ← anota 'cantidad' con el mismo nombre
        ...                       #   que el campo real 'cantidad' del modelo
    )
    ...
)
```

Django 5.2 rechaza anotar un alias con el mismo nombre que un campo existente
del modelo: `ValueError: The annotation 'cantidad' conflicts with a field on
the model`. Esto ocurre en la construcción del queryset, **antes** de
evaluarlo — así que la vista crasheaba con 500 para cualquier insumo, incluso
sin ningún movimiento registrado. Nunca se detectó porque la única
verificación previa era `manage.py check` (no ejecuta queries).

**Fix:** `views.py` — pasar `'cantidad'` como argumento posicional de
`.values()` (selecciona el campo tal cual, sin anotarlo) en vez de
`cantidad=F('cantidad')`.

### Tests agregados (`produccion/tests.py`)

9 tests en 4 clases — todos en verde:

- `VerificacionStockProduccionTests` (3): stock insuficiente bloquea el
  guardado y no descuenta nada; stock suficiente guarda y descuenta
  correctamente; el límite exacto (stock == cantidad requerida) se acepta.
- `CompraInsumoStockTests` (1): registrar una compra incrementa `stock_actual`
  atómicamente.
- `KardexInsumoTests` (2): el saldo acumulado combina entradas (compras) y
  salidas (consumos) en orden cronológico; un insumo sin movimientos
  devuelve saldo 0 (regresión del bug de arriba).
- `RecetaProductoTests` (3): `unique_together(producto, insumo)` se respeta;
  `receta_api` devuelve las líneas de receta de un producto; un producto sin
  receta devuelve `{'receta': []}`.

### "Registro de regalías" — definido e implementado

Tabla 3 (§8.6.5) del documento de tesis mencionaba "registro de regalías" bajo
producción sin definirlo ni implementarlo — hallazgo de
`docs/ALINEACION_DOCUMENTO_DESARROLLO.md` §3.4. Se confirmó con el usuario:

- **Significado:** producto terminado entregado sin cobro (obsequio a
  cliente, cortesía institucional o promoción) — no es una venta, pero sí
  sale del producto terminado.
- **Decisión:** implementarlo ya, no documentar como excluido.

**Modelo `Regalia`** (`models.py`): `fecha`, `producto` (FK), `produccion`
(FK opcional al lote de origen — trazabilidad BPM Res. 2674/2013),
`cantidad`, `destinatario`, `motivo` (choices: promoción/obsequio/cortesía/
otro), `observaciones`, `registrado_por`. CRUD reducido a lista + creación
(mismo patrón minimalista que `CompraInsumo`, sin update/delete).

Nota: el sistema no lleva stock de producto terminado (`Producto` no tiene
`stock_actual`, a diferencia de `Insumo`), así que `Regalia` es un registro
de trazabilidad/auditoría, no descuenta ningún contador — igual que
`Produccion` en sí misma no se resta de ningún inventario.

Rutas: `/produccion/regalias/` (lista + filtros por producto/motivo/fecha),
`/produccion/regalias/nueva/`. Enlace agregado al sidebar
(`templates/includes/sidebar_nav.html`).

### Tareas sesión actual

- [x] Crear `produccion/MODULO_PRODUCCION.md`
- [x] Tests reales: verificación de stock, kardex, recetas
- [x] Fix del crash 500 en `InsumoKardexView` (anotación `cantidad` duplicada)
- [x] Confirmar con el usuario significado de "regalías" e implementar
- [x] Modelo `Regalia` + migración `0004_regalia` + CRUD + tests + sidebar
- [x] `manage.py test produccion` — 12/12 en verde
- [x] `manage.py check` — 0 errores

---

## Backlog futuro

- [ ] Ampliar cobertura de tests: `ProductoToggleActivoView`,
  `InsumoToggleActivoView`, filtros de listados (búsqueda, categoría, alertas)
- [ ] Revisar si otras vistas con `.values(campo=F('campo'))` tienen el mismo
  patrón de anotación duplicada (no se encontraron más casos en este módulo)
- [ ] Actualizar el documento de tesis (§8.6.5, Tabla 3) para reflejar la
  implementación real de "registro de regalías" (ver
  `docs/ALINEACION_DOCUMENTO_DESARROLLO.md` §3.4)
