# Brief de alineación — documento de tesis vs. desarrollo real

Generado originalmente desde el repositorio (Claude Code) el 2026-08-30. Auditoría
inicial con acceso completo a `TRABAJO DE GRADO IS 2026 claude.pdf` (202 páginas,
extraído vía `pdftotext`) contra el estado del código en los commits `6aff4ef` y
`114a39d`.

**Actualizado 2026-08-31** (sesión usuarios) para reflejar el trabajo hecho por las
5 sesiones paralelas del proyecto entre el 30 y 31 de agosto — ver nota al final de
cada hallazgo resuelto. Esta actualización se hizo **sin volver a leer el PDF**:
los hallazgos de código se verificaron contra `CLAUDE.md` (secciones 4 y 6) y los
`*/MODULO_*.md` de cada app, que sí están al día. Los hallazgos que dependen del
texto del propio documento (§3.5, §3.7) **no se pudieron re-verificar** — quedan
marcados explícitamente como pendientes de una nueva lectura del PDF antes de
confiar en ellos.

---

## 1. Resumen ejecutivo de avance por módulo (actualizado 2026-08-31)

| Módulo | Estado real verificado | Evidencia |
|---|---|---|
| Usuarios | CRUD completo + 31 tests, todos en verde. Los 7 bugs de code review/seguridad (U-01 a U-07) resueltos. Backup de PostgreSQL implementado (CLI + web para superusuario). | `usuarios/tests.py`, [usuarios/MODULO_USUARIOS.md](../usuarios/MODULO_USUARIOS.md) |
| Producción | CRUD completo, kardex de insumos (bug crítico de 500 corregido), recetas por producto con API JSON, transacción atómica de stock, **regalías** implementadas. 12 tests. | `produccion/tests.py`, [produccion/MODULO_PRODUCCION.md](../produccion/MODULO_PRODUCCION.md) |
| Activos | Doble registro diario (inicio/fin), dashboard de estado, CRUD de movimientos, `BajaActivo` con motivo individual (HU-07). 11 tests. | `activos/tests.py`, [activos/MODULO_ACTIVOS.md](../activos/MODULO_ACTIVOS.md) |
| Distribución | Sync híbrida localStorage + Axios, API REST DRF (5 endpoints), generación automática de crédito, precio validado en servidor (D-01). 20 tests. | `distribucion/tests.py`, [distribucion/MODULO_DISTRIBUCION.md](../distribucion/MODULO_DISTRIBUCION.md) |
| Reportes | Dashboard, export Excel y PDF (ReportLab), descuadres con **detección automática (HU-13)**, créditos con pago parcial, URL hardcodeada corregida (B-02). 25 tests. | `reportes/tests.py`, [reportes/MODULO_REPORTES.md](../reportes/MODULO_REPORTES.md) |

**Cobertura de pruebas real: 99 tests en los 5 módulos (antes: 9 tests en 1 de 5).**

---

## 2. Cambios de código de esta sesión (2026-08-30, sesión original)

1. **Bug corregido (B-01):** alertas de insumos comparaba `stock_actual <= 0` en vez de `stock_minimo`. Corregido y verificado con smoke test end-to-end.
2. **Funcionalidad nueva:** exportación de ventas a PDF (ReportLab 5.0.1). Verificado generando un PDF real (200 OK, `application/pdf`).
3. **Gap cerrado:** ReportLab estaba documentado como instalado en sesión previa pero no existía en el entorno ni en `requirements.txt` — habría fallado con `ModuleNotFoundError` en producción.
4. **`CLAUDE.md` corregido:** faltaba la entidad `ActivoRetornable` en el listado de modelo de datos (sección 8) — sí existe en el código y sí está bien documentada en el diccionario de datos del documento de tesis (Tabla 27).

---

## 3. Hallazgos de la auditoría documento-vs-código

### 3.1 ~~CRÍTICO — Riesgo documentado como crítico, nunca tratado~~ — RESUELTO 2026-08-30/31

§13.3 (Tabla 39, Evaluación de riesgos) identifica **"Pérdida de información por
ausencia de copias de seguridad"** con nivel 15 (probabilidad 3 × impacto 5),
el **tercer riesgo más alto** del proyecto. §13.4 define el tratamiento:
*"implementar copias de seguridad periódicas de la base de datos y aprovechar
la redundancia del servicio de hosting"*.

**Resuelto:** `python manage.py backup_bd` (pg_dump -F c) + procedimiento de
restauración documentado, más una vista web (`/usuarios/backups/`, solo
`is_superuser=True`) con botón "Generar backup ahora" y listado/descarga de
backups existentes. La periodicidad se agenda con cron/Task Scheduler del
sistema operativo (fuera del alcance de la app, documentado en el docstring
del comando). Ver [usuarios/MODULO_USUARIOS.md](../usuarios/MODULO_USUARIOS.md).

**Para el documento:** §13.4 puede actualizarse para reflejar el tratamiento
como implementado y verificado (11 tests: `BackupBdCommandTests` +
`BackupViewsTests`), no solo planeado.

### 3.2 ~~HU-13 promete detección automática que no existe~~ — RESUELTO 2026-08-30

La historia de usuario HU-13 "Alerta de descuadres" (§11.2, Tabla 17) dice:
*"el sistema debe comparar las cantidades producidas, vendidas y disponibles, y
alertar cuando exista una diferencia"* / *"indica la magnitud y el origen
probable de la diferencia"*.

**Resuelto:** `reportes/detector.py` (`detectar_pv`, `detectar_vi`, `detectar_ac`)
compara producción/ventas/disponible acumulado contra un umbral y genera
`Descuadre` automáticamente (`es_automatico=True`), con botón "Detectar
descuadres" en el dashboard y `python manage.py detectar_descuadres` para cron.
El registro manual (`DescuadreCreateView`) se mantiene para hallazgos que un
humano detecta en campo (ej. una canastilla rota que no deja rastro en el
sistema) — no reemplaza a la detección automática, la complementa. Ver decisión
de diseño en `CLAUDE.md` sección 5 y detalle en
[reportes/MODULO_REPORTES.md](../reportes/MODULO_REPORTES.md).

**Para el documento:** el criterio de aceptación de HU-13 ya se cumple tal como
está escrito.

### 3.3 Bitácora de auditoría CRUD declarada pero no implementada — SIGUE ABIERTO

§5.1 (Alcance presente) y la Tabla 19 (RS-04) prometen: *"una bitácora de
auditoría que asienta los eventos de acceso y las operaciones de creación,
modificación y eliminación de registros, indicando usuario, fecha y hora,
operación y registro afectado"*.

`RegistroAcceso` (único modelo de auditoría existente) solo registra
`LOGIN` / `LOGOUT` / `FALLO` — eventos de acceso, no operaciones CRUD sobre
entidades de negocio. La mitad de lo prometido (control de acceso) está
implementada; la otra mitad (trazabilidad de operaciones) no.

**Sigue sin resolver.** Es una decisión de diseño transversal a los 5 módulos
(un modelo genérico de auditoría con signals `post_save`/`post_delete` afecta
a todas las apps) que requiere decisión explícita del usuario antes de
implementar: o se construye ese modelo genérico, o se acota el alcance
declarado en el documento (§5.1/Tabla 19) para que coincida con lo que
`RegistroAcceso` ya cubre. Documentado como pendiente en `CLAUDE.md` sección 7.

### 3.4 ~~"Registro de regalías" — requisito huérfano~~ — RESUELTO 2026-08-30

Tabla 3 (§8.6.5, requerimientos derivados del cuestionario) incluye "registro
de regalías" bajo el módulo de producción.

**Resuelto:** modelo `Regalia` (producto terminado entregado sin cobro —
obsequio/cortesía/promoción — con lote de origen opcional para trazabilidad
BPM), CRUD completo en `/produccion/regalias/`. Decisión documentada en
`CLAUDE.md` sección 5: `Regalia` no descuenta ningún contador de stock porque
`Producto` no lleva `stock_actual` (a diferencia de `Insumo`) — es un registro
de trazabilidad, confirmado con el usuario ya que §8.6.5 Tabla 3 no lo
definía con ese detalle. Ver
[produccion/MODULO_PRODUCCION.md](../produccion/MODULO_PRODUCCION.md).

**Para el documento:** actualizar §8.6.5 Tabla 3 para reflejar que ya está
implementado — sigue pendiente en `CLAUDE.md` backlog (baja prioridad).

### 3.5 Redacción ambigua en §5.1 — SIN RE-VERIFICAR (necesita nueva lectura del PDF)

El alcance presente decía *"gestión de precios diferenciados por cliente"*,
lo cual contradice la propia decisión documentada del proyecto (precio por
**categoría** REG/MAY, nunca individual). Este hallazgo es puramente de
redacción del documento, no de código — nadie en las sesiones de código pudo
confirmar si ya se corrigió en el `.docx`. **Antes de dar esto por resuelto,
hay que releer §5.1 del documento actual.**

### 3.6 ~~HU-07 parcialmente cumplida~~ — RESUELTO 2026-08-30

HU-07 (bajas de envases/embalajes) pedía registrar *"tipo, cantidad, motivo y
fecha"* de cada baja. `MovimientoActivo.cantidad_baja` era solo un contador
agregado por jornada, sin campo de motivo por baja individual.

**Resuelto:** modelo `BajaActivo` (fecha/tipo heredados del `MovimientoActivo`
vía FK, `cantidad`, `motivo` con default "Rotura", `descripcion`), siguiendo
el mismo patrón de `Averia` en distribución. Ver
[activos/MODULO_ACTIVOS.md](../activos/MODULO_ACTIVOS.md).

### 3.7 Capítulos aún sin redactar — SIN RE-VERIFICAR (necesita nueva lectura del PDF)

Verificado en el PDF **el 2026-08-30**: §14.3.4 (Gantt), §15 (Pruebas) y §16
(Recomendaciones) seguían siendo texto guía de la plantilla. Nadie con acceso
al código pudo confirmar si esto cambió desde entonces — es contenido que se
redacta en Word, no en este repo. **Releer estas secciones antes de asumir que
siguen vacías.**

Para §15, el material real y verificado ya creció bastante desde el
2026-08-30: 99 tests en verde en los 5 módulos (antes 9 en 1 solo módulo), un
smoke test end-to-end del export PDF/Excel, y 12 hallazgos de code
review/seguridad resueltos con severidad y evidencia (ver tabla en §4). Sigue
siendo contenido listable, no hay que inventar nada — solo hay más ahora que
en el primer corte.

### 3.8 Lo que SÍ está bien alineado (para no perder tiempo re-revisándolo)

- **Diccionario de datos (§12.2, Tablas 20-35):** coincidía campo por campo con
  los modelos reales de los 5 módulos al 2026-08-30, incluyendo `ActivoRetornable`
  (Tabla 27). Desde entonces se agregaron campos/modelos nuevos (`RecetaProducto`,
  `Regalia`, `BajaActivo`) que **no estaban en el diccionario de datos original**
  — esto es nuevo trabajo para el documento, no una regresión de alineación.
- **Arquitectura (§12.1):** 3 capas + patrón MVT de Django, API REST para
  distribución, PostgreSQL, componente de sincronización local — descripción
  fiel a la implementación real, sin cambios desde el corte anterior.
- **Riesgo de sincronización híbrida (nivel 20, §13.4):** mitigado (el módulo
  de distribución con localStorage + Axios está implementado y operativo) —
  se puede marcar como resuelto en las conclusiones del análisis de riesgos.
- **Marco legal (Ley 1581/2012, Ley 527/1999, Resolución 2674/2013):**
  reflejado correctamente en el modelo (`autoriza_datos` en `Cliente`, `lote`
  único en `Produccion`).

---

## 4. Hallazgos de calidad — estado actualizado 2026-08-31 (material para §15 Pruebas)

| ID | Severidad | Descripción corta | Estado |
|---|---|---|---|
| 3.1 | Crítica | Riesgo de pérdida de datos (nivel 15) sin backup implementado | **Resuelto** — `backup_bd` (CLI + web) |
| 3.2 | Alta | HU-13 no detecta descuadres automáticamente, era registro manual | **Resuelto** — `reportes/detector.py` |
| U-01 | Alta | POST a un pk de superusuario en `UsuarioUpdateView` producía error 500 (y, hallazgo posterior al TDD: con datos válidos creaba un usuario fantasma) | **Resuelto** |
| U-02 | Media | Validación de contraseña no comparaba contra el username | **Resuelto** |
| U-03 | Media | Restricción de auto-cambio de rol solo existía en la vista, no en `/admin/` | **Resuelto** |
| U-07 | Alta | `UsuarioAdmin` no impedía editar/borrar a un superusuario vía `/admin/` con permisos Django (hallazgo posterior, extiende U-03) | **Resuelto** |
| 3.3 | Media | Bitácora de auditoría CRUD (RS-04) no implementada, solo login/logout | **Abierto** — pendiente decisión del usuario |
| B-02 | Media | URL hardcodeada en JS de `creditos.html` | **Resuelto** |
| U-04 | Baja | Mensaje de error duplicado en un guard | **Resuelto** |
| U-05 | Baja | `get_object()` retornaba `None` en vez de lanzar `Http404` | **Resuelto** |
| U-06 | Baja | Dos guards de auto-protección independientes, uno podía quedar invisible | **Resuelto** |
| 3.4 | Baja | "Registro de regalías" (Tabla 3) sin implementar ni justificar su exclusión | **Resuelto** — modelo `Regalia` |
| 3.6 | Baja | HU-07: bajas sin campo de motivo individual | **Resuelto** — modelo `BajaActivo` |

11 de 12 hallazgos de código resueltos. El único abierto (RS-04, bitácora de
auditoría CRUD) tiene decisión pendiente del usuario documentada en
`CLAUDE.md` sección 7.

Detalle línea por línea en `usuarios/MODULO_USUARIOS.md`,
`produccion/MODULO_PRODUCCION.md`, `activos/MODULO_ACTIVOS.md`,
`distribucion/MODULO_DISTRIBUCION.md` y `reportes/MODULO_REPORTES.md`.

---

## 5. Cómo usar este brief

Este archivo queda versionado en el repo. Para editar el documento de Word,
pégalo (completo o por sección) en la sesión de Claude para Word — ya no hace
falta que esa sesión ni esta carguen el documento completo dos veces, esto ya
resume la comparación punto por punto.

**Antes de pegarlo:** las secciones 3.5 y 3.7 dependen del texto actual del
`.docx`, que ninguna sesión de código pudo releer en esta actualización. Si la
sesión de Word tiene el documento abierto, que confirme el estado real de esas
dos secciones antes de aplicar cambios basados en ellas — todo lo demás (3.1,
3.2, 3.3, 3.4, 3.6, la tabla de §4 y el resumen de §1) está verificado contra
el código real al 2026-08-31.
