/**
 * ui.js
 * Piezas de interfaz reutilizables: escape de HTML, iconos, formato,
 * barra superior compartida, toasts, diálogos (confirmar / aviso /
 * formulario genérico), menú contextual flotante y tabla genérica con
 * orden y paginación.
 * Todas las clases nuevas llevan prefijo "dc-" (o son propias) para no
 * chocar con las de Bootstrap.
 */
const UI = (() => {
  'use strict';

  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  let _uid = 0;
  const uid = (p = 'dc') => `${p}-${++_uid}`;

  const normalizar = (t) => String(t || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();

  // ---------------------------------------------------------------
  // Iconos
  // ---------------------------------------------------------------
  const p = (d) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${d}</svg>`;
  const iconos = {
    carpeta: p('<path d="M3 7a1 1 0 0 1 1-1h5l2 2h9a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7Z"/>'),
    nube: p('<path d="M4 14.9A7 7 0 1 1 15.7 8h1.8a4.5 4.5 0 0 1 2.5 8.2"/><path d="M12 12v9"/><path d="m16 16-4-4-4 4"/>'),
    compartir: p('<circle cx="7" cy="12" r="2.4"/><circle cx="17" cy="6" r="2.4"/><circle cx="17" cy="18" r="2.4"/><path d="m9 10.8 6-3.6M9 13.2l6 3.6"/>'),
    papelera: p('<path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2m-9 0 1 12a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-12"/>'),
    usuario: p('<circle cx="12" cy="8" r="3.5"/><path d="M5 20c1.2-3.5 4-5.2 7-5.2s5.8 1.7 7 5.2"/>'),
    usuarios: p('<circle cx="9" cy="8" r="3"/><path d="M3 20c.9-3 3.2-4.5 6-4.5s5.1 1.5 6 4.5"/><circle cx="17" cy="9" r="2.4"/><path d="M17 14.5c2 .2 3.4 1.5 4 3.5"/>'),
    mas: p('<path d="M12 5v14M5 12h14"/>'),
    editar: p('<path d="M4 20h4L18.5 9.5a2.1 2.1 0 0 0-3-3L5 17v3Z"/><path d="m14 6.5 3 3"/>'),
    descargar: p('<path d="M12 4v11m0 0-4-4m4 4 4-4"/><path d="M5 19h14"/>'),
    subir: p('<path d="M12 16V5m0 0-4 4m4-4 4 4"/><path d="M5 19h14"/>'),
    mover: p('<path d="M3 7a1 1 0 0 1 1-1h5l2 2h9a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7Z"/><path d="M9 13h6m0 0-2-2m2 2-2 2"/>'),
    abrir: p('<path d="M5 12h14m0 0-5-5m5 5-5 5"/>'),
    restaurar: p('<path d="M4 12a8 8 0 1 0 2.5-5.8"/><path d="M4 4v4h4"/>'),
    lupa: p('<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>'),
    menu: p('<path d="M4 6h16M4 12h16M4 18h16"/>'),
    info: p('<circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16h.01"/>'),
    cerrar: p('<path d="M6 6l12 12M18 6 6 18"/>'),
    check: p('<path d="m5 12 5 5 9-10"/>'),
    escudo: p('<path d="M12 3 5 6v5c0 4.5 3 8 7 10 4-2 7-5.5 7-10V6l-7-3Z"/>'),
    politicas: p('<circle cx="12" cy="12" r="3"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1"/>'),
    salir: p('<path d="M9 4H5a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h4"/><path d="M16 8l4 4-4 4M20 12H9"/>'),
    reloj: p('<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>'),
    disco: p('<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>'),
    chevron: p('<path d="m6 9 6 6 6-6"/>'),
    kebab: '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false"><circle cx="12" cy="5" r="1.7"/><circle cx="12" cy="12" r="1.7"/><circle cx="12" cy="19" r="1.7"/></svg>',
  };

  // ---------------------------------------------------------------
  // Tipos de archivo (chip de color con la extensión + filtro "Todos los tipos")
  // ---------------------------------------------------------------
  const TIPOS = [
    { valor: 'todos', texto: 'Todos los tipos' },
    { valor: 'documentos', texto: 'Documentos', ext: ['pdf', 'doc', 'docx', 'odt', 'txt', 'rtf', 'md'] },
    { valor: 'hojas', texto: 'Hojas de cálculo', ext: ['xls', 'xlsx', 'csv', 'ods'] },
    { valor: 'presentaciones', texto: 'Presentaciones', ext: ['ppt', 'pptx', 'odp'] },
    { valor: 'imagenes', texto: 'Imágenes', ext: ['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'bmp', 'ico'] },
    { valor: 'comprimidos', texto: 'Comprimidos', ext: ['zip', 'rar', '7z', 'tar', 'gz'] },
    { valor: 'codigo', texto: 'Código y datos', ext: ['sql', 'js', 'ts', 'html', 'css', 'json', 'xml', 'py', 'java', 'c', 'cpp', 'php'] },
    { valor: 'otros', texto: 'Otros' },
  ];

  function tipoDeArchivo(ext) {
    const e = String(ext || '').toLowerCase();
    const t = TIPOS.find(x => x.ext && x.ext.includes(e));
    return t ? t.valor : 'otros';
  }

  function iconoArchivo(ext) {
    const e = String(ext || '').toLowerCase();
    const clase = e === 'pdf' ? 'pdf' : tipoDeArchivo(e);
    return `<span class="dc-ftype dc-ft-${clase}" aria-hidden="true">${esc((e || 'file').slice(0, 4))}</span>`;
  }

  const iconoNodo = (n) => n.tipo === 'carpeta'
    ? `<span class="dc-ftype dc-ft-carpeta" aria-hidden="true">${iconos.carpeta}</span>`
    : iconoArchivo(n.ext);

  // ---------------------------------------------------------------
  // Formato
  // ---------------------------------------------------------------
  function formatoTamanio(mb, { cero = '—' } = {}) {
    if (!mb || mb <= 0) return cero;
    const corto = (n, dec) => String(parseFloat(n.toFixed(dec))); // 25.0 → "25", 2.4 → "2.4"
    if (mb < 1) return Math.max(1, Math.round(mb * 1024)) + ' KB';
    if (mb >= 1024) return corto(mb / 1024, mb >= 10240 ? 0 : 1) + ' GB';
    return (mb >= 100 ? Math.round(mb) : corto(mb, 1)) + ' MB';
  }

  function formatoFecha(valor) {
    const d = new Date(valor);
    if (isNaN(d)) return '—';
    return d.toLocaleDateString('es-AR', { day: 'numeric', month: 'short', year: 'numeric' });
  }

  // Saltea los títulos ("Lic.", "Dr.") para que "Lic. Laura Méndez" sea LM.
  function iniciales(nombre) {
    const i = String(nombre || '').split(' ').filter(x => x && !x.endsWith('.')).slice(0, 2).map(x => x[0].toUpperCase()).join('');
    return i || '?';
  }

  // Un color de avatar estable por cuenta (0 a 4, ver .av-0 … .av-4 en el CSS).
  function colorAvatar(id) {
    return Array.from(String(id || '')).reduce((a, c) => a + c.charCodeAt(0), 0) % 5;
  }

  function badge(texto, tipo = 'neutral', titulo = '') {
    return `<span class="dc-badge dc-badge-${tipo}"${titulo ? ` title="${esc(titulo)}"` : ''}>${esc(texto)}</span>`;
  }

  const ROL_CORTO = { alumno: 'Alumno', docente: 'Docente', admin: 'Admin' };
  function badgeRol(rol) {
    return `<span class="dc-role dc-role-${esc(rol)}">${esc(ROL_CORTO[rol] || rol)}</span>`;
  }

  // ---------------------------------------------------------------
  // Barra superior y barra lateral compartidas por index.html y admin.html
  // ---------------------------------------------------------------
  function topbarHtml(usuario, { placeholder = 'Buscar archivos y carpetas…' } = {}) {
    const mac = /Mac|iPhone|iPad/i.test(navigator.platform || navigator.userAgent || '');
    return `
      <button type="button" class="menu-toggle" id="btnMenu" aria-label="Abrir menú" aria-controls="cabinet" aria-expanded="false">${iconos.menu}</button>
      <a class="brand" href="index.html" aria-label="CampusCloud, ir al inicio"><span class="brand-mark">${iconos.nube}</span><span class="brand-name">CampusCloud</span></a>
      <div class="search">
        ${iconos.lupa}
        <label for="searchInput" class="visually-hidden">Buscar archivos y carpetas</label>
        <input type="search" id="searchInput" placeholder="${esc(placeholder)}" autocomplete="off">
        <kbd class="kbd-hint" aria-hidden="true">${mac ? '⌘K' : 'Ctrl K'}</kbd>
      </div>
      <div class="topbar-right">
        <button type="button" class="user-chip" id="btnCuenta" aria-label="Mi cuenta: ${esc(usuario.nombre)}">
          <span class="avatar" aria-hidden="true">${esc(iniciales(usuario.nombre))}<span class="presence"></span></span>
          <span class="user-meta"><strong>${esc(usuario.nombre)}</strong>${badgeRol(usuario.rol)}</span>
        </button>
        <button type="button" class="btn-logout" id="btnSalir">${iconos.salir}<span>Cerrar sesión</span></button>
      </div>`;
  }

  /** Ctrl/⌘ + K enfoca el buscador. */
  function atajoBuscar(input) {
    document.addEventListener('keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        input.focus();
        input.select();
      }
    });
  }

  /** Conecta el botón de menú (móvil) con la barra lateral. Devuelve cerrar(). */
  function enlazarSidebar() {
    const cab = document.getElementById('cabinet');
    const back = document.getElementById('backdrop');
    const btn = document.getElementById('btnMenu');
    const cerrar = () => {
      cab.classList.remove('open');
      back.classList.remove('open');
      btn.setAttribute('aria-expanded', 'false');
    };
    btn.addEventListener('click', () => {
      const abrir = !cab.classList.contains('open');
      cab.classList.toggle('open', abrir);
      back.classList.toggle('open', abrir);
      btn.setAttribute('aria-expanded', String(abrir));
    });
    back.addEventListener('click', cerrar);
    return cerrar;
  }

  // ---------------------------------------------------------------
  // Toasts
  // ---------------------------------------------------------------
  function toast(mensaje, { tipo = 'info', accion = null, duracion = 5000 } = {}) {
    let cont = document.getElementById('dcToasts');
    if (!cont) {
      cont = document.createElement('div');
      cont.id = 'dcToasts';
      cont.className = 'dc-toasts';
      cont.setAttribute('role', 'status');
      cont.setAttribute('aria-live', 'polite');
      document.body.appendChild(cont);
    }
    const el = document.createElement('div');
    el.className = `dc-toast dc-toast-${tipo}`;
    const txt = document.createElement('span');
    txt.textContent = mensaje;
    el.appendChild(txt);
    const cerrar = () => el.remove();
    if (accion) {
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = accion.texto;
      b.addEventListener('click', () => { cerrar(); accion.fn(); });
      el.appendChild(b);
    }
    cont.appendChild(el);
    setTimeout(cerrar, duracion);
  }

  // ---------------------------------------------------------------
  // Diálogos
  // ---------------------------------------------------------------
  function dialogo(html, { ancho = '' } = {}) {
    const dlg = document.createElement('dialog');
    dlg.className = 'dc-dialog' + (ancho ? ` dc-dialog-${ancho}` : '');
    dlg.innerHTML = html;
    document.body.appendChild(dlg);
    dlg.addEventListener('close', () => dlg.remove());
    dlg.showModal();
    return dlg;
  }

  function confirmar({ titulo, mensaje = '', textoOk = 'Aceptar', peligro = false }) {
    return new Promise(resolve => {
      const id = uid('dlg');
      const dlg = dialogo(`
        <form method="dialog" class="dc-dialog-body">
          <h2 class="dc-dialog-title" id="${id}">${esc(titulo)}</h2>
          ${mensaje ? `<p class="dc-dialog-text">${esc(mensaje)}</p>` : ''}
          <div class="dc-dialog-actions">
            <button type="submit" value="cancel" class="dc-btn dc-btn-ghost" formnovalidate>Cancelar</button>
            <button type="submit" value="ok" class="dc-btn ${peligro ? 'dc-btn-danger' : 'dc-btn-primary'}">${esc(textoOk)}</button>
          </div>
        </form>`);
      dlg.setAttribute('aria-labelledby', id);
      dlg.addEventListener('close', () => resolve(dlg.returnValue === 'ok'));
    });
  }

  function aviso({ titulo, mensaje = '', items = [], textoOk = 'Entendido' }) {
    return new Promise(resolve => {
      const id = uid('dlg');
      const dlg = dialogo(`
        <form method="dialog" class="dc-dialog-body">
          <h2 class="dc-dialog-title" id="${id}">${esc(titulo)}</h2>
          ${mensaje ? `<p class="dc-dialog-text">${esc(mensaje)}</p>` : ''}
          ${items.length ? `<ul class="dc-dialog-list">${items.map(i => `<li>${esc(i)}</li>`).join('')}</ul>` : ''}
          <div class="dc-dialog-actions">
            <button type="submit" class="dc-btn dc-btn-primary">${esc(textoOk)}</button>
          </div>
        </form>`);
      dlg.setAttribute('aria-labelledby', id);
      dlg.addEventListener('close', resolve);
    });
  }

  // ---- Formulario genérico ----
  // campos: [{ nombre, etiqueta, tipo: text|number|email|password|select|textarea|info,
  //            requerido, requeridoSi(datos), mostrarSi(datos), placeholder, ayuda,
  //            opciones:[{valor,texto}], min, max, filas, texto (info), validar(valor, datos) }]
  // alEnviar(datos) puede devolver un mensaje de error (string) para dejar el diálogo abierto.
  // Devuelve una promesa con los datos, o null si se canceló.

  function campoHtml(c, valor, pref) {
    if (c.tipo === 'info') {
      return `<p class="dc-info" data-campo="${esc(c.nombre)}">${c.html ? c.html : esc(c.texto)}</p>`;
    }
    const id = `${pref}-${c.nombre}`;
    const errId = `${id}-err`;
    const ayudaId = `${id}-ayuda`;
    const desc = [c.ayuda ? ayudaId : null, errId].filter(Boolean).join(' ');
    const attrs = `id="${id}" name="${esc(c.nombre)}" aria-describedby="${desc}" aria-invalid="false"${c.requerido ? ' required' : ''}`;
    const v = valor ?? '';
    let control;
    if (c.tipo === 'select') {
      control = `<select ${attrs}>${(c.opciones || []).map(o => `<option value="${esc(o.valor)}"${String(o.valor) === String(v) ? ' selected' : ''}>${esc(o.texto)}</option>`).join('')}</select>`;
    } else if (c.tipo === 'textarea') {
      control = `<textarea ${attrs} rows="${c.filas || 3}" placeholder="${esc(c.placeholder || '')}">${esc(v)}</textarea>`;
    } else {
      const tipo = c.tipo === 'number' ? 'text' : (c.tipo || 'text');
      control = `<input type="${tipo}" ${attrs} value="${esc(v)}" placeholder="${esc(c.placeholder || '')}" autocomplete="off"${c.tipo === 'number' ? ' inputmode="decimal"' : ''}>`;
    }
    return `
      <div class="field" data-campo="${esc(c.nombre)}">
        <label for="${id}">${esc(c.etiqueta)}</label>
        <div class="input-wrap dc-control">${control}</div>
        ${c.ayuda ? `<span class="dc-help" id="${ayudaId}">${esc(c.ayuda)}</span>` : ''}
        <span class="field-error" id="${errId}"></span>
      </div>`;
  }

  function leerValores(form, campos) {
    const v = {};
    campos.forEach(c => {
      if (c.tipo === 'info') return;
      const el = form.elements[c.nombre];
      let val = el ? el.value : '';
      if (c.tipo === 'number') {
        val = String(val).trim().replace(',', '.');
        val = val === '' ? null : Number(val);
      } else if (c.tipo !== 'password') {
        val = String(val).trim();
      }
      v[c.nombre] = val;
    });
    return v;
  }

  function validarCampo(c, val, datos) {
    if (c.tipo === 'info') return null;
    const requerido = c.requerido || (c.requeridoSi && c.requeridoSi(datos));
    const vacio = val === null || val === '';
    if (vacio) return requerido ? (c.msgRequerido || 'Este campo es obligatorio.') : null;
    if (c.tipo === 'number') {
      if (Number.isNaN(val)) return 'Ingresá un número válido.';
      if (c.min != null && val < c.min) return `Debe ser mayor o igual a ${c.min}.`;
      if (c.max != null && val > c.max) return `Debe ser menor o igual a ${c.max}.`;
    }
    if (c.tipo === 'email' && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val)) return 'Ingresá un correo válido.';
    if (c.validar) return c.validar(val, datos) || null;
    return null;
  }

  function formulario({ titulo, descripcion = '', campos, valores = {}, textoOk = 'Guardar', peligro = false, alEnviar = null, ancho = '' }) {
    return new Promise(resolve => {
      const id = uid('dlg');
      const html = `
        <form class="dc-dialog-body" novalidate>
          <h2 class="dc-dialog-title" id="${id}">${esc(titulo)}</h2>
          ${descripcion ? `<p class="dc-dialog-text">${esc(descripcion)}</p>` : ''}
          <div class="auth-alert" data-form-error role="alert" hidden>${iconos.info}<span></span></div>
          ${campos.map(c => campoHtml(c, valores[c.nombre], id)).join('')}
          <div class="dc-dialog-actions">
            <button type="button" class="dc-btn dc-btn-ghost" data-cancelar>Cancelar</button>
            <button type="submit" class="dc-btn ${peligro ? 'dc-btn-danger' : 'dc-btn-primary'}">${esc(textoOk)}</button>
          </div>
        </form>`;
      const dlg = dialogo(html, { ancho });
      dlg.setAttribute('aria-labelledby', id);
      const form = dlg.querySelector('form');
      const alerta = form.querySelector('[data-form-error]');
      const btnOk = form.querySelector('button[type="submit"]');
      let resultado = null;

      const actualizarVisibilidad = () => {
        const datos = leerValores(form, campos);
        campos.forEach(c => {
          if (!c.mostrarSi) return;
          const el = form.querySelector(`[data-campo="${c.nombre}"]`);
          if (el) el.hidden = !c.mostrarSi(datos);
        });
      };
      form.addEventListener('input', actualizarVisibilidad);
      form.addEventListener('change', actualizarVisibilidad);
      actualizarVisibilidad();

      form.querySelector('[data-cancelar]').addEventListener('click', () => dlg.close());

      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        alerta.hidden = true;
        const datos = leerValores(form, campos);
        let primero = null;
        campos.forEach(c => {
          if (c.tipo === 'info') return;
          const cont = form.querySelector(`[data-campo="${c.nombre}"]`);
          const input = form.elements[c.nombre];
          const visible = !cont.hidden;
          const error = visible ? validarCampo(c, datos[c.nombre], datos) : null;
          cont.classList.toggle('has-error', !!error);
          input.setAttribute('aria-invalid', error ? 'true' : 'false');
          cont.querySelector('.field-error').textContent = error || '';
          if (error && !primero) primero = input;
        });
        if (primero) { primero.focus(); return; }

        if (alEnviar) {
          cargando(btnOk, true);
          const msg = await alEnviar(datos);
          cargando(btnOk, false);
          if (msg) {
            alerta.querySelector('span').textContent = msg;
            alerta.hidden = false;
            return;
          }
        }
        resultado = datos;
        dlg.close();
      });

      dlg.addEventListener('close', () => resolve(resultado));
    });
  }

  // ---------------------------------------------------------------
  // Menú contextual flotante (kebab, "Nuevo", "Gestionar", etc.)
  // items: [{ texto, icono, accion, peligro } | { separador: true }]
  // ---------------------------------------------------------------
  let menuEl = null;
  let menuAnchor = null;

  function cerrarMenu(devolverFoco = false) {
    if (menuEl) { menuEl.remove(); menuEl = null; }
    if (menuAnchor) {
      menuAnchor.setAttribute('aria-expanded', 'false');
      if (devolverFoco) menuAnchor.focus();
      menuAnchor = null;
    }
  }

  function menuContextual(anchor, items, { alinear = 'der', minAncho = 190 } = {}) {
    const yaAbierto = menuAnchor === anchor;
    cerrarMenu();
    if (yaAbierto) return;

    menuEl = document.createElement('div');
    menuEl.className = 'ctx-menu';
    menuEl.setAttribute('role', 'menu');
    menuEl.style.minWidth = minAncho + 'px';
    menuEl.style.visibility = 'hidden';
    menuEl.innerHTML = items.map((it, i) => it.separador
      ? '<div class="ctx-sep" role="separator"></div>'
      : `<button type="button" role="menuitem" data-i="${i}" class="${it.peligro ? 'is-danger' : ''}">${it.icono || ''}<span>${esc(it.texto)}</span></button>`
    ).join('');
    document.body.appendChild(menuEl);

    const r = anchor.getBoundingClientRect();
    const mw = menuEl.offsetWidth;
    const mh = menuEl.offsetHeight;
    let left = alinear === 'izq' ? r.left : r.right - mw;
    let top = r.bottom + 6;
    if (top + mh > window.innerHeight - 8) top = Math.max(8, r.top - mh - 6);
    left = Math.min(Math.max(8, left), window.innerWidth - mw - 8);
    menuEl.style.top = top + 'px';
    menuEl.style.left = left + 'px';
    menuEl.style.visibility = '';

    menuAnchor = anchor;
    anchor.setAttribute('aria-expanded', 'true');

    const botones = Array.from(menuEl.querySelectorAll('button'));
    if (botones[0]) botones[0].focus();

    menuEl.addEventListener('click', (e) => {
      const b = e.target.closest('button[data-i]');
      if (!b) return;
      const it = items[Number(b.dataset.i)];
      cerrarMenu(true);
      if (it && it.accion) it.accion();
    });

    menuEl.addEventListener('keydown', (e) => {
      const i = botones.indexOf(document.activeElement);
      if (e.key === 'ArrowDown') { e.preventDefault(); botones[(i + 1) % botones.length].focus(); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); botones[(i - 1 + botones.length) % botones.length].focus(); }
      else if (e.key === 'Home') { e.preventDefault(); botones[0].focus(); }
      else if (e.key === 'End') { e.preventDefault(); botones[botones.length - 1].focus(); }
      else if (e.key === 'Escape') { e.preventDefault(); cerrarMenu(true); }
      else if (e.key === 'Tab') { cerrarMenu(); }
    });
  }

  document.addEventListener('click', (e) => {
    if (!menuEl) return;
    if (menuEl.contains(e.target) || e.target.closest('[aria-haspopup="menu"]')) return;
    cerrarMenu();
  });
  window.addEventListener('resize', () => cerrarMenu());
  window.addEventListener('scroll', (e) => { if (menuEl && !menuEl.contains(e.target)) cerrarMenu(); }, true);

  // ---------------------------------------------------------------
  // Tabla genérica: orden por columna + paginación
  // columnas: [{ clave, titulo, ordenable, clase, valor(fila), render(fila) }]
  // estado:   { clave, dir: 'asc'|'desc', pagina }  (se muta: se ajusta la página)
  // grupo(fila): número; los grupos menores van siempre primero (carpetas antes que archivos)
  // ---------------------------------------------------------------
  function paginador(estado, total, porPagina, paginas) {
    const ini = (estado.pagina - 1) * porPagina + 1;
    const fin = Math.min(total, estado.pagina * porPagina);
    const info = `<span class="dc-pager-info">Mostrando ${ini}–${fin} de ${total}</span>`;
    if (paginas <= 1) return `<div class="dc-pager">${info}</div>`;

    const set = new Set([1, paginas, estado.pagina - 1, estado.pagina, estado.pagina + 1]);
    const nums = Array.from(set).filter(n => n >= 1 && n <= paginas).sort((a, b) => a - b);
    let botones = '';
    let previo = 0;
    nums.forEach(n => {
      if (n - previo > 1) botones += '<span class="dc-pager-gap" aria-hidden="true">…</span>';
      botones += `<button type="button" class="dc-pager-btn${n === estado.pagina ? ' is-active' : ''}" data-pagina="${n}" aria-label="Página ${n}"${n === estado.pagina ? ' aria-current="page"' : ''}>${n}</button>`;
      previo = n;
    });
    return `
      <nav class="dc-pager" aria-label="Paginación">
        ${info}
        <div class="dc-pager-btns">
          <button type="button" class="dc-pager-btn" data-pagina="${estado.pagina - 1}" aria-label="Página anterior"${estado.pagina === 1 ? ' disabled' : ''}>‹</button>
          ${botones}
          <button type="button" class="dc-pager-btn" data-pagina="${estado.pagina + 1}" aria-label="Página siguiente"${estado.pagina === paginas ? ' disabled' : ''}>›</button>
        </div>
      </nav>`;
  }

  function tabla({ caption = '', columnas, filas, estado, porPagina = 10, grupo = null, vacio = 'No hay nada para mostrar.' }) {
    if (!filas.length) {
      return `<div class="empty-state" role="status">${iconos.carpeta}<p>${esc(vacio)}</p></div>`;
    }
    const col = columnas.find(c => c.clave === estado.clave && c.valor);
    const dir = estado.dir === 'desc' ? -1 : 1;

    const ordenadas = filas.slice().sort((a, b) => {
      if (grupo) {
        const g = grupo(a) - grupo(b);
        if (g) return g;
      }
      if (!col) return 0;
      const va = col.valor(a);
      const vb = col.valor(b);
      const r = (typeof va === 'number' && typeof vb === 'number')
        ? (va || 0) - (vb || 0)
        : String(va ?? '').localeCompare(String(vb ?? ''), 'es', { numeric: true, sensitivity: 'base' });
      return r * dir;
    });

    const paginas = Math.max(1, Math.ceil(ordenadas.length / porPagina));
    estado.pagina = Math.min(Math.max(1, estado.pagina || 1), paginas);
    const desde = (estado.pagina - 1) * porPagina;
    const visibles = ordenadas.slice(desde, desde + porPagina);

    const encabezados = columnas.map(c => {
      const activa = c.clave === estado.clave && c.valor;
      const aria = c.ordenable ? ` aria-sort="${activa ? (estado.dir === 'desc' ? 'descending' : 'ascending') : 'none'}"` : '';
      const contenido = c.ordenable
        ? `<button type="button" class="th-sort" data-sort="${c.clave}">${esc(c.titulo)}<span class="th-arrow" aria-hidden="true">${activa ? (estado.dir === 'desc' ? '↓' : '↑') : ''}</span></button>`
        : esc(c.titulo);
      return `<th scope="col" class="${c.clase || ''}"${aria}>${contenido}</th>`;
    }).join('');

    const cuerpo = visibles.map(f => `<tr data-id="${esc(f.id)}">${columnas.map(c => `<td class="${c.clase || ''}">${c.render(f)}</td>`).join('')}</tr>`).join('');

    return `
      <div class="dc-table-wrap">
        <table class="file-table">
          <caption class="visually-hidden">${esc(caption)}</caption>
          <thead><tr>${encabezados}</tr></thead>
          <tbody>${cuerpo}</tbody>
        </table>
      </div>
      ${paginador(estado, ordenadas.length, porPagina, paginas)}`;
  }

  /**
   * Conecta (una sola vez) el click en encabezados y paginador de un
   * contenedor. getEstado() devuelve el estado de la tabla vigente.
   */
  function enlazarTabla(contenedor, getEstado, redibujar) {
    contenedor.addEventListener('click', (e) => {
      const estado = getEstado();
      if (!estado) return;
      const s = e.target.closest('[data-sort]');
      if (s && contenedor.contains(s)) {
        const clave = s.dataset.sort;
        if (estado.clave === clave) estado.dir = estado.dir === 'asc' ? 'desc' : 'asc';
        else { estado.clave = clave; estado.dir = 'asc'; }
        estado.pagina = 1;
        redibujar();
        const nuevo = contenedor.querySelector(`[data-sort="${clave}"]`);
        if (nuevo) nuevo.focus();
        return;
      }
      const pg = e.target.closest('[data-pagina]');
      if (pg && contenedor.contains(pg) && !pg.disabled) {
        estado.pagina = Number(pg.dataset.pagina);
        redibujar();
        const activo = contenedor.querySelector('.dc-pager-btn.is-active');
        if (activo) activo.focus();
      }
    });
  }

  // ---------------------------------------------------------------
  // Estados de carga y de error (alertas visuales)
  // ---------------------------------------------------------------

  /** Pone/quita el estado "cargando" (spinner + deshabilitado) en un botón. */
  function cargando(boton, activo = true) {
    if (!boton) return;
    boton.classList.toggle('is-loading', activo);
    boton.disabled = activo;
    if (activo) boton.setAttribute('aria-busy', 'true'); else boton.removeAttribute('aria-busy');
  }

  /** HTML de una sección que falló, con botón "Reintentar" (data-reintentar). */
  function errorVista(mensaje = 'No pudimos mostrar esta sección.', { reintentar = true } = {}) {
    return `
      <div class="error-state" role="alert">
        ${iconos.info}
        <h2>Algo salió mal</h2>
        <p>${esc(mensaje)}</p>
        ${reintentar ? '<button type="button" class="dc-btn dc-btn-primary" data-reintentar>Reintentar</button>' : ''}
      </div>`;
  }

  // Barra fina de carga arriba de todo: se prende mientras haya pedidos en
  // curso (api.js y http.js avisan con el evento "cc:carga"). Espera 150 ms
  // para no parpadear con respuestas instantáneas.
  let pedidosEnCurso = 0;
  let temporizadorCarga = null;
  let barraCarga = null;

  function alCambiarCarga(e) {
    pedidosEnCurso = Math.max(0, pedidosEnCurso + ((e.detail && e.detail.delta) || 0));
    if (!barraCarga) {
      barraCarga = document.createElement('div');
      barraCarga.className = 'dc-topload';
      barraCarga.setAttribute('aria-hidden', 'true');
      document.body.appendChild(barraCarga);
    }
    if (pedidosEnCurso > 0) {
      if (!temporizadorCarga) temporizadorCarga = setTimeout(() => barraCarga.classList.add('is-on'), 150);
    } else {
      clearTimeout(temporizadorCarga);
      temporizadorCarga = null;
      barraCarga.classList.remove('is-on');
    }
  }

  // Aviso "sin conexión" fijo arriba mientras el navegador esté offline.
  let bannerOffline = null;

  function mostrarOffline(offline) {
    if (offline && !bannerOffline) {
      bannerOffline = document.createElement('div');
      bannerOffline.className = 'dc-offline';
      bannerOffline.setAttribute('role', 'status');
      bannerOffline.textContent = 'Sin conexión a internet. Los cambios pueden no guardarse hasta que vuelva.';
      document.body.appendChild(bannerOffline);
    } else if (!offline && bannerOffline) {
      bannerOffline.remove();
      bannerOffline = null;
      toast('Volviste a estar en línea.', { tipo: 'ok' });
    }
  }

  // Errores de JavaScript que nadie atrapó: en vez de quedar mudos, avisan.
  let ultimoAvisoError = 0;

  function errorInesperado(e) {
    const msg = String((e && (e.message || (e.reason && e.reason.message))) || '');
    // Estos no son fallas: las páginas cortan su script a propósito al redirigir sin sesión.
    if (msg.includes('redirigiendo') || msg.includes('ResizeObserver')) return;
    const t = Date.now();
    if (t - ultimoAvisoError < 3000) return; // evita una lluvia de avisos
    ultimoAvisoError = t;
    toast('Ocurrió un error inesperado. Si sigue pasando, recargá la página.', { tipo: 'error' });
  }

  let globalesInstalados = false;
  function instalarGlobales() {
    if (globalesInstalados) return;
    globalesInstalados = true;
    document.addEventListener('cc:carga', alCambiarCarga);
    window.addEventListener('offline', () => mostrarOffline(true));
    window.addEventListener('online', () => mostrarOffline(false));
    window.addEventListener('error', errorInesperado);
    window.addEventListener('unhandledrejection', errorInesperado);
    if (navigator.onLine === false) mostrarOffline(true);
  }
  // Listeners de carga desde ya; el banner inicial necesita <body>.
  if (document.body) instalarGlobales();
  else document.addEventListener('DOMContentLoaded', instalarGlobales);

  return {
    esc, uid, normalizar, iconos, TIPOS, tipoDeArchivo, iconoArchivo, iconoNodo,
    formatoTamanio, formatoFecha, iniciales, colorAvatar, badge, badgeRol,
    topbarHtml, atajoBuscar, enlazarSidebar,
    toast, dialogo, confirmar, aviso, formulario,
    cargando, errorVista,
    menuContextual, cerrarMenu,
    tabla, enlazarTabla,
  };
})();