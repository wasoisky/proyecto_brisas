# Correcciones de roles y accesos — módulo Usuarios

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corregir cuatro problemas identificados en el módulo `usuarios`: dos de seguridad (S-01, S-02) y dos de calidad de código (Q-01, Q-02).

**Architecture:** Cambios quirúrgicos en tres archivos del módulo `usuarios`. Cada fix es independiente. Se aplica TDD: test primero, implementación mínima después, commit por cada fix.

**Tech Stack:** Python 3.13, Django 5.2, `django.test.TestCase`, `assertNumQueries`, `override_settings`.

**Test runner:** `venv/Scripts/python manage.py test usuarios --verbosity=2`

---

## Mapa de archivos

| Archivo | Rol en este plan |
|---------|-----------------|
| `usuarios/tests.py` | Crear todos los tests (actualmente vacío) |
| `usuarios/mixins.py` | Q-02: listas → tuplas |
| `usuarios/forms.py` | S-01: agregar `validate_password` |
| `usuarios/views.py` | Q-01: eliminar doble query · S-02: bloquear auto-cambio de rol |

---

## Task 1: Infraestructura de tests

**Files:**
- Modify: `usuarios/tests.py`

- [ ] **Step 1: Reemplazar el contenido de `usuarios/tests.py` con la clase base**

```python
from django.test import TestCase
from django.urls import reverse
from .models import Usuario


class UsuarioTestMixin:
    """Helpers compartidos por los TestCase del módulo."""

    def crear_admin(self, username='maximino', password='brisas2024'):
        return Usuario.objects.create_user(
            username=username,
            password=password,
            rol='ADMIN',
            first_name='Admin',
            last_name='Test',
        )

    def crear_usuario(self, username, rol, password='brisas2024'):
        return Usuario.objects.create_user(
            username=username,
            password=password,
            rol=rol,
            first_name='Test',
            last_name='User',
        )
```

- [ ] **Step 2: Verificar que el runner arranca sin errores**

Ejecutar: `venv/Scripts/python manage.py test usuarios --verbosity=2`

Salida esperada:
```
Ran 0 tests in 0.000s
OK
```

---

## Task 2: Q-02 — Tuplas inmutables en `mixins.py`

**Files:**
- Modify: `usuarios/mixins.py`
- Modify: `usuarios/tests.py`

- [ ] **Step 1: Agregar `MixinsTests` a `usuarios/tests.py`**

Añadir al final del archivo:

```python
from .mixins import TODOS, ADMIN_PROD, SOLO_ADMIN, ADMIN_DIST, RolRequiredMixin


class MixinsTests(TestCase):
    def test_role_constants_son_tuplas(self):
        self.assertIsInstance(TODOS, tuple)
        self.assertIsInstance(ADMIN_PROD, tuple)
        self.assertIsInstance(SOLO_ADMIN, tuple)
        self.assertIsInstance(ADMIN_DIST, tuple)

    def test_roles_permitidos_default_es_tupla(self):
        self.assertIsInstance(RolRequiredMixin.roles_permitidos, tuple)
```

- [ ] **Step 2: Ejecutar el test — verificar que falla**

Ejecutar: `venv/Scripts/python manage.py test usuarios.tests.MixinsTests --verbosity=2`

Salida esperada:
```
FAIL: test_role_constants_son_tuplas
AssertionError: <class 'list'> is not <class 'tuple'>
```

- [ ] **Step 3: Implementar el fix en `usuarios/mixins.py`**

Reemplazar las cuatro constantes y el atributo de clase:

```python
TODOS      = ('ADMIN', 'PROD', 'DIST')
ADMIN_PROD = ('ADMIN', 'PROD')
SOLO_ADMIN = ('ADMIN',)
ADMIN_DIST = ('ADMIN', 'DIST')


class RolRequiredMixin(LoginRequiredMixin):
    """
    Reemplaza LoginRequiredMixin en todas las vistas del proyecto.
    Declara `roles_permitidos` en cada vista para controlar el acceso.
    Los superusuarios técnicos (is_superuser) siempre tienen acceso.
    """
    roles_permitidos: tuple[str, ...] = ()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.is_superuser or request.user.rol in self.roles_permitidos:
            return super().dispatch(request, *args, **kwargs)
        messages.error(request, 'No tienes permiso para acceder a esta sección.')
        destino = INICIO_POR_ROL.get(request.user.rol, '/')
        return redirect(destino)
```

- [ ] **Step 4: Ejecutar el test — verificar que pasa**

Ejecutar: `venv/Scripts/python manage.py test usuarios.tests.MixinsTests --verbosity=2`

Salida esperada:
```
test_role_constants_son_tuplas ... ok
test_roles_permitidos_default_es_tupla ... ok
Ran 2 tests in 0.001s
OK
```

- [ ] **Step 5: Commit**

```bash
git add usuarios/mixins.py usuarios/tests.py
git commit -m "fix: convertir constantes de roles a tuplas inmutables (Q-02)"
```

---

## Task 3: S-01 — Validadores de contraseña en `AdminPasswordResetForm`

**Files:**
- Modify: `usuarios/forms.py`
- Modify: `usuarios/tests.py`

- [ ] **Step 1: Agregar `AdminPasswordResetFormTests` a `usuarios/tests.py`**

Añadir al final del archivo:

```python
from django.test import override_settings
from .forms import AdminPasswordResetForm

_VALIDATORS_MINIMOS = [
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8},
    },
]


class AdminPasswordResetFormTests(TestCase):
    @override_settings(AUTH_PASSWORD_VALIDATORS=_VALIDATORS_MINIMOS)
    def test_contrasena_corta_es_rechazada(self):
        form = AdminPasswordResetForm(data={'password1': '123', 'password2': '123'})
        self.assertFalse(form.is_valid())
        self.assertIn('password1', form.errors)

    @override_settings(AUTH_PASSWORD_VALIDATORS=_VALIDATORS_MINIMOS)
    def test_contrasena_fuerte_es_aceptada(self):
        form = AdminPasswordResetForm(
            data={'password1': 'Brisas2024!', 'password2': 'Brisas2024!'}
        )
        self.assertTrue(form.is_valid())

    def test_contrasenas_distintas_son_rechazadas(self):
        form = AdminPasswordResetForm(
            data={'password1': 'Brisas2024!', 'password2': 'OtroValor2024!'}
        )
        self.assertFalse(form.is_valid())
```

- [ ] **Step 2: Ejecutar los tests — verificar que el primero falla**

Ejecutar: `venv/Scripts/python manage.py test usuarios.tests.AdminPasswordResetFormTests --verbosity=2`

Salida esperada:
```
test_contrasena_corta_es_rechazada ... FAIL
test_contrasena_fuerte_es_aceptada ... ok
test_contrasenas_distintas_son_rechazadas ... ok
```

`test_contrasena_corta_es_rechazada` debe fallar porque actualmente el form acepta "123" si ambas contraseñas coinciden.

- [ ] **Step 3: Implementar el fix en `usuarios/forms.py`**

Agregar la importación al inicio del archivo:

```python
from django.contrib.auth.password_validation import validate_password
```

Reemplazar el método `clean` de `AdminPasswordResetForm`:

```python
def clean(self):
    cleaned = super().clean()
    p1 = cleaned.get('password1')
    p2 = cleaned.get('password2')
    if p1 and p2 and p1 != p2:
        raise forms.ValidationError('Las contraseñas no coinciden.')
    if p1:
        try:
            validate_password(p1)
        except forms.ValidationError as e:
            self.add_error('password1', e)
    return cleaned
```

- [ ] **Step 4: Ejecutar los tests — verificar que pasan todos**

Ejecutar: `venv/Scripts/python manage.py test usuarios.tests.AdminPasswordResetFormTests --verbosity=2`

Salida esperada:
```
test_contrasena_corta_es_rechazada ... ok
test_contrasena_fuerte_es_aceptada ... ok
test_contrasenas_distintas_son_rechazadas ... ok
Ran 3 tests in 0.002s
OK
```

- [ ] **Step 5: Commit**

```bash
git add usuarios/forms.py usuarios/tests.py
git commit -m "fix: aplicar validadores Django en AdminPasswordResetForm (S-01)"
```

---

## Task 4: S-02 — Prevenir auto-cambio de rol en `UsuarioUpdateView`

**Files:**
- Modify: `usuarios/views.py`
- Modify: `usuarios/tests.py`

- [ ] **Step 1: Agregar `UsuarioUpdateViewTests` a `usuarios/tests.py`**

Añadir al final del archivo:

```python
class UsuarioUpdateViewTests(UsuarioTestMixin, TestCase):
    def setUp(self):
        self.admin = self.crear_admin()
        self.client.login(username='maximino', password='brisas2024')

    def test_admin_no_puede_cambiar_su_propio_rol(self):
        response = self.client.post(
            reverse('usuarios:editar', args=[self.admin.pk]),
            data={
                'first_name': 'Admin',
                'last_name': 'Test',
                'email': '',
                'telefono': '',
                'rol': 'PROD',
                'is_active': True,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.rol, 'ADMIN')

    def test_admin_puede_cambiar_rol_de_otro_usuario(self):
        otro = self.crear_usuario('nicolas', rol='PROD')
        response = self.client.post(
            reverse('usuarios:editar', args=[otro.pk]),
            data={
                'first_name': 'Test',
                'last_name': 'User',
                'email': '',
                'telefono': '',
                'rol': 'DIST',
                'is_active': True,
            },
        )
        self.assertRedirects(response, reverse('usuarios:lista'))
        otro.refresh_from_db()
        self.assertEqual(otro.rol, 'DIST')
```

- [ ] **Step 2: Ejecutar los tests — verificar que el primero falla**

Ejecutar: `venv/Scripts/python manage.py test usuarios.tests.UsuarioUpdateViewTests --verbosity=2`

Salida esperada:
```
test_admin_no_puede_cambiar_su_propio_rol ... FAIL
test_admin_puede_cambiar_rol_de_otro_usuario ... ok
```

`test_admin_no_puede_cambiar_su_propio_rol` debe fallar porque actualmente el cambio de rol propio se guarda sin restricción.

- [ ] **Step 3: Implementar el fix en `usuarios/views.py`**

Reemplazar `form_valid` en `UsuarioUpdateView`:

```python
def form_valid(self, form):
    usuario = form.save(commit=False)
    if usuario.pk == self.request.user.pk and not form.cleaned_data.get('is_active', True):
        messages.error(self.request, 'No puedes desactivar tu propia cuenta.')
        return self.form_invalid(form)
    if usuario.pk == self.request.user.pk and form.cleaned_data.get('rol') != 'ADMIN':
        messages.error(self.request, 'No puedes cambiar tu propio rol.')
        form.add_error('rol', 'No puedes cambiar tu propio rol.')
        return self.form_invalid(form)
    usuario.save()
    messages.success(self.request, f'Usuario "{usuario.username}" actualizado.')
    return redirect(self.success_url)
```

- [ ] **Step 4: Ejecutar los tests — verificar que pasan todos**

Ejecutar: `venv/Scripts/python manage.py test usuarios.tests.UsuarioUpdateViewTests --verbosity=2`

Salida esperada:
```
test_admin_no_puede_cambiar_su_propio_rol ... ok
test_admin_puede_cambiar_rol_de_otro_usuario ... ok
Ran 2 tests in 0.050s
OK
```

- [ ] **Step 5: Commit**

```bash
git add usuarios/views.py usuarios/tests.py
git commit -m "fix: bloquear auto-cambio de rol en UsuarioUpdateView (S-02)"
```

---

## Task 5: Q-01 — Eliminar doble query en `UsuarioUpdateView.get()`

**Files:**
- Modify: `usuarios/views.py`
- Modify: `usuarios/tests.py`

- [ ] **Step 1: Agregar test de regresión a `UsuarioUpdateViewTests` en `usuarios/tests.py`**

Agregar dentro de `UsuarioUpdateViewTests`:

```python
def test_editar_superusuario_redirige_a_lista(self):
    super_user = Usuario.objects.create_superuser(
        username='superadmin',
        password='brisas2024',
    )
    response = self.client.get(reverse('usuarios:editar', args=[super_user.pk]))
    self.assertRedirects(response, reverse('usuarios:lista'))

def test_get_editar_usuario_normal_renderiza_formulario(self):
    otro = self.crear_usuario('cesar', rol='PROD')
    response = self.client.get(reverse('usuarios:editar', args=[otro.pk]))
    self.assertEqual(response.status_code, 200)
    self.assertContains(response, 'cesar')
```

- [ ] **Step 2: Ejecutar los tests — verificar que pasan (son regresión, no TDD de nueva funcionalidad)**

Ejecutar: `venv/Scripts/python manage.py test usuarios.tests.UsuarioUpdateViewTests --verbosity=2`

Salida esperada: los 4 tests de la clase pasan.

- [ ] **Step 3: Implementar el fix en `usuarios/views.py`**

Reemplazar el método `get` y `get_object` en `UsuarioUpdateView`:

```python
def get_object(self, queryset=None):
    obj = super().get_object(queryset)
    if obj.is_superuser:
        messages.error(self.request, 'No se puede editar un superusuario desde aquí.')
        return None
    return obj

def get(self, request, *args, **kwargs):
    self.object = self.get_object()
    if self.object is None:
        return redirect('usuarios:lista')
    return self.render_to_response(self.get_context_data())
```

- [ ] **Step 4: Ejecutar todos los tests del módulo**

Ejecutar: `venv/Scripts/python manage.py test usuarios --verbosity=2`

Salida esperada:
```
test_admin_no_puede_cambiar_su_propio_rol ... ok
test_admin_puede_cambiar_rol_de_otro_usuario ... ok
test_contrasena_corta_es_rechazada ... ok
test_contrasena_fuerte_es_aceptada ... ok
test_contrasenas_distintas_son_rechazadas ... ok
test_editar_superusuario_redirige_a_lista ... ok
test_get_editar_usuario_normal_renderiza_formulario ... ok
test_role_constants_son_tuplas ... ok
test_roles_permitidos_default_es_tupla ... ok
Ran 9 tests in 0.XXXs
OK
```

- [ ] **Step 5: Commit**

```bash
git add usuarios/views.py usuarios/tests.py
git commit -m "refactor: eliminar doble llamada a get_object() en UsuarioUpdateView (Q-01)"
```
