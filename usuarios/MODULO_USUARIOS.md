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

## Backlog futuro

- [ ] U-01 Agregar `post()` guard + reemplazar `get_object()` con `get_object_or_404` (U-05)
- [ ] U-02 Pasar `user=usuario` a `validate_password` en `AdminPasswordResetForm`
- [ ] U-03 Marcar `rol` como `readonly_fields` en `UsuarioAdmin` o agregar `save_model()` con la misma restricción
- [ ] U-04 Unificar mecanismo de error: solo `form.add_error` en guards de `form_valid()`
- [ ] U-06 Consolidar los dos guards de auto-protección en un solo bloque `if`
