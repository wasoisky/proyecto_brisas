# Diseño: Corrección de roles y accesos — módulo Usuarios

**Fecha:** 2026-06-10
**Módulo:** `usuarios`
**Tipo:** Corrección de bugs (seguridad + calidad de código)
**Archivos afectados:** `usuarios/forms.py`, `usuarios/views.py`, `usuarios/mixins.py`

---

## Contexto

El módulo `usuarios` implementa CRUD de usuarios, control de acceso por rol (`RolRequiredMixin`) y log de accesos (`RegistroAcceso`). La revisión identificó cuatro problemas — dos de seguridad y dos de calidad de código — que se corrigen en esta sesión.

---

## Correcciones

### S-01 — Validadores de contraseña en `AdminPasswordResetForm`

**Archivo:** `usuarios/forms.py`  
**Problema:** `AdminPasswordResetForm.clean()` solo verifica que las dos contraseñas coincidan. No ejecuta los validadores de Django (`AUTH_PASSWORD_VALIDATORS`), permitiendo contraseñas débiles como "123".

**Solución:**
- Importar `validate_password` de `django.contrib.auth.password_validation`.
- En `clean()`, después de confirmar que `p1 == p2`, llamar `validate_password(p1)`.
- Capturar la `ValidationError` resultante y adjuntarla al campo `password1` con `self.add_error('password1', e)`.

**Invariante:** si `AUTH_PASSWORD_VALIDATORS` está vacío en settings, `validate_password` no lanza error — comportamiento correcto para tests y desarrollo.

---

### S-02 — Prevenir auto-cambio de rol en `UsuarioUpdateView`

**Archivo:** `usuarios/views.py`  
**Problema:** `form_valid()` impide que un admin se auto-desactive, pero no impide que cambie su propio rol a `PROD` o `DIST`, quedando bloqueado fuera de todas las vistas de administración.

**Solución:**
- En `form_valid()`, después del chequeo de auto-desactivación, agregar:
  ```
  Si usuario.pk == request.user.pk Y cleaned_data['rol'] != 'ADMIN':
      → error "No puedes cambiar tu propio rol."
      → return self.form_invalid(form)
  ```
- El error se adjunta como mensaje de formulario (no de campo), usando `form.add_error('rol', ...)`.

**Alcance:** la protección es unidireccional — solo bloquea el degradado de rol propio. Un admin puede cambiar el rol de otros usuarios sin restricción.

---

### Q-01 — Eliminar doble query en `UsuarioUpdateView.get()`

**Archivo:** `usuarios/views.py`  
**Problema:** `get()` llama `self.get_object()` manualmente para verificar si el objeto es superusuario, y luego delega en `super().get()` que internamente vuelve a llamar `self.get_object()`. Dos queries a la BD por cada GET.

**Solución:** Reemplazar el cuerpo de `get()` por la secuencia equivalente a `BaseUpdateView.get()`, reutilizando el objeto ya cargado:

```python
def get(self, request, *args, **kwargs):
    self.object = self.get_object()
    if self.object is None:
        return redirect('usuarios:lista')
    return self.render_to_response(self.get_context_data())
```

**Sin cambios en `post()`:** `BaseUpdateView.post()` llama `get_object()` una sola vez — no hay doble query en POST.

---

### Q-02 — `roles_permitidos` como tupla inmutable

**Archivo:** `usuarios/mixins.py`  
**Problema:** Las constantes `TODOS`, `ADMIN_PROD`, `SOLO_ADMIN`, `ADMIN_DIST` son listas mutables. Si cualquier código llama `.append()` sobre alguna, modifica el estado compartido de todas las vistas que la usan.

**Solución:** Convertir todas las constantes a tuplas y actualizar el tipo del atributo de clase:

```python
TODOS      = ('ADMIN', 'PROD', 'DIST')
ADMIN_PROD = ('ADMIN', 'PROD')
SOLO_ADMIN = ('ADMIN',)
ADMIN_DIST = ('ADMIN', 'DIST')

roles_permitidos: tuple[str, ...] = ()
```

**Sin cambios en consumidores:** el operador `in` y las asignaciones `roles_permitidos = SOLO_ADMIN` funcionan igual con tuplas.

---

## Archivos y líneas

| Fix | Archivo | Método/sección |
|-----|---------|----------------|
| S-01 | `usuarios/forms.py` | `AdminPasswordResetForm.clean()` |
| S-02 | `usuarios/views.py` | `UsuarioUpdateView.form_valid()` |
| Q-01 | `usuarios/views.py` | `UsuarioUpdateView.get()` |
| Q-02 | `usuarios/mixins.py` | Constantes + `roles_permitidos` |

---

## Lo que NO cambia

- Modelos, migraciones y señales — sin tocar.
- Templates — sin tocar.
- URLs — sin tocar.
- `UsuarioSetPasswordView` — usa `get_object_or_404`, no tiene el mismo problema que Q-01.
- La lógica de redirect por rol en `config/urls.py` — fuera de scope de esta sesión.
