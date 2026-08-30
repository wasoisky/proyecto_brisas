# Módulo Activos — Brisas de Pacandé

Archivo de seguimiento de sesiones para el módulo `activos/`.

---

## Estado general

| Vista | URL | Estado |
|---|---|---|
| Dashboard | `/activos/` | ✅ operativo |
| Historial de movimientos | `/activos/movimientos/` | ✅ operativo |
| Registrar movimiento | `/activos/movimientos/nuevo/` | ✅ operativo |
| Detalle de movimiento | `/activos/movimientos/<pk>/` | ✅ operativo — ahora incluye bajas detalladas |
| Registrar baja detallada | `/activos/movimientos/<pk>/bajas/nueva/` | ✅ nuevo — sesión 2026-08-30 |

---

## Archivos principales

```
activos/
  models.py             — ActivoRetornable, MovimientoActivo, BajaActivo [NUEVO]
  views.py               — ActivosDashboardView, MovimientoListView, MovimientoCreateView,
                           MovimientoDetailView, BajaActivoCreateView [NUEVO]
  forms.py               — MovimientoActivoForm, BajaActivoForm [NUEVO]
  urls.py                 — app_name='activos', 5 rutas
  admin.py                — ActivoRetornable, MovimientoActivo, BajaActivo [NUEVO]
  tests.py                — 11 tests (MovimientoActivoModelTests, BajaActivoModelTests,
                            BajaActivoFormTests, BajaActivoViewTests)
  templates/activos/
    dashboard.html
    movimiento_list.html
    movimiento_form.html
    movimiento_detail.html — ahora lista bajas + formulario inline de alta
```

---

## Sesión 2026-08-30 — HU-07: bajas individuales con motivo (TDD)

### Contexto del hallazgo

Auditoría contra el documento de tesis (`docs/ALINEACION_DOCUMENTO_DESARROLLO.md` §3.6):
HU-07 pide registrar cada baja de envases/embalajes con *"tipo, cantidad, motivo y
fecha"*. `MovimientoActivo.cantidad_baja` era solo un contador agregado por jornada
(INI/FIN), sin motivo por baja individual.

### Decisión de diseño

Se agregó `BajaActivo` como modelo independiente, **no** se modificó
`MovimientoActivo.cantidad_baja` (se mantiene el conteo agregado tal cual, para no
romper el formulario de doble registro diario ni el dashboard existentes):

```python
class BajaActivo(models.Model):
    class Motivo(models.TextChoices):
        ROTURA = 'ROT', 'Rotura'
        PERDIDA = 'PER', 'Pérdida'
        ROBO = 'ROB', 'Robo'
        DETERIORO = 'DET', 'Deterioro'
        OTRO = 'OTR', 'Otro'

    movimiento = models.ForeignKey(MovimientoActivo, on_delete=models.CASCADE, related_name='bajas')
    cantidad = models.PositiveIntegerField()
    motivo = models.CharField(max_length=3, choices=Motivo.choices, default=Motivo.ROTURA)
    descripcion = models.TextField(blank=True)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='bajas_activos')
    creado_en = models.DateTimeField(auto_now_add=True)
```

**Por qué FK a `MovimientoActivo` (CASCADE) en vez de campos `fecha`/`tipo_activo`
propios:** sigue exactamente el patrón ya validado de `Averia` en distribución
(FK a `Planilla` con CASCADE, sin duplicar la fecha de la planilla). `fecha` y
`tipo_activo` se leen vía `baja.movimiento.fecha` / `baja.movimiento.tipo_activo`,
evitando datos redundantes que puedan desincronizarse.

**Por qué no se valida `sum(bajas.cantidad) == movimiento.cantidad_baja`:** fuera de
alcance de esta sesión — el conteo agregado sigue siendo la fuente de verdad rápida
para el dashboard; `BajaActivo` es el detalle auditable. Si se prioriza más adelante,
agregar la validación cruzada en `MovimientoActivoForm.clean()` o una señal
`post_save`.

**Motivo por defecto "Rotura":** replica la regla de negocio ya definida para
`Averia` en `CLAUDE.md` §9.8 ("Averías: se registran con motivo predeterminado
'rotura'"), extendida aquí a bajas de activos.

### Ciclo TDD seguido

1. **RED** — tests de `MovimientoActivoModelTests` (unique_together, total) y
   `BajaActivoModelTests`/`FormTests`/`ViewTests` escritos primero; fallo confirmado
   por `ImportError: cannot import name 'BajaActivo'`.
2. **GREEN** — modelo `BajaActivo` + migración `0002_bajaactivo` → tests de modelo
   en verde.
3. **RED** — tests de form/vista fallan por `BajaActivoForm`/URL `baja_create`
   inexistentes.
4. **GREEN** — `BajaActivoForm`, `BajaActivoCreateView`, ruta
   `movimientos/<movimiento_pk>/bajas/nueva/`, listado + formulario inline en
   `movimiento_detail.html`.
5. Suite completa de `activos`: **11/11 tests en verde**.

### Tests agregados (`activos/tests.py`)

- `MovimientoActivoModelTests` (3): unique_together lanza `IntegrityError`, mismo
  día con distinto momento no choca, `total` suma los 4 estados
- `BajaActivoModelTests` (3): motivo por defecto es "Rotura", `__str__` incluye
  cantidad y motivo, se borra en cascada con el movimiento
- `BajaActivoFormTests` (2): válido con datos mínimos, rechaza cantidad 0
- `BajaActivoViewTests` (3): crea baja y redirige al detalle, el detalle lista las
  bajas registradas, un usuario DIST no puede registrar bajas (redirige, no crea)

### Verificación de no-regresión

- `python manage.py check` — 0 errores
- `python manage.py test activos` — 11/11 en verde
- Suite completa del proyecto corrida en paralelo con otras sesiones activas
  (usuarios/producción/distribución/reportes) — el único fallo observado
  (`usuarios.tests.UsuarioAdminTests.test_rol_es_readonly_al_editar_su_propio_usuario`)
  es de la sesión de usuarios (U-03 en curso), no relacionado con este módulo.

---

## Backlog futuro

- [ ] Validación cruzada opcional: `sum(bajas.cantidad)` vs `movimiento.cantidad_baja`
- [ ] Filtro por motivo en el historial de movimientos
- [ ] Exportar bajas a Excel/PDF (mismo patrón que reportes de ventas)
