/**
 * http.js
 * Script común para hablar con la API real cuando exista el backend.
 *
 * 1) Inyecta "Authorization: Bearer <token>" en TODOS los fetch() que van a
 *    la API (aunque se llamen con fetch() directo, sin pasar por acá).
 * 2) Http.get / post / put / patch / delete / subir hacen el pedido y
 *    devuelven SIEMPRE el mismo formato que api.js:
 *        { ok: true,  status, ...datos }
 *        { ok: false, status, motivo }        (status 0 = sin conexión / timeout)
 *    con mensajes de error listos para mostrar en un toast o una alerta.
 * 3) Si el servidor responde 401 en un pedido con sesión, cierra la sesión y
 *    manda a login.html?e=expirada.
 *
 * Cómo se conecta (lo hace quien arma el backend):
 *    Http.configurar({ baseUrl: 'https://tu-api.com' });   // una sola vez
 *    const r = await Http.post('auth/login', { email, password }, { publico: true });
 *    const r = await Http.get('drive/items?padreId=' + id);
 *    const r = await Http.subir('drive/files', formData, { onProgress: p => ... });
 *
 * No toca localStorage de datos ni ninguna base: solo usa la sesión de
 * auth.js para leer el token. Requiere auth.js cargado antes.
 */
const Http = (() => {
  'use strict';

  const CONFIG = {
    baseUrl: '',          // ej: 'https://tu-api.com' ('' = mismo origen que la página)
    timeoutMs: 15000,     // corta pedidos que no responden
    paginaLogin: 'login.html?e=expirada',
  };

  const MENSAJES = {
    0: 'No pudimos conectarnos con el servidor. Revisá tu conexión y probá de nuevo.',
    400: 'Los datos enviados no son válidos.',
    401: 'Tu sesión expiró. Volvé a iniciar sesión.',
    403: 'Tu rol no tiene permiso para hacer esto.',
    404: 'No encontramos lo que buscabas.',
    409: 'Ya existe un elemento con esos datos.',
    413: 'El archivo es demasiado grande.',
    422: 'Revisá los datos: alguno no es válido.',
    429: 'Hiciste demasiados intentos seguidos. Esperá un momento y probá de nuevo.',
    500: 'El servidor tuvo un problema. Probá de nuevo en unos minutos.',
    503: 'El servicio no está disponible por ahora. Probá de nuevo en unos minutos.',
  };
  const MENSAJE_TIMEOUT = 'El servidor tardó demasiado en responder. Probá de nuevo.';

  function configurar(opciones) {
    Object.assign(CONFIG, opciones || {});
  }

  function mensajeDeStatus(status) {
    if (MENSAJES[status]) return MENSAJES[status];
    if (status >= 500) return MENSAJES[500];
    if (status >= 400) return MENSAJES[400];
    return 'Ocurrió un error inesperado. Probá de nuevo.';
  }

  /** Arma la URL final: relativa a baseUrl, o tal cual si ya es absoluta. */
  function urlDe(ruta) {
    if (/^https?:\/\//i.test(ruta)) return ruta;
    const base = String(CONFIG.baseUrl || '').replace(/\/+$/, '');
    return base + '/' + String(ruta).replace(/^\/+/, '');
  }

  /** ¿Este destino es NUESTRA API? (el token nunca se manda a otros sitios) */
  function esNuestraApi(url) {
    try {
      const destino = new URL(url, window.location.href);
      const api = new URL(CONFIG.baseUrl || '/', window.location.href);
      return destino.origin === api.origin;
    } catch {
      return false;
    }
  }

  // ---------------------------------------------------------------
  // (1) Interceptor de fetch: agrega Authorization a los pedidos a la API
  // ---------------------------------------------------------------
  let instalado = false;

  function instalar() {
    if (instalado || typeof window.fetch !== 'function') return;
    const fetchOriginal = window.fetch.bind(window);
    window.fetch = function (entrada, init) {
      const opciones = init ? { ...init } : {};
      const url = typeof entrada === 'string' ? entrada : (entrada && entrada.url) || '';
      const sinAuth = !!opciones.sinAuth; // { sinAuth: true } para endpoints públicos (login, registro)
      delete opciones.sinAuth;
      if (!sinAuth && esNuestraApi(url)) {
        const token = Auth.obtenerToken();
        if (token) {
          const headers = new Headers(opciones.headers || (entrada && entrada.headers) || {});
          if (!headers.has('Authorization')) headers.set('Authorization', `Bearer ${token}`);
          opciones.headers = headers;
        }
      }
      return fetchOriginal(entrada, opciones);
    };
    instalado = true;
  }

  // ---------------------------------------------------------------
  // (2) Pedidos con formato de respuesta unificado
  // ---------------------------------------------------------------
  const avisarCarga = (delta) => {
    document.dispatchEvent(new CustomEvent('cc:carga', { detail: { delta } })); // la barra de carga de ui.js escucha esto
  };

  function sesionExpirada() {
    Auth.cerrarSesion();
    Auth.irA(CONFIG.paginaLogin);
  }

  /** Convierte status + texto de respuesta en { ok, status, ... } o { ok:false, status, motivo }. */
  function normalizar(status, texto, publico) {
    let datos = null;
    if (texto) { try { datos = JSON.parse(texto); } catch { datos = null; } }

    if (status === 401 && !publico) {
      sesionExpirada();
      return { ok: false, status, motivo: MENSAJES[401] };
    }
    if (status >= 200 && status < 300) {
      if (datos && typeof datos === 'object' && !Array.isArray(datos)) return { ok: true, status, ...datos };
      return { ok: true, status, datos };
    }
    const motivo = datos && (datos.motivo || datos.message || datos.error);
    const campo = datos && datos.campo ? { campo: datos.campo } : {};
    return { ok: false, status, motivo: typeof motivo === 'string' && motivo ? motivo : mensajeDeStatus(status), ...campo };
  }

  async function pedir(metodo, ruta, { cuerpo, headers = {}, publico = false, timeoutMs = CONFIG.timeoutMs } = {}) {
    instalar();
    const url = urlDe(ruta);
    const h = { Accept: 'application/json', ...headers };
    const esForm = typeof FormData !== 'undefined' && cuerpo instanceof FormData;
    if (cuerpo !== undefined && !esForm && !h['Content-Type']) h['Content-Type'] = 'application/json';

    const ctrl = typeof AbortController !== 'undefined' ? new AbortController() : null;
    let venció = false;
    const timer = ctrl && timeoutMs ? setTimeout(() => { venció = true; ctrl.abort(); }, timeoutMs) : null;

    avisarCarga(1);
    try {
      const resp = await fetch(url, {
        method: metodo,
        headers: h,
        body: cuerpo === undefined ? undefined : (esForm ? cuerpo : JSON.stringify(cuerpo)),
        signal: ctrl ? ctrl.signal : undefined,
        sinAuth: publico, // el interceptor de arriba lo lee y no agrega el token
      });
      const texto = await resp.text();
      return normalizar(resp.status, texto, publico);
    } catch (e) {
      return { ok: false, status: 0, motivo: venció ? MENSAJE_TIMEOUT : MENSAJES[0], red: true };
    } finally {
      if (timer) clearTimeout(timer);
      avisarCarga(-1);
    }
  }

  /**
   * Sube un FormData con progreso real (fetch no informa el progreso de
   * subida; XMLHttpRequest sí). onProgress recibe un número de 0 a 100.
   */
  function subir(ruta, formData, { metodo = 'POST', onProgress = null, publico = false, timeoutMs = 0 } = {}) {
    return new Promise((resolve) => {
      const url = urlDe(ruta);
      const xhr = new XMLHttpRequest();
      xhr.open(metodo, url);
      xhr.setRequestHeader('Accept', 'application/json');
      if (!publico && esNuestraApi(url)) {
        const token = Auth.obtenerToken();
        if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);
      }
      if (timeoutMs) xhr.timeout = timeoutMs;
      if (onProgress && xhr.upload) {
        xhr.upload.onprogress = (e) => { if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100)); };
      }
      avisarCarga(1);
      const terminar = (r) => { avisarCarga(-1); resolve(r); };
      xhr.onload = () => {
        if (onProgress && xhr.status >= 200 && xhr.status < 300) onProgress(100);
        terminar(normalizar(xhr.status, xhr.responseText, publico));
      };
      xhr.onerror = () => terminar({ ok: false, status: 0, motivo: MENSAJES[0], red: true });
      xhr.ontimeout = () => terminar({ ok: false, status: 0, motivo: MENSAJE_TIMEOUT, red: true });
      xhr.onabort = () => terminar({ ok: false, status: 0, motivo: 'Se canceló la subida.', red: true });
      xhr.send(formData);
    });
  }

  instalar();

  return {
    configurar, instalar, mensajeDeStatus,
    get: (ruta, o) => pedir('GET', ruta, o),
    post: (ruta, cuerpo, o) => pedir('POST', ruta, { ...o, cuerpo }),
    put: (ruta, cuerpo, o) => pedir('PUT', ruta, { ...o, cuerpo }),
    patch: (ruta, cuerpo, o) => pedir('PATCH', ruta, { ...o, cuerpo }),
    delete: (ruta, o) => pedir('DELETE', ruta, o),
    subir,
  };
})();