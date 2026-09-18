/**
 * Filtrado en vivo para listados con formulario GET + paginación.
 * En vez de recargar la página, reenvía el formulario por fetch() y
 * reemplaza solo el contenedor de resultados con la respuesta parcial
 * del servidor (la vista debe devolver el fragmento cuando detecta la
 * cabecera X-Requested-With: XMLHttpRequest).
 *
 * El botón de enviar / Enter siguen funcionando como último recurso
 * manual; si JS falla, el formulario se comporta como un GET normal.
 */
function initFiltroVivo(formId, resultadosId, opciones) {
  const form = document.getElementById(formId);
  const resultados = document.getElementById(resultadosId);
  if (!form || !resultados) return;

  const espera = (opciones && opciones.espera) || 350;
  let temporizador = null;

  function mostrarErrorCarga() {
    let aviso = resultados.querySelector(':scope > .aviso-error-filtro');
    if (aviso) return;
    aviso = document.createElement('div');
    aviso.className = 'alert alert-warning alert-dismissible fade show aviso-error-filtro';
    aviso.setAttribute('role', 'alert');
    aviso.innerHTML =
      'No se pudo actualizar la lista. Revisa tu conexión e intenta de nuevo.' +
      '<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Cerrar"></button>';
    resultados.prepend(aviso);
  }

  function cargar(destino) {
    resultados.classList.add('opacity-50');
    fetch(destino, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then((resp) => {
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        return resp.text();
      })
      .then((html) => {
        resultados.innerHTML = html;
        history.replaceState(null, '', destino);
        if (window.initTooltips) window.initTooltips(resultados);
      })
      .catch(mostrarErrorCarga)
      .finally(() => resultados.classList.remove('opacity-50'));
  }

  function buscar() {
    const params = new URLSearchParams(new FormData(form));
    cargar(window.location.pathname + '?' + params.toString());
  }

  // Texto: búsqueda en vivo mientras se escribe, con una pequeña espera
  // para no disparar una petición por cada tecla.
  form.querySelectorAll('input[type="text"], input[type="search"]').forEach(function (campo) {
    campo.addEventListener('input', function () {
      clearTimeout(temporizador);
      temporizador = setTimeout(buscar, espera);
    });
  });

  // Selects, checkboxes y fechas filtran de inmediato al cambiar.
  form.querySelectorAll('select, input[type="checkbox"], input[type="date"]').forEach(function (campo) {
    campo.addEventListener('change', buscar);
  });

  // El botón de enviar (o Enter) queda como último recurso: si no se
  // quiere esperar la búsqueda en vivo, fuerza la misma petición ya.
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    clearTimeout(temporizador);
    buscar();
  });

  // La paginación, dentro del propio contenedor de resultados, también
  // navega sin recargar la página completa.
  resultados.addEventListener('click', function (e) {
    const link = e.target.closest('a.page-link');
    if (!link) return;
    const href = link.getAttribute('href');
    if (!href || href === '#') return;
    e.preventDefault();
    cargar(link.href);
  });
}
