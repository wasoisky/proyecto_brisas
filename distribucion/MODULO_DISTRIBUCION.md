# Módulo Distribución — Brisas de Pacandé

Archivo de seguimiento de sesiones para el módulo `distribucion/`.

---

## Estado general

| Vista | URL | Estado |
|---|---|---|
| Lista de clientes | `/distribucion/clientes/` | ✅ operativo |
| Crear/editar cliente | `/distribucion/clientes/nuevo/`, `/<pk>/editar/` | ✅ operativo |
| Lista de planillas (admin) | `/distribucion/planillas/` | ✅ operativo |
| Detalle de planilla | `/distribucion/planillas/<pk>/` | ✅ operativo |
| Validar planilla | `/distribucion/planillas/<pk>/validar/` | ✅ operativo |
| Selector de ruta (DIST) | `/distribucion/ruta/` | ✅ operativo |
| Trabajo de ruta (DIST) | `/distribucion/ruta/<pk>/` | ✅ operativo |
| API planilla activa | `/distribucion/api/planilla-activa/` | ✅ operativo |
| API crear entrega | `/distribucion/api/entregas/` | ✅ operativo |
| API crear avería | `/distribucion/api/averias/` | ✅ operativo |
| API clientes (con precios) | `/distribucion/api/clientes/` | ✅ operativo |
| API productos | `/distribucion/api/productos/` | ✅ operativo |

---

## Archivos principales

```
distribucion/
  models.py       — Cliente, PrecioPorCategoria, Planilla, Entrega, Averia, Credito
  forms.py        — ClienteForm, PrecioPorCategoriaForm, PlanillaForm, EntregaForm, AveriaForm
  views.py        — Cliente*, Planilla*, PlanillaRutaListView, PlanillaRutaView
  api_views.py    — PlanillaActivaAPIView, EntregaCreateAPIView, AveriaCreateAPIView,
                    ClienteListAPIView, ProductoListAPIView (permiso PermisoDist: ADMIN/DIST)
  serializers.py  — PlanillaSerializer, EntregaSerializer, AveriaSerializer,
                    ClienteConPreciosSerializer, ProductoSerializer, PrecioPorCategoriaSerializer
  urls.py         — app_name='distribucion', 12 rutas (7 vistas + 5 API)
  tests.py        — 20 tests (PrecioPorCategoriaTests, CreditoAutoGeneracionTests,
                    APIDistribucionTests) — todos en verde
  templates/distribucion/
    cliente_list.html, cliente_form.html
    planilla_list.html, planilla_detail.html
    planilla_ruta_list.html, planilla_ruta.html   — móvil-first, sync localStorage+Axios
```

---

## Sesión 2026-08-30 — Tests reales + fix de regla de negocio central

Motivada por directriz del usuario (relayada por la sesión general del proyecto)
tras la auditoría de alineación documento↔código: `distribucion/tests.py` seguía
con el boilerplate de Django, sin ningún test propio.

### Bug encontrado por TDD (test primero, implementación después)

**Síntoma:** la regla de negocio "el precio es por categoría (REG/MAY), nunca
por cliente individual" (sección 9, regla 2 de `CLAUDE.md`) solo se cumplía en
el **cliente**: `planilla_ruta.html` autocompleta `#f-precio` con JS a partir de
`PRECIOS` (mapa cliente→producto→precio construido desde `PrecioPorCategoria`),
pero el campo es un `<input type="number">` editable, y ni `EntregaForm`
(`views.py` — flujo web) ni `EntregaSerializer` (`api_views.py` — sync API)
validaban `precio_unitario` contra `PrecioPorCategoria` en el servidor. Un valor
manipulado en el POST/JSON se guardaba tal cual.

**Fix (D-01):**

| Archivo | Cambio |
|---|---|
| `forms.py` | `EntregaForm.clean()` busca `PrecioPorCategoria` por `(cliente.categoria, producto)`, sobrescribe `cleaned_data['precio_unitario']` con el valor vigente y rechaza el formulario si no existe precio configurado para esa combinación |
| `serializers.py` | `EntregaSerializer.validate()` — misma lógica, para que la API de sincronización quede protegida igual que el flujo web |

Ambos ignoran el `precio_unitario` recibido y lo reemplazan por el de
`PrecioPorCategoria`; ya no es un dato de confianza del cliente.

### Tests agregados (`distribucion/tests.py`)

20 tests en 3 clases — todos en verde:

- **`PrecioPorCategoriaTests`** (5): dos clientes de la misma categoría comparten
  precio; categorías distintas pueden tener precios distintos; `unique_together
  (categoria, producto)` se respeta; `EntregaForm` ignora un `precio_unitario`
  manipulado y usa el de la categoría (test que expuso D-01); `EntregaForm`
  rechaza productos sin precio configurado para la categoría del cliente.
- **`CreditoAutoGeneracionTests`** (4): `Credito` se crea automáticamente con
  `modalidad_pago='CRE'` (monto/saldo/pagado correctos); no se crea con
  `EFE` ni `NEQ`; `Credito.entrega` es estrictamente 1:1 (`IntegrityError` al
  duplicar).
- **`APIDistribucionTests`** (11): cobertura de los 5 endpoints DRF —
  `planilla-activa` (GET 404 sin planilla, POST crea, POST es idempotente el
  mismo día), permisos (`PROD` → 403, anónimo → 401/403), `entregas` (crea
  `Credito` si `CRE`, 400 con datos inválidos), `averias` (crea correctamente),
  `clientes` (incluye precios de su categoría, excluye inactivos), `productos`
  (excluye inactivos).

### Nota — auditoría documento de tesis

La auditoría de `docs/ALINEACION_DOCUMENTO_DESARROLLO.md` no encontró gaps de
código específicos de distribución frente al documento de tesis; el módulo es
de los mejor alineados. El único hallazgo (§5.1 dice "precios diferenciados
por cliente" de forma ambigua) es una corrección de redacción del documento,
no de código — la implementación real (por categoría) es la correcta según la
regla de negocio §9.2.

### Comandos usados

```bash
./venv/Scripts/python.exe manage.py test distribucion --keepdb -v2
./venv/Scripts/python.exe manage.py test --keepdb -v2   # suite completa, sin regresiones
```

---

## Backlog futuro

- [ ] Refactor: la creación de `Credito` está duplicada entre
      `views.py::PlanillaRutaView.post` y `serializers.py::EntregaSerializer.create`
      (mismo bloque `if modalidad_pago == CREDITO: Credito.objects.create(...)`).
      Candidato a moverse a un método del modelo `Entrega` o a una señal
      `post_save`, para que ambos flujos (web y API) queden sincronizados por
      construcción y no por duplicación manual.
- [ ] B-02: URL hardcodeada en `reportes/creditos.html` referencia créditos de
      distribución — corregirla usando `{% url %}` (fix vive en `reportes/`,
      pero el dato es de este módulo).
- [ ] Considerar mover el descubrimiento de precio (`PrecioPorCategoria`) del
      formulario/serializer a un método reutilizable (p. ej.
      `PrecioPorCategoria.objects.precio_vigente(cliente, producto)`) si se
      necesita la misma lógica en un tercer lugar.
