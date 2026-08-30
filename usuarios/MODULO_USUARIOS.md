# Módulo Usuarios — Brisas de Pacandé

Archivo de seguimiento de sesiones para el módulo `usuarios/`.

---

## Estado general

| Vista | URL | Estado |
|---|---|---|
| Lista de usuarios | `/usuarios/` | ✅ operativo |
| Crear usuario | `/usuarios/nuevo/` | ✅ operativo |
| Editar usuario | `/usuarios/<pk>/editar/` | ✅ operativo — bugs parciales (ver abajo) |
| Cambiar contraseña | `/usuarios/<pk>/password/` | ✅ operativo — bug pendiente (ver abajo) |
| Activar / desactivar | `/usuarios/<pk>/toggle/` | ✅ operativo |
| Log de accesos | `/usuarios/accesos/` | ✅ operativo |

---

## Archivos principales

```
usuarios/
  models.py             — Usuario(AbstractUser) con campo rol + RegistroAcceso
  views.py              — UsuarioListView, UsuarioCreateView, UsuarioUpdateView,
                          UsuarioSetPasswordView, UsuarioToggleActivoView,
                          RegistroAccesoListView
  forms.py              — UsuarioCreateForm, UsuarioUpdateForm, AdminPasswordResetForm
  mixins.py             — RolRequiredMixin + constantes TODOS/ADMIN_PROD/SOLO_ADMIN/ADMIN_DIST
  urls.py               — app_name='usuarios', 6 rutas
  admin.py              — Usuario registrado con UserAdmin + fieldset rol/telefono
  tests.py              — 9 tests (MixinsTests, AdminPasswordResetFormTests,
                          UsuarioUpdateViewTests)
  templatetags/         — template tags personalizados
  templates/usuarios/
    lista.html
    form.html
    password_form.html
    accesos.html
```

---

## Sesión 2026-06-10 — Revisión de roles y accesos

### Fixes implementados (TDD — test primero, implementación después)

| ID | Archivo | Descripción | Commit |
|----|---------|-------------|--------|
| Q-02 | `mixins.py` | Constantes de roles convertidas de listas mutables a tuplas inmutables | `848c309` |
| S-01 | `forms.py` | `AdminPasswordResetForm.clean()` ahora llama `validate_password(p1)` | `db77842` |
| S-02 | `views.py` | `UsuarioUpdateView.form_valid()` bloquea auto-cambio de rol del admin logueado | `174af59` |
| Q-01 | `views.py` | `UsuarioUpdateView.get()` ya no llama `get_object()` dos veces | `395560f` |

### Tests agregados (`usuarios/tests.py`)

9 tests en 3 clases — todos en verde:

- `MixinsTests` (2): constantes son tuplas, `roles_permitidos` default es tupla
- `AdminPasswordResetFormTests` (3): contraseña corta rechazada, fuerte aceptada, distintas rechazadas
- `UsuarioUpdateViewTests` (4): auto-cambio de rol bloqueado, cambio de rol a otro permitido, superusuario redirige, GET normal renderiza formulario

Nota: se usa `client.force_login()` en lugar de `client.login()` porque `django-axes` exige objeto request real en `authenticate()`.

---

## Bugs pendientes identificados en code review (2026-06-13)

| # | Severidad | Archivo | Línea | Descripción |
|---|-----------|---------|-------|-------------|
| U-01 | Alta | `views.py` | 73 | No existe `post()` equivalente al guard de `get()`: un POST a un pk de superusuario deja `self.object = None` → `form_invalid` → `get_context_data` → `AttributeError` en `self.object.username` → 500 |
| U-02 | Media | `forms.py` | 52 | `validate_password(p1)` sin kwarg `user=` → `UserAttributeSimilarityValidator` se salta silenciosamente → contraseña igual al username se acepta |
| U-03 | Media | `views.py` / `admin.py` | 84 | Guard de auto-cambio de rol solo vive en la vista; accesible desde `/admin/usuarios/usuario/<pk>/change/` sin restricción |
| U-04 | Baja | `views.py` | 85 | `messages.error` + `form.add_error` se disparan juntos → el usuario ve el mismo error dos veces (banner + inline); inconsistente con el guard de `is_active` que solo usa `messages.error` |
| U-05 | Baja | `views.py` | 66 | `get_object()` retorna `None` en vez de lanzar `Http404`; viola el contrato de Django CBV. Los demás views del módulo usan `get_object_or_404(..., is_superuser=False)` que es el patrón correcto |
| U-06 | Baja | `views.py` | 81 | Dos guards separados con `if usuario.pk == self.request.user.pk`; solo el primero que dispara muestra error — si ambas condiciones aplican, la segunda queda invisible hasta el siguiente envío |

### Fix recomendado para U-01 + U-05 (misma raíz)

Reemplazar `get_object()` en `UsuarioUpdateView` por el patrón ya usado en `UsuarioSetPasswordView` y `UsuarioToggleActivoView`:

```python
def get_object(self, queryset=None):
    return get_object_or_404(Usuario, pk=self.kwargs['pk'], is_superuser=False)

def post(self, request, *args, **kwargs):
    self.object = self.get_object()
    return super(BaseUpdateView, self).post(request, *args, **kwargs)
```

Esto elimina el `return None` antipatrón y cierra el crash del POST en una sola operación.

---

## Sesión 2026-08-30 — U-01 a U-06 + backup crítico de PostgreSQL

Directrices recibidas de la sesión general (orquestando las 5 sesiones paralelas del proyecto) tras auditoría documento-vs-código. TDD estricto: cada fix con test rojo verificado antes de tocar producción.

### Fixes implementados (TDD)

| ID | Archivo | Cambio | Test que lo prueba |
|----|---------|--------|---------------------|
| U-01 + U-05 | `views.py` — `UsuarioUpdateView.get_object()` | Reemplazado el `get_object()` que devolvía `None` (+ `get()` custom) por `get_object_or_404(Usuario, pk=self.kwargs['pk'], is_superuser=False)`. Ya no hace falta sobrescribir `get()`: `BaseUpdateView` llama `get_object()` tanto en GET como en POST. | `test_get_editar_superusuario_retorna_404`, `test_post_editar_superusuario_retorna_404` |
| U-02 | `forms.py` — `AdminPasswordResetForm` | Constructor acepta `usuario=None`; `clean()` llama `validate_password(p1, user=self.usuario)`. `views.py` (`UsuarioSetPasswordView`) pasa `usuario=usuario` en `GET` y `POST`. | `test_contrasena_similar_al_username_es_rechazada` |
| U-03 | `admin.py` — `UsuarioAdmin` | `get_readonly_fields()` agrega `'rol'` a los campos de solo lectura cuando `obj.pk == request.user.pk` (el admin está editando su propia cuenta desde `/admin/`). | `UsuarioAdminTests` (3 tests: readonly en auto-edición, no readonly en otros, no readonly al crear) |
| U-04 + U-06 | `views.py` — `UsuarioUpdateView.form_valid()` | Los dos guards de auto-protección (desactivar cuenta propia, cambiar rol propio) se evalúan ambos en el mismo bloque, cada uno con `form.add_error()`; se retorna `form_invalid` solo si `form.errors` quedó no vacío. Elimina el `messages.error` duplicado y la pérdida del segundo error. | `test_auto_edicion_con_rol_y_activo_invalidos_muestra_ambos_errores` |

**Hallazgo durante TDD (más grave de lo documentado):** el bug U-01 no solo crasheaba con `AttributeError` cuando el formulario era inválido — con datos de formulario **válidos**, un POST a un pk de superusuario pasaba `instance=None` al `ModelForm`, que Django interpreta como "crear una instancia nueva". El resultado era un usuario fantasma activo con `username=''` guardado silenciosamente en la base de datos, sin que el atacante necesitara enviar datos inválidos. El fix (`get_object_or_404`) cierra ambas rutas porque el 404 ocurre antes de construir el formulario.

### Tests agregados

`usuarios/tests.py` pasó de 9 a 18 tests: `UsuarioAdminTests` (3, nueva clase), `BackupBdCommandTests` (3, nueva clase), más 4 tests nuevos/reescritos en `UsuarioUpdateViewTests` y `AdminPasswordResetFormTests`. Los 9 tests originales permanecen verdes (2 renombrados para reflejar el nuevo contrato 404 en vez de redirect).

### Backup de PostgreSQL (riesgo crítico §13.3, nivel 15)

Nuevo comando `usuarios/management/commands/backup_bd.py`:

```bash
python manage.py backup_bd                    # dump en BASE_DIR/backups/
python manage.py backup_bd --destino /ruta     # dump en carpeta custom
```

- Usa `pg_dump -F c` (formato custom, comprimido) leyendo host/puerto/usuario/nombre de BD desde `settings.DATABASES['default']` y `PGPASSWORD` vía variable de entorno (no en argv, no queda en `ps`/logs del shell).
- Falla con `CommandError` si el motor no es `django.db.backends.postgresql` o si `pg_dump` retorna código de error distinto de 0.
- Tests (`BackupBdCommandTests`) mockean `subprocess.run` — no requieren el binario `pg_dump` instalado en CI.

**Procedimiento de restauración:**
```bash
pg_restore --clean --if-exists -h HOST -p PORT -U USER -d NOMBRE_BD archivo.dump
```
`--clean --if-exists` permite restaurar sobre una base ya existente sin fallar por objetos duplicados.

**Programación periódica (pendiente de configurar en el servidor de despliegue, no en este repo):**
- Linux/cron: `0 3 * * * cd /ruta/proyecto && venv/bin/python manage.py backup_bd`
- Windows Task Scheduler: acción diaria ejecutando `venv\Scripts\python.exe manage.py backup_bd` con directorio de inicio en la raíz del proyecto.

### Pendiente (fuera de alcance de esta sesión)

- Bitácora de auditoría CRUD (RS-04) — decisión de diseño transversal a varios módulos, requiere consulta directa con el usuario antes de implementar (ver CLAUDE.md sección 7).
- Rotación/purga de dumps antiguos en `backup_bd` — no había requisito explícito; se puede agregar si el volumen de backups se vuelve un problema real.

---

## Sesión 2026-08-30 (cont.) — U-07: protección de superusuarios en Django admin

Hallazgo de una revisión de seguridad automática sobre el commit `6129d8a`, verificado antes de implementar (no se implementó a ciegas): extiende U-03.

**U-07 (Alta — bypass de protección vía `/admin/`):** `UsuarioUpdateView.get_object()` protege completamente a los superusuarios en la app (404 con `is_superuser=False`), pero `UsuarioAdmin` no tenía el mismo filtro. `get_readonly_fields()` (U-03) solo bloquea el auto-cambio de rol; nada impedía que un usuario `is_staff=True` con permisos Django de `change_usuario`/`delete_usuario` editara o borrara a **otro** usuario que sí fuera superusuario, vía `/admin/usuarios/usuario/<pk>/change/` o `/delete/`.

No es explotable hoy: `maximino` (rol de negocio ADMIN) tiene `is_staff=True` pero ningún permiso Django asignado (sin `user_permissions`, sin grupo), así que el admin le niega el acceso al modelo `Usuario` por el chequeo estándar de permisos. Pero es protección accidental, no por diseño — si en el futuro se le otorga permiso de gestión de usuarios vía admin (plausible, ya que `is_staff=True` fue una decisión deliberada), el hueco se abre.

**Fix (mismo patrón que las vistas, adaptado a `ModelAdmin`):**
```python
def has_change_permission(self, request, obj=None):
    if obj is not None and obj.is_superuser and not request.user.is_superuser:
        return False
    return super().has_change_permission(request, obj)

def has_delete_permission(self, request, obj=None):
    if obj is not None and obj.is_superuser and not request.user.is_superuser:
        return False
    return super().has_delete_permission(request, obj)
```

Tests agregados a `UsuarioAdminTests` (18 → 22 tests en total): un staff con permiso `change_usuario` no puede editar a un superusuario pero sí a otro usuario normal; un staff con `delete_usuario` no puede borrar a un superusuario; un superusuario sí puede editar a otro superusuario (caso de control, para no romper la gestión legítima entre superusuarios técnicos).

---

## Sesión 2026-08-30 (cont. 2) — Backup desde el navegador (botón + listado/descarga)

Directriz del usuario: el superusuario técnico de Django (`is_superuser=True` — se descartó explícitamente crear un rol de negocio nuevo para esto) debe poder generar un backup manual con un botón y descargar backups existentes desde la web. Alcance acotado por el usuario: **sin** programación de periodicidad desde la web — eso sigue siendo cron/Task Scheduler del sistema operativo, tal como documenta `backup_bd.py`.

### Refactor previo (sin cambiar comportamiento, tests existentes se mantienen verdes)

El cuerpo de `backup_bd.py` se movió a `usuarios/backup.py` para que tanto el management command como la vista web usen la misma lógica sin duplicarla:

- `generar_backup(destino=None)` — genera el dump con `pg_dump -F c`, lanza `BackupError` (no `CommandError`, que es específico de management commands) si el motor no es PostgreSQL o si `pg_dump` falla.
- `listar_backups()` — devuelve `BackupInfo(nombre, tamano, fecha)` por cada archivo en `BASE_DIR/backups`, ordenados por fecha descendente.
- `get_backup_dir()` — helper para la ruta de la carpeta.

`backup_bd.py` (el comando) quedó como un wrapper delgado: llama `generar_backup()` y traduce `BackupError` a `CommandError`. Los 3 tests de `BackupBdCommandTests` se mantuvieron sin cambio de comportamiento, solo se movió el objetivo del `@patch` de `usuarios.management.commands.backup_bd.subprocess.run` a `usuarios.backup.subprocess.run`.

### Decisiones de diseño (a documentar, según lo pedido)

| Decisión | Motivo |
|---|---|
| Mixin nuevo `SuperusuarioRequiredMixin` (`usuarios/mixins.py`), no reutilizar `RolRequiredMixin` | `RolRequiredMixin` está pensado para roles de negocio (ADMIN/PROD/DIST) y ya trata a cualquier `is_superuser` como acceso total a todo. Backups es una función administrativa del sistema que ni siquiera el rol de negocio ADMIN debe poder ejecutar — necesita su propio chequeo estricto de `is_superuser`, independiente del campo `rol` |
| `BackupError` (excepción propia en `usuarios/backup.py`) en vez de `CommandError` en la capa compartida | `CommandError` es específico de `django.core.management` y no tiene sentido en una vista web; la vista atrapa `BackupError` y muestra `messages.error()` en vez de dejar que la petición HTTP falle con 500 |
| Descarga valida `nombre` contra `{b.nombre for b in listar_backups()}` en vez de confiar en el parámetro de la URL | Defensa contra path traversal: aunque el nombre del archivo generado siempre sigue el patrón `brisas_pacande_<timestamp>.dump`, la vista de descarga no asume eso — solo sirve un archivo cuyo nombre exacto ya apareció en el listado real de la carpeta de backups, así que un parámetro `../../config/settings.py` nunca coincide con el set y devuelve 404 antes de tocar el filesystem con ese valor |
| `FileResponse(..., as_attachment=True, filename=nombre)` | Fuerza la descarga (no intenta previsualizar un `.dump` binario en el navegador) |
| Botón "Generar backup ahora" en la misma pantalla del listado, sin programación de periodicidad en la UI | Alcance explícito del usuario — la periodicidad sigue siendo responsabilidad de cron/Task Scheduler en el servidor de despliegue |

### Vistas y rutas nuevas

| Vista | URL | Acceso |
|---|---|---|
| `BackupListView` | `/usuarios/backups/` | Solo superusuario — lista con nombre, tamaño (`filesizeformat`), fecha y enlace de descarga |
| `BackupGenerarView` | `POST /usuarios/backups/generar/` | Solo superusuario — llama `generar_backup()`, mensaje de éxito o error, redirige a la lista |
| `BackupDescargarView` | `/usuarios/backups/<nombre>/descargar/` | Solo superusuario — 404 si `nombre` no está en el listado real |

Enlace "Backups" agregado al sidebar (`templates/includes/sidebar_nav.html`), visible solo si `request.user.is_superuser`.

### Tests agregados

`BackupViewsTests` (9 tests, `usuarios/tests.py` 22 → 31 en total): rechazo a admin de negocio no-superusuario (lista, generar, descargar), acceso permitido a superusuario, listado muestra archivos existentes (con `override_settings(BASE_DIR=...)` + `tempfile.TemporaryDirectory` para no tocar backups reales), generar llama `generar_backup` y redirige, generar con `BackupError` no crashea (verifica que sigue redirigiendo en vez de 500), descarga devuelve el contenido exacto del archivo, descarga con nombre no listado (simulando un intento de path traversal) devuelve 404.

`python manage.py test` completo: 99/99 en verde. `python manage.py check`: sin issues.
