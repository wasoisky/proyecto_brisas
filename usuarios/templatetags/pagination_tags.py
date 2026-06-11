from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def url_replace(context, **kwargs):
    """Devuelve el querystring actual reemplazando los parámetros indicados.
    Uso: href="?{% url_replace page=page_obj.next_page_number %}"
    Preserva todos los filtros activos (q, estado, fecha, etc.) al paginar.
    """
    params = context['request'].GET.copy()
    for key, val in kwargs.items():
        params[key] = val
    return params.urlencode()
