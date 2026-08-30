# CONTEXTO DE DESARROLLO — Sistema de Información Brisas de Pacandé
## Estado actualizado: 30 de agosto de 2026

---

## 1. Identidad del proyecto

| Campo | Detalle |
|---|---|
| **Proyecto** | Sistema de información web integrado — Brisas de Pacandé |
| **Tipo** | Trabajo de grado — Ingeniería de Sistemas |
| **Universidad** | Universidad Piloto de Colombia, Seccional Alto Magdalena |
| **Desarrollador** | Leonardo A. Rodríguez Morantes (individual) |
| **Empresa** | Envasadora y distribuidora de agua — Melgar, Tolima |
| **Cronograma** | Junio – Septiembre 2026 |
| **Metodología** | XP adaptada a desarrollador individual — una sesión por módulo |

---

## 2. Stack tecnológico (fijo — no sugerir alternativas)

| Capa | Tecnología |
|---|---|
| Backend | Python 3.13 + Django 5.2 LTS |
| API distribución | Django REST Framework |
| Base de datos | PostgreSQL 16 + Django ORM |
| Frontend | Django Templates + Bootstrap 5 + Bootstrap Icons |
| JS cliente | Vanilla JS + Axios (solo módulo distribución) |
| Almacenamiento offline | localStorage (distribución) |
| Autenticación | Django Auth + roles por campo `rol` en Usuario |
| PDF | ReportLab 5.0.1 (implementado — export de ventas, sesión 2026-06-10) |
| Excel | openpyxl (implementado) |
| Despliegue objetivo | Railway / Render / PythonAnywhere |

**NO usar:** React, Vue, FastAPI, MongoDB, Django 6.0 ni nada fuera de este stack.

---

## 3. Personas y roles

| Persona | Rol | Contexto de uso |
|---|---|---|
| Maximino | ADMIN | Todos los módulos — escritorio |
| César | PROD | Producción y activos — escritorio |
| Nicolás | DIST | Distribución en ruta — celular institucional, pierde señal ~4h/día en Boquerón y Chimbí |

Credenciales de prueba: `maximino` / `cesar` / `nicolas` — password: `brisas2024`

---

## 4. Estado actual — módulos completados

### ✅ Infraestructura base
- `config/settings.py` y `urls.py` configurados con login/logout y redirect por rol
- `ALLOWED_HOSTS` incluye `192.168.18.6` para pruebas en celular real
- Comando de datos de prueba: `python manage.py crear_datos_prueba` (o `--limpiar`)
- Arranque para red local: `python manage.py runserver 0.0.0.0:8000`

### ✅ Módulo usuarios
- Modelo: `Usuario(AbstractUser)` con campo `rol` (ADMIN/PROD/DIST) + `RegistroAcceso`
- CRUD completo de usuarios + gestión de contraseñas
- Mixin `RolRequiredMixin` aplicado a todas las vistas (no rehacer)
- Template tags personalizados en `usuarios/templatetags/`
- Log de accesos visible en `accesos.html`
- `usuarios/tests.py`: 22 tests (mixins, `AdminPasswordResetForm`, `UsuarioUpdateView`, `UsuarioAdmin`, `backup_bd`) — todos en verde
- **Backup de PostgreSQL**: `python manage.py backup_bd [--destino RUTA]` genera dump con `pg_dump -F c`; procedimiento de restauración (`pg_restore`) documentado en el docstring del comando y en [usuarios/MODULO_USUARIOS.md](usuarios/MODULO_USUARIOS.md) — cierra el riesgo crítico §13.3 del documento de tesis
- `UsuarioAdmin.has_change_permission()`/`has_delete_permission()` bloquean editar/borrar a un superusuario desde `/admin/` si quien lo intenta no es superusuario (U-07)
- Bitácora detallada de sesiones en [usuarios/MODULO_USUARIOS.md](usuarios/MODULO_USUARIOS.md); los 7 bugs de code review/seguridad (U-01 a U-07) quedaron resueltos — ver sección 6

### ✅ Módulo producción
- Modelos: `Producto`, `Insumo`, `Produccion`, `ConsumoInsumo`, `CompraInsumo`, `RecetaProducto`, `Regalia`
- CRUD completo con búsqueda y filtros en todos los listados
- Formset inline de consumo de insumos al registrar producción
- Verificación de stock antes de guardar (transacción atómica)
- **Kardex de insumos**: historial cronológico entradas/salidas con saldo acumulado
- **Recetas por producto**: cantidad de insumo por unidad producida + API JSON para precarga
- **Regalías**: producto terminado entregado sin cobro (obsequio/cortesía/promoción), con lote de origen opcional para trazabilidad BPM — implementa el requisito huérfano de §8.6.5 Tabla 3, ver decisión en sección 5
- Migraciones `0003_receta_producto`, `0004_regalia` aplicadas
- `produccion/tests.py`: 12 tests (verificación de stock atómica, compra incrementa stock, kardex, recetas, regalías) — todos en verde
- Bitácora detallada de sesiones en [produccion/MODULO_PRODUCCION.md](produccion/MODULO_PRODUCCION.md), incluye fix de bug crítico de kardex (500) — sesión 2026-08-30

### ✅ Módulo activos
- Doble registro diario (inicio y fin de jornada) con `UNIQUE(fecha, momento, tipo_activo)`
- Dashboard de activos con estado actual de botellones y canastillas
- CRUD `MovimientoActivo` con detalle
- **HU-07 resuelta**: `BajaActivo` — bajas individuales con motivo (rotura/pérdida/robo/deterioro/otro), FK a `MovimientoActivo`, listado y alta desde el detalle del movimiento; el contador agregado `cantidad_baja` se mantiene sin cambios
- `activos/tests.py`: 11 tests (unique_together, total, modelo/form/vista de `BajaActivo`) — todos en verde
- Bitácora detallada de sesiones en [activos/MODULO_ACTIVOS.md](activos/MODULO_ACTIVOS.md)

### ✅ Módulo distribución
- Modelos: `Cliente` (categoría REG/MAY), `PrecioPorCategoria`, `Planilla`, `Entrega`, `Averia`, `Credito`
- CRUD Clientes y Planillas (admin)
- Vista planilla de ruta para DIST (móvil-first)
- Múltiples planillas por día por distribuidor (constraint `unique_together` eliminado)
- **Sincronización híbrida**: localStorage + Axios — operación offline completa para Nicolás
- **API REST DRF**: 5 endpoints para sincronización
- Generación automática de `Credito` cuando `modalidad_pago = 'CRE'`
- `distribucion/tests.py`: 20 tests (`PrecioPorCategoria`, generación automática de `Credito`, los 5 endpoints DRF) — todos en verde
- Bitácora detallada de sesiones en [distribucion/MODULO_DISTRIBUCION.md](distribucion/MODULO_DISTRIBUCION.md), incluye fix D-01 (precio no validado en servidor) — sesión 2026-08-30

### ✅ Módulo reportes
- Dashboard admin: producción mes, ventas mes, créditos pendientes, alertas insumos (stock bajo mínimo), planillas pendientes, descuadres
- Ventas consolidadas con filtro por fechas y distribuidor
- **Export Excel** de ventas (openpyxl) con formato y autoajuste de columnas
- **Export PDF** de ventas (ReportLab, A4 horizontal) con resumen por producto y gran total — botones en dashboard y `ventas.html`
- Descuadres: registro, filtro por tipo/estado, marcar como resuelto
- Créditos pendientes: lista paginada + **pago parcial** desde modal
- Sin tests propios todavía (`reportes/tests.py` sigue con el boilerplate de Django, 0 tests reales) — ver backlog sección 7
- Bitácora de sesiones en [reportes/MODULO_REPORTES.md](reportes/MODULO_REPORTES.md)

### ✅ UI/UX — design system "Hydraulic Modernity"
- Sidebar navy `#1B2870` + contenido blanco, Inter font (Google Fonts CDN)
- Submenús con Bootstrap Collapse + chevron rotativo — el activo inicia expandido
- Sidebar móvil slide-in con backdrop semitransparente + botón X + auto-cierre al navegar
- Login rediseñado con tema claro en todos los dispositivos (panel branding solo en `lg+`)
- `--text-muted2: #64748b` (cumple WCAG AA ~4.6:1)
- Fechas en formato `d/m/Y` en toda la UI
- `flex-wrap gap-2` en todos los headers para que no se desborden en móvil
- Paginación global: `templates/includes/pagination.html`

---

## 5. Decisiones técnicas registradas

| Decisión | Motivo |
|---|---|
| Múltiples planillas/día → eliminar `unique_together(fecha, distribuidor)` | Operativa real: el camión y la moto hacen jornadas separadas |
| `PrecioPorCategoria` en vez de precio por cliente individual | Solo 2 categorías (REG/MAY), nunca precio individual |
| `RecetaProducto` añadido al modelo de producción | Necesario para precalcular consumos y escalar futuras órdenes |
| Paginación como include reutilizable | Evita duplicar el snippet en 8+ templates |
| `RolRequiredMixin` centralizado en `usuarios/mixins.py` | Single point of truth para control de acceso |
| `SOLO_ADMIN`, `ADMIN_PROD`, `ADMIN_DIST` como constantes de rol | Expresivo y fácil de cambiar |
| Design system "Hydraulic Modernity" — tema claro | Accesibilidad WCAG AA, usuarios sin experiencia digital |
| Sesión de trabajo por módulo | Mantener contexto acotado y commits coherentes |
| ReportLab (no WeasyPrint) para export PDF | Ya está en el stack aprobado y no requiere instalar wkhtmltopdf/GTK en Windows |
| Bitácora de sesión por módulo en `<app>/MODULO_<NOMBRE>.md` | Detalle línea por línea de bugs/tareas sin inflar este archivo; `CLAUDE.md` resume, el `MODULO_*.md` referenciado tiene el detalle |
| `pg_dump`/`pg_restore` vía `subprocess` en management command propio (no librería de terceros) | Ya están disponibles con cualquier instalación de PostgreSQL 16, sin dependencias nuevas; tests mockean `subprocess.run` para no requerir el binario en CI |
| `EntregaForm.clean()` / `EntregaSerializer.validate()` reemplazan `precio_unitario` por el de `PrecioPorCategoria`, ignorando el valor recibido en el POST/JSON | El precio solo se autocompletaba por JS en el cliente; nada validaba en servidor que respetara la categoría (regla 2, sección 9) — un valor manipulado se guardaba tal cual |
| "Regalías" = producto terminado entregado sin cobro (obsequio/cortesía/promoción); modelo `Regalia` no descuenta ningún contador de stock | Confirmado con el usuario (§8.6.5 Tabla 3 no lo definía). `Producto` no lleva `stock_actual` (a diferencia de `Insumo`), así que es un registro de trazabilidad, no un movimiento de inventario |

---

## 6. Bugs conocidos pendientes de corregir

**Resuelto:** B-01 (`reportes/views.py`) — `alertas_insumos` ya filtra contra `F('stock_minimo')`. Commit `6aff4ef`, sesión 2026-08-30.

**Resuelto:** Kardex de insumos (`produccion/views.py:376`) — `InsumoKardexView` crasheaba con 500 para cualquier insumo (incluso sin movimientos) porque anotaba `cantidad=F('cantidad')`, duplicando el nombre de un campo real del modelo (Django 5.2 lo rechaza). Detectado por TDD al escribir los tests de kardex, sesión 2026-08-30. Ver [produccion/MODULO_PRODUCCION.md](produccion/MODULO_PRODUCCION.md).

**Resuelto:** HU-07 (activos) — `MovimientoActivo.cantidad_baja` solo era un contador agregado sin motivo por baja. Se agregó `BajaActivo` (fecha/tipo heredados del `MovimientoActivo` vía FK, `cantidad`, `motivo` con default "Rotura", `descripcion`), siguiendo el mismo patrón de `Averia` en distribución. TDD, sesión 2026-08-30. Ver [activos/MODULO_ACTIVOS.md](activos/MODULO_ACTIVOS.md).

**Resuelto:** D-01 (distribución) — `precio_unitario` de una `Entrega` no se validaba en servidor contra `PrecioPorCategoria`; solo se autocompletaba por JS en `planilla_ruta.html`, así que un valor manipulado en el POST (web) o el JSON (API de sync) se guardaba tal cual, violando la regla "precio por categoría, nunca por cliente individual" (sección 9, regla 2). `EntregaForm.clean()` y `EntregaSerializer.validate()` ahora recalculan `precio_unitario` desde `PrecioPorCategoria` según `(cliente.categoria, producto)` y rechazan la operación si no hay precio configurado. Detectado por TDD al escribir los tests de distribución, sesión 2026-08-30. Ver [distribucion/MODULO_DISTRIBUCION.md](distribucion/MODULO_DISTRIBUCION.md).

**Resuelto:** U-01 a U-06 (`usuarios/`) — los 6 bugs de code review quedaron corregidos con TDD, sesión 2026-08-30: `UsuarioUpdateView.get_object()` ahora usa `get_object_or_404(..., is_superuser=False)` (cierra U-01 y U-05: GET/POST a un pk de superusuario devuelven 404 en vez de crashear o crear un usuario fantasma con username vacío); `AdminPasswordResetForm` recibe `usuario=` y lo pasa a `validate_password(p1, user=usuario)` (U-02); `UsuarioAdmin.get_readonly_fields()` bloquea el campo `rol` cuando el objeto editado es el propio usuario logueado, cerrando el bypass desde `/admin/` (U-03); `UsuarioUpdateView.form_valid()` consolida los dos guards de auto-protección en un solo bloque que solo usa `form.add_error` (U-04, U-06). Detalle en [usuarios/MODULO_USUARIOS.md](usuarios/MODULO_USUARIOS.md).

**Resuelto:** U-07 (`usuarios/admin.py`) — hallazgo de revisión de seguridad sobre el commit `6129d8a`, extiende U-03: `UsuarioAdmin` no impedía que un `is_staff=True` con permisos Django de `change_usuario`/`delete_usuario` editara o borrara a un superusuario vía `/admin/`. No explotable hoy (`maximino` no tiene esos permisos asignados) pero era protección accidental. `has_change_permission()`/`has_delete_permission()` ahora devuelven `False` cuando `obj.is_superuser` y quien pide el cambio no es superusuario. TDD, sesión 2026-08-30. Ver [usuarios/MODULO_USUARIOS.md](usuarios/MODULO_USUARIOS.md).

| # | Archivo | Descripción | Impacto |
|---|---|---|---|
| B-02 | `reportes/templates/reportes/creditos.html:116` | URL hardcodeada en JS: `` `/reportes/creditos/${pk}/pagar/` `` | Se rompe si cambia el prefijo de URL |

---

## 7. Pendiente — backlog priorizado

```
ALTA PRIORIDAD
  [ ] HU-13 (reportes): implementar detección automática de descuadres
      comparando producción/ventas/inventario. Hoy Descuadre es 100% registro
      manual (DescuadreCreateView) — no cumple el criterio de aceptación de
      la historia de usuario. Ver docs/ALINEACION_DOCUMENTO_DESARROLLO.md §3.2.
  [ ] B-02 Corregir URL hardcodeada en creditos.html JS        (10 min)
  [ ] Pruebas Django TestCase para reportes
      (usuarios, producción, activos y distribución ya tienen — ver sección 4)

MEDIA PRIORIDAD
  [ ] Bitácora de auditoría CRUD (RS-04, §5.1 y Tabla 19): declarada en el
      documento pero RegistroAcceso solo cubre login/logout, no operaciones
      de creación/modificación/eliminación sobre entidades de negocio. Decisión
      pendiente de consultar con el usuario: modelo genérico de auditoría con
      signals post_save/post_delete (afecta todos los módulos) vs. limitar el
      alcance declarado en el documento. No implementar sin esa decisión.
  [ ] Fixtures de datos reales (productos, clientes, precios actuales)
  [ ] Despliegue Railway / Render / PythonAnywhere
  [ ] Gráficas Chart.js en ventas, PDF resumen mensual ejecutivo (ver reportes/MODULO_REPORTES.md)

BAJA PRIORIDAD
  [ ] Actualizar el documento de tesis (§8.6.5, Tabla 3) para reflejar que
      "registro de regalías" ya está implementado (modelo `Regalia`, sesión
      2026-08-30) — ver docs/ALINEACION_DOCUMENTO_DESARROLLO.md §3.4.
  [ ] Manual de usuario
  [ ] Capacitación al personal
```

---

## 8. Modelo de datos (entidades implementadas)

```
USUARIOS
  Usuario           id | username | password | rol(ADMIN/PROD/DIST) | first_name | last_name
  RegistroAcceso    id | FK:usuario | accion | ip | timestamp

PRODUCCIÓN
  Producto          id | nombre | presentacion(PST/PCT/BOT/B5L/B3C/HIE) | unidad_medida | activo
  Insumo            id | nombre | categoria | unidad_medida | stock_actual | stock_minimo | activo
  Produccion        id | fecha | lote* | FK:producto | cantidad_producida | FK:registrado_por
  ConsumoInsumo     id | FK:produccion | FK:insumo | cantidad
  CompraInsumo      id | fecha | FK:insumo | cantidad | precio_unitario | proveedor | factura
  RecetaProducto    id | FK:producto | FK:insumo | cantidad_por_unidad  [NUEVO]
  Regalia           id | fecha | FK:producto | FK:produccion(opcional) | cantidad |
                    destinatario | motivo(PRO/OBS/COR/OTR) | FK:registrado_por  [NUEVO]

ACTIVOS
  ActivoRetornable  id | tipo(BOT/CAN) | estado(PLL/PVA/CLI/BAJ) | activo  [faltaba en este listado]
  MovimientoActivo  id | fecha | momento(INI/FIN) | tipo_activo(BOT/CAN) |
                    cantidad_en_planta_lleno | cantidad_en_planta_vacio |
                    cantidad_en_clientes | cantidad_baja
                    UNIQUE(fecha, momento, tipo_activo)
  BajaActivo        id | FK:movimiento | cantidad | motivo(ROT/PER/ROB/DET/OTR) |
                    descripcion | FK:registrado_por  [NUEVO — HU-07]

DISTRIBUCIÓN
  Cliente           id | nombre | telefono | direccion | categoria(REG/MAY) | autoriza_datos | activo
  PrecioPorCategoria id | categoria | FK:producto | precio    UNIQUE(categoria, producto)
  Planilla          id | fecha | FK:distribuidor | estado(ABR/PEN/VAL)
  Entrega           id | FK:planilla | FK:cliente | FK:producto | cantidad | precio_unitario |
                    modalidad_pago(EFE/NEQ/CRE) | devolucion → subtotal()
  Averia            id | FK:planilla | FK:producto | cantidad | descripcion
  Credito           id | FK:cliente | OneToOne:entrega | monto | saldo_pendiente | pagado |
                    fecha_creacion | fecha_pago

REPORTES
  Descuadre         id | fecha | tipo(PV/VI/AC) | severidad(LEV/MOD/CRI) |
                    descripcion | diferencia | resuelto | FK:detectado_por
```

---

## 9. Reglas de negocio definitivas

1. Sin pedidos previos — la venta se registra en el momento de la visita.
2. Solo 2 categorías de precio: REG y MAY — nunca por cliente individual.
3. Crédito se genera automáticamente cuando `modalidad_pago = 'CRE'` (1:1 con Entrega).
4. Inventario de activos: doble registro diario (inicio y fin de jornada).
5. Sync híbrida SOLO para distribución — los demás módulos son online estándar.
6. Múltiples planillas por día por distribuidor están permitidas.
7. Botellones: intercambio mano a mano al momento de la entrega.
8. Averías: se registran con motivo predeterminado "rotura".

---

## 10. Marco legal que afecta el código

| Norma | Impacto |
|---|---|
| Ley 1581/2012 | `autoriza_datos` en Cliente — checkbox obligatorio al registrar |
| Ley 527/1999 | Registros digitales con misma validez legal que físicos |
| Resolución 2674/2013 BPM | `lote` único en `Produccion` |
| Django PBKDF2 | Contraseñas — no modificar el hasher |

---

## 11. Comandos frecuentes

```bash
# Arranque para pruebas en red local (celular de Nicolás)
python manage.py runserver 0.0.0.0:8000

# Datos de prueba
python manage.py crear_datos_prueba        # carga usuarios + datos demo
python manage.py crear_datos_prueba --limpiar  # borra todo y recarga

# Migraciones
python manage.py makemigrations
python manage.py migrate
```

---

**FIN DEL CONTEXTO.**
Toda decisión técnica nueva que se tome debe registrarse en la sección 5.
Toda sesión de trabajo debe empezar confirmando el estado de la sección 4.
