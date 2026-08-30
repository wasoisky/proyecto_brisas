from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario, RegistroAcceso


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ('username', 'get_full_name', 'email', 'rol', 'is_active')
    list_filter = ('rol', 'is_active', 'is_staff')
    fieldsets = UserAdmin.fieldsets + (
        ('Brisas de Pacandé', {'fields': ('rol', 'telefono')}),
    )

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj is not None and obj.pk == request.user.pk:
            readonly.append('rol')
        return readonly


@admin.register(RegistroAcceso)
class RegistroAccesoAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'accion', 'username_intento', 'usuario', 'ip')
    list_filter = ('accion',)
    search_fields = ('username_intento', 'ip')
    readonly_fields = ('timestamp', 'usuario', 'username_intento', 'accion', 'ip', 'user_agent')
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
