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
- `usuarios/tests.py`: 9 tests (mixins, `AdminPasswordResetForm`, `UsuarioUpdateView`) — todos en verde
- Bitácora detallada de sesiones en [usuarios/MODULO_USUARIOS.md](usuarios/MODULO_USUARIOS.md), incluye 6 bugs de code review (U-01 a U-06) pendientes — ver sección 6

### ✅ Módulo producción
- Modelos: `Producto`, `Insumo`, `Produccion`, `ConsumoInsumo`, `CompraInsumo`, `RecetaProducto`
- CRUD completo con búsqueda y filtros en todos los listados
- Formset inline de consumo de insumos al registrar producción
- Verificación de stock antes de guardar (transacción atómica)
- **Kardex de insumos**: historial cronológico entradas/salidas con saldo acumulado
- **Recetas por producto**: cantidad de insumo por unidad producida + API JSON para precarga
- Migración `0003_receta_producto` aplicada

### ✅ Módulo activos
- Doble registro diario (inicio y fin de jornada) con `UNIQUE(fecha, momento, tipo_activo)`
- Dashboard de activos con estado actual de botellones y canastillas
- CRUD `MovimientoActivo` con detalle

### ✅ Módulo distribución
- Modelos: `Cliente` (categoría REG/MAY), `PrecioPorCategoria`, `Planilla`, `Entrega`, `Averia`, `Credito`
- CRUD Clientes y Planillas (admin)
- Vista planilla de ruta para DIST (móvil-first)
- Múltiples planillas por día por distribuidor (constraint `unique_together` eliminado)
- **Sincronización híbrida**: localStorage + Axios — operación offline completa para Nicolás
- **API REST DRF**: 5 endpoints para sincronización
- Generación automática de `Credito` cuando `modalidad_pago = 'CRE'`

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

---

## 6. Bugs conocidos pendientes de corregir

**Resuelto:** B-01 (`reportes/views.py`) — `alertas_insumos` ya filtra contra `F('stock_minimo')`. Commit `6aff4ef`, sesión 2026-08-30.

| # | Archivo | Descripción | Impacto |
|---|---|---|---|
| B-02 | `reportes/templates/reportes/creditos.html:116` | URL hardcodeada en JS: `` `/reportes/creditos/${pk}/pagar/` `` | Se rompe si cambia el prefijo de URL |
| U-01 | `usuarios/views.py:73` | No hay `post()` que replique el guard de `get()`: un POST a un pk de superusuario deja `self.object = None` → `AttributeError` 500 | Alta — crash en producción |
| U-02 | `usuarios/forms.py:52` | `validate_password(p1)` sin `user=` → `UserAttributeSimilarityValidator` no se aplica → contraseña igual al username se acepta | Media — seguridad |
| U-03 | `usuarios/views.py` / `admin.py:84` | Guard de auto-cambio de rol solo vive en la vista; sin restricción en `/admin/usuarios/usuario/<pk>/change/` | Media — bypass del control de acceso |
| U-04 | `usuarios/views.py:85` | `messages.error` + `form.add_error` se disparan juntos → error duplicado en pantalla | Baja — UX |
| U-05 | `usuarios/views.py:66` | `get_object()` retorna `None` en vez de `Http404`; inconsistente con el resto del módulo | Baja — mismo fix que U-01 |
| U-06 | `usuarios/views.py:81` | Dos guards de auto-protección separados; si ambos aplican, solo el primero se muestra | Baja |

Detalle completo (código propuesto, línea exacta) en [usuarios/MODULO_USUARIOS.md](usuarios/MODULO_USUARIOS.md).

---

## 7. Pendiente — backlog priorizado

```
CRÍTICA (riesgo calificado como crítico en el documento de tesis, §13.3-13.4,
         nivel 15/20 — ver docs/ALINEACION_DOCUMENTO_DESARROLLO.md §3.1)
  [ ] Implementar rutina de backup periódico de PostgreSQL + procedimiento de
      restauración documentado. Declarado en alcance presente (§5.1) y como
      tratamiento de riesgo crítico; hoy no existe ningún management command
      ni cron para esto. Módulo: usuarios/administración (mgmt command propio).

ALTA PRIORIDAD
  [ ] HU-13 (reportes): implementar detección automática de descuadres
      comparando producción/ventas/inventario. Hoy Descuadre es 100% registro
      manual (DescuadreCreateView) — no cumple el criterio de aceptación de
      la historia de usuario. Ver docs/ALINEACION_DOCUMENTO_DESARROLLO.md §3.2.
  [ ] B-02 Corregir URL hardcodeada en creditos.html JS        (10 min)
  [ ] U-01 + U-05 Guard post() + get_object_or_404 en usuarios (mismo fix, ver sección 6)
  [ ] U-02 Pasar user=usuario a validate_password
  [ ] U-03 Bloquear auto-cambio de rol también desde /admin/
  [ ] Pruebas Django TestCase para producción/activos/distribución/reportes
      (usuarios ya tiene 9 — ver sección 4)

MEDIA PRIORIDAD
  [ ] Bitácora de auditoría CRUD (RS-04, §5.1 y Tabla 19): declarada en el
      documento pero RegistroAcceso solo cubre login/logout, no operaciones
      de creación/modificación/eliminación sobre entidades de negocio.
  [ ] U-04 Unificar mecanismo de error (solo form.add_error)
  [ ] U-06 Consolidar los dos guards de auto-protección
  [ ] Fixtures de datos reales (productos, clientes, precios actuales)
  [ ] Despliegue Railway / Render / PythonAnywhere
  [ ] Gráficas Chart.js en ventas, PDF resumen mensual ejecutivo (ver reportes/MODULO_REPORTES.md)

BAJA PRIORIDAD
  [ ] "Registro de regalías" (producción): requisito derivado del cuestionario
      (documento §8.6.5, tabla 3) sin implementar ni justificar su exclusión.
  [ ] HU-07 (activos): registro de bajas sin campo de motivo individual —
      hoy es solo un contador agregado por jornada.
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

ACTIVOS
  ActivoRetornable  id | tipo(BOT/CAN) | estado(PLL/PVA/CLI/BAJ) | activo  [faltaba en este listado]
  MovimientoActivo  id | fecha | momento(INI/FIN) | tipo_activo(BOT/CAN) |
                    cantidad_en_planta_lleno | cantidad_en_planta_vacio |
                    cantidad_en_clientes | cantidad_baja
                    UNIQUE(fecha, momento, tipo_activo)

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
