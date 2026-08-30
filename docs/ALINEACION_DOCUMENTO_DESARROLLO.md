# Brief de alineación — documento de tesis vs. desarrollo real

Generado desde el repositorio (Claude Code) el 2026-08-30. Auditoría con acceso
completo a `TRABAJO DE GRADO IS 2026 claude.pdf` (202 páginas, extraído vía
`pdftotext`) contra el estado real del código, commits `6aff4ef` y `114a39d`.

---

## 1. Resumen ejecutivo de avance por módulo

| Módulo | Estado real verificado | Evidencia |
|---|---|---|
| Usuarios | CRUD completo + 9 tests (`MixinsTests`, `AdminPasswordResetFormTests`, `UsuarioUpdateViewTests`), todos en verde. 6 bugs de code review pendientes (U-01 a U-06, ver §4). | `usuarios/tests.py`, [usuarios/MODULO_USUARIOS.md](../usuarios/MODULO_USUARIOS.md) |
| Producción | CRUD completo, kardex de insumos, recetas por producto con API JSON, transacción atómica de stock. Sin tests propios. | `produccion/` |
| Activos | Doble registro diario (inicio/fin), dashboard de estado, CRUD de movimientos, entidad `ActivoRetornable` + `MovimientoActivo`. Sin tests propios. | `activos/` |
| Distribución | Sync híbrida localStorage + Axios, API REST DRF (5 endpoints), generación automática de crédito. Sin tests propios. | `distribucion/` |
| Reportes | Dashboard con 6 tarjetas, export Excel y **export PDF (ReportLab) nuevo esta sesión**, descuadres (registro **manual**, ver §3), créditos con pago parcial. Sin tests propios. | `reportes/`, [reportes/MODULO_REPORTES.md](../reportes/MODULO_REPORTES.md) |

**Cobertura de pruebas real: 9 tests en 1 de 5 módulos.**

---

## 2. Cambios de código de esta sesión

1. **Bug corregido (B-01):** alertas de insumos comparaba `stock_actual <= 0` en vez de `stock_minimo`. Corregido y verificado con smoke test end-to-end.
2. **Funcionalidad nueva:** exportación de ventas a PDF (ReportLab 5.0.1). Verificado generando un PDF real (200 OK, `application/pdf`).
3. **Gap cerrado:** ReportLab estaba documentado como instalado en sesión previa pero no existía en el entorno ni en `requirements.txt` — habría fallado con `ModuleNotFoundError` en producción.
4. **`CLAUDE.md` corregido:** faltaba la entidad `ActivoRetornable` en el listado de modelo de datos (sección 8) — sí existe en el código y sí está bien documentada en el diccionario de datos del documento de tesis (Tabla 27).

---

## 3. Hallazgos de la auditoría documento-vs-código (nuevo, con acceso completo al PDF)

### 3.1 CRÍTICO — Riesgo documentado como crítico, nunca tratado

§13.3 (Tabla 39, Evaluación de riesgos) identifica **"Pérdida de información por
ausencia de copias de seguridad"** con nivel 15 (probabilidad 3 × impacto 5),
el **tercer riesgo más alto** del proyecto. §13.4 define el tratamiento:
*"implementar copias de seguridad periódicas de la base de datos y aprovechar
la redundancia del servicio de hosting"*.

**No existe ningún management command, cron ni configuración de backup en el
repositorio.** No es un simple "falta implementar" — es un riesgo que el propio
documento califica de crítico, con plan de mitigación por escrito, sin ejecutar.
Si un jurado revisa el análisis de riesgos y luego el sistema, la inconsistencia
es evidente.

### 3.2 HU-13 promete detección automática que no existe

La historia de usuario HU-13 "Alerta de descuadres" (§11.2, Tabla 17) dice:
*"el sistema debe comparar las cantidades producidas, vendidas y disponibles, y
alertar cuando exista una diferencia"* / *"indica la magnitud y el origen
probable de la diferencia"*.

El código real (`DescuadreCreateView` + `DescuadreForm` en `reportes/`) es un
**formulario de registro manual** — un humano ingresa el descuadre que ya
detectó. No hay ninguna lógica que compare producción/ventas/inventario
automáticamente. Es, literalmente, el mismo proceso manual que el sistema
debía reemplazar. Si se prueba el criterio de aceptación tal como está escrito,
no se cumple.

### 3.3 Bitácora de auditoría CRUD declarada pero no implementada

§5.1 (Alcance presente) y la Tabla 19 (RS-04) prometen: *"una bitácora de
auditoría que asienta los eventos de acceso y las operaciones de creación,
modificación y eliminación de registros, indicando usuario, fecha y hora,
operación y registro afectado"*.

`RegistroAcceso` (único modelo de auditoría existente) solo registra
`LOGIN` / `LOGOUT` / `FALLO` — eventos de acceso, no operaciones CRUD sobre
entidades de negocio. La mitad de lo prometido (control de acceso) está
implementada; la otra mitad (trazabilidad de operaciones) no.

### 3.4 "Registro de regalías" — requisito huérfano

Tabla 3 (§8.6.5, requerimientos derivados del cuestionario) incluye "registro
de regalías" bajo el módulo de producción. No hay ninguna coincidencia en todo
el repositorio (modelos, vistas, templates). No quedó ni siquiera mencionado
como excluido en alcance futuro — simplemente desapareció entre el análisis y
la implementación.

### 3.5 Redacción ambigua en §5.1 (fácil de corregir)

El alcance presente dice *"gestión de precios diferenciados por cliente"*,
lo cual contradice la propia decisión documentada del proyecto (precio por
**categoría** REG/MAY, nunca individual) y contradice lo que el mismo
documento aclara correctamente en HU-09 y en §8.6.5 ("por categoría de
cliente"). Es solo redacción — cambiar "por cliente" por "por categoría de
cliente" en §5.1 resuelve la inconsistencia interna del propio documento.

### 3.6 HU-07 parcialmente cumplida

HU-07 (bajas de envases/embalajes) pide registrar *"tipo, cantidad, motivo y
fecha"* de cada baja. `MovimientoActivo.cantidad_baja` es solo un contador
agregado por jornada, sin campo de motivo por baja individual. Menor, pero
real.

### 3.7 Capítulos aún sin redactar (no es un tema de alineación — es contenido pendiente)

Verificado en el PDF: los siguientes apartados **siguen siendo el texto guía
de la plantilla**, sin contenido real del proyecto:

- **§14.3.4 Cronograma de actividades (Gantt)** — solo el ejemplo genérico de
  la plantilla. Además, §14.2.4 ya hace referencia a *"Ilustración 8.
  cronograma de actividades del primer semestre 2026"*, que tampoco existe
  todavía.
- **§15 Pruebas** (planificación, ejecución, análisis, resultados,
  conclusiones) — plantilla con placeholders literales ("se ejecutaron X
  pruebas, de las cuales X fueron exitosas").
- **§16 Recomendaciones** — solo las instrucciones de qué debe contener.

Para §15 ya hay material real y verificado esta sesión: 9 tests en verde de
`usuarios`, un smoke test end-to-end del export PDF, y 7 hallazgos de code
review con severidad (B-02, U-01 a U-06, ver §4). Es contenido listable, no
hay que inventar nada.

### 3.8 Lo que SÍ está bien alineado (para no perder tiempo re-revisándolo)

- **Diccionario de datos (§12.2, Tablas 20-35):** coincide campo por campo con
  los modelos reales de los 5 módulos, incluyendo `ActivoRetornable` (Tabla
  27) que yo mismo había omitido en `CLAUDE.md`.
- **Arquitectura (§12.1):** 3 capas + patrón MVT de Django, API REST para
  distribución, PostgreSQL, componente de sincronización local — descripción
  fiel a la implementación real.
- **Riesgo de sincronización híbrida (nivel 20, §13.4):** ya mitigado con
  éxito (el módulo de distribución con localStorage + Axios está
  implementado y operativo) — se puede marcar como resuelto en las
  conclusiones del análisis de riesgos en vez de dejarlo como riesgo abierto.
- **Marco legal (Ley 1581/2012, Ley 527/1999, Resolución 2674/2013):**
  reflejado correctamente en el modelo (`autoriza_datos` en `Cliente`, `lote`
  único en `Produccion`).

---

## 4. Hallazgos de calidad pendientes (material para §15 Pruebas)

| ID | Severidad | Descripción corta |
|---|---|---|
| 3.1 | Crítica | Riesgo de pérdida de datos (nivel 15) sin backup implementado — ver §3.1 |
| 3.2 | Alta | HU-13 no detecta descuadres automáticamente, es registro manual — ver §3.2 |
| U-01 | Alta | POST a un pk de superusuario en `UsuarioUpdateView` produce error 500 |
| U-02 | Media | Validación de contraseña no compara contra el username |
| U-03 | Media | Restricción de auto-cambio de rol solo existe en la vista, no en `/admin/` |
| 3.3 | Media | Bitácora de auditoría CRUD (RS-04) no implementada, solo login/logout |
| B-02 | Media | URL hardcodeada en JS de `creditos.html` |
| U-04 | Baja | Mensaje de error duplicado en un guard |
| U-05 | Baja | `get_object()` retorna `None` en vez de lanzar `Http404` |
| U-06 | Baja | Dos guards de auto-protección independientes, uno puede quedar invisible |
| 3.4 | Baja | "Registro de regalías" (Tabla 3) sin implementar ni justificar su exclusión |
| 3.6 | Baja | HU-07: bajas sin campo de motivo individual |

Detalle línea por línea de U-01 a U-06 y B-02 en `usuarios/MODULO_USUARIOS.md`
y `reportes/MODULO_REPORTES.md`.

---

## 5. Cómo usar este brief

Este archivo queda versionado en el repo. Para editar el documento de Word,
pégalo (completo o por sección) en la sesión de Claude para Word — ya no hace
falta que esa sesión ni esta carguen el documento completo dos veces, esto ya
resume la comparación punto por punto.
