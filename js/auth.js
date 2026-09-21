const Auth = (() => {
  'use strict';

  const KEY_USUARIOS = 'campuscloud_usuarios';
  const KEY_POLITICAS = 'campuscloud_politicas';
  const KEY_SESION = 'campuscloud_sesion';
  const KEY_TOKEN = 'campuscloud_token';
  const DURACION_TOKEN_SEG = 60 * 60 * 8; // 8 horas

  const ROLES = { alumno: 'Alumno', docente: 'Docente', admin: 'Administrador' };
  const ROLES_SOLICITABLES = ['alumno', 'docente']; // el admin nunca se pide desde el registro
  const ESTADOS = { pendiente: 'Pendiente', aprobado: 'Aprobado', rechazado: 'Rechazado' };
  const MODOS_EXT = ['todas', 'permitidas', 'bloqueadas'];

  // Qué roles pueden hacer cada cosa (lo consultan Drive y Api).
  const CAPACIDADES = {
    compartir: ['docente', 'admin'],
  };

  // Capacidad total del servidor (VPS) que se muestra en el panel de admin.
  const CAPACIDAD_SERVIDOR_MB = 100 * 1024;

  const MOTIVOS_RECHAZO = [
    { valor: 'datos', texto: 'Los datos ingresados no son válidos o no se pudieron verificar.' },
    { valor: 'dni', texto: 'El DNI no coincide con el nombre indicado.' },
    { valor: 'duplicada', texto: 'Ya existe otra cuenta a nombre de la misma persona.' },
    { valor: 'sin_acceso', texto: 'No tenés autorización para usar este servicio.' },
    { valor: 'otro', texto: 'Otro motivo (detallalo abajo)' },
  ];

  const POLITICAS_POR_DEFECTO = {
    global: {
      cuotaMB: 250,
      maxArchivoMB: 25,
      extensiones: { modo: 'bloqueadas', lista: ['exe', 'bat', 'cmd', 'com', 'msi', 'scr'] },
    },
    roles: {
      alumno: {},
      docente: { cuotaMB: 2 * 1024 },
      admin: { cuotaMB: 10 * 1024, maxArchivoMB: 100 },
    },
  };

  const haceDias = (d) => new Date(Date.now() - d * 86400000).toISOString();
  const USUARIOS_SEMILLA = [
    { nombre: 'Marina Gómez', email: 'admin@campus.edu.ar', dni: '27314559', password: 'admin123', rol: 'admin', estado: 'aprobado', creado: haceDias(90) },
    { nombre: 'Lic. Laura Méndez', email: 'docente@campus.edu.ar', dni: '29731442', password: 'docente123', rol: 'docente', rolSolicitado: 'docente', estado: 'aprobado', creado: haceDias(60) },
    { nombre: 'Juan Fernández', email: 'alumno@campus.edu.ar', dni: '40218931', password: 'alumno123', rol: 'alumno', rolSolicitado: 'alumno', estado: 'aprobado', creado: haceDias(40) },
    { nombre: 'Ana Sofía Ruiz', email: 'aruiz@campus.edu.ar', dni: '41829304', password: 'alumno123', rol: 'alumno', rolSolicitado: 'alumno', estado: 'pendiente', creado: haceDias(1) },
    { nombre: 'Martín Rojas', email: 'mrojas@campus.edu.ar', dni: '32114608', password: 'docente123', rol: 'alumno', rolSolicitado: 'docente', estado: 'pendiente', creado: haceDias(2) },
    { nombre: 'Camila Vera', email: 'cvera@campus.edu.ar', dni: '40782195', password: 'alumno123', rol: 'alumno', rolSolicitado: 'alumno', estado: 'pendiente', creado: haceDias(3) },
  ];

  const CUENTAS_DEMO = {};
  USUARIOS_SEMILLA.filter(u => u.estado === 'aprobado').forEach(u => {
    CUENTAS_DEMO[u.rol] = { email: u.email, password: u.password };
  });

  const clonar = (o) => JSON.parse(JSON.stringify(o));

  function generarId(prefijo = 'id') {
    return `${prefijo}_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
  }

  function irA(pagina) {
    window.location.href = new URL(pagina, window.location.href).href;
  }

  function puede(usuario, capacidad) {
    return !!usuario && (CAPACIDADES[capacidad] || []).includes(usuario.rol);
  }

  // ---------------------------------------------------------------
  // Validaciones
  // ---------------------------------------------------------------

  function validarEmail(valor) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(valor);
  }

  function limpiarDNI(valor) {
    return String(valor || '').replace(/[.\s-]/g, '');
  }

  function validarDNI(valor) {
    return /^\d{7,8}$/.test(limpiarDNI(valor));
  }

  /** Vale si es un correo válido o un DNI de 7 u 8 números (con o sin puntos). */
  function validarIdentificador(valor) {
    const v = String(valor || '').trim();
    return v.includes('@') ? validarEmail(v) : validarDNI(v);
  }

  function formatearDNI(valor) {
    const s = String(valor || '').replace(/\D/g, '');
    return s ? s.replace(/\B(?=(\d{3})+(?!\d))/g, '.') : '';
  }

  // ---------------------------------------------------------------
  // Usuarios
  // ---------------------------------------------------------------

  function normalizarUsuario(u) {
    u = u || {};
    const rol = ROLES[u.rol] ? u.rol : 'alumno';
    return {
      id: u.id || generarId('u'),
      nombre: String(u.nombre || '').trim(),
      email: String(u.email || '').trim().toLowerCase(),
      dni: limpiarDNI(u.dni).replace(/\D/g, ''),
      password: String(u.password || ''),
      rol,
      rolSolicitado: ROLES_SOLICITABLES.includes(u.rolSolicitado) ? u.rolSolicitado : (rol === 'docente' ? 'docente' : 'alumno'),
      estado: ESTADOS[u.estado] ? u.estado : 'pendiente',
      motivoRechazo: String(u.motivoRechazo || ''),
      excepciones: u.excepciones && typeof u.excepciones === 'object' ? sanitizarPolitica(u.excepciones) : {},
      creado: u.creado || new Date().toISOString(),
    };
  }

  function leerUsuarios() {
    const crudo = localStorage.getItem(KEY_USUARIOS);
    let lista = null;
    if (crudo) {
      try { lista = JSON.parse(crudo); } catch { lista = null; }
    }
    if (!Array.isArray(lista) || lista.length === 0) lista = clonar(USUARIOS_SEMILLA);
    const normales = lista.map(normalizarUsuario);

    if (!normales.some(u => u.rol === 'admin')) {
      const base = USUARIOS_SEMILLA.find(u => u.rol === 'admin');
      const existente = normales.find(u => u.email === base.email);
      if (existente) {
        existente.rol = 'admin';
        existente.estado = 'aprobado';
        existente.motivoRechazo = '';
      } else {
        normales.push(normalizarUsuario(base));
      }
    }

    const nuevoCrudo = JSON.stringify(normales);
    if (nuevoCrudo !== crudo) localStorage.setItem(KEY_USUARIOS, nuevoCrudo);
    return normales;
  }

  function guardarUsuarios(lista) {
    localStorage.setItem(KEY_USUARIOS, JSON.stringify(lista));
  }

  const publico = ({ password, ...resto }) => resto;

  function listarUsuarios() {
    return leerUsuarios().map(publico);
  }

  function obtenerUsuario(id) {
    const u = leerUsuarios().find(x => x.id === id);
    return u ? publico(u) : null;
  }

  function usuarioPorEmail(email) {
    const e = String(email || '').trim().toLowerCase();
    const u = leerUsuarios().find(x => x.email === e);
    return u ? publico(u) : null;
  }

  /** Busca una cuenta por correo o por DNI (lo que escriba la persona en el modal de compartir). */
  function usuarioPorIdentificador(valor) {
    const v = String(valor || '').trim();
    if (!validarIdentificador(v)) return null;
    if (v.includes('@')) return usuarioPorEmail(v);
    const dni = limpiarDNI(v);
    const u = leerUsuarios().find(x => x.dni === dni);
    return u ? publico(u) : null;
  }

  function obtenerPendientes() {
    return listarUsuarios().filter(u => u.estado === 'pendiente');
  }

  function registrarUsuario({ nombre, email, dni, password, rolSolicitado }) {
    nombre = String(nombre || '').trim().replace(/\s+/g, ' ');
    email = String(email || '').trim().toLowerCase();
    const dniLimpio = limpiarDNI(dni);

    if (nombre.length < 2) return { ok: false, campo: 'nombre', motivo: 'Ingresá tu nombre completo.' };
    if (!validarEmail(email)) return { ok: false, campo: 'email', motivo: 'Ingresá un correo válido.' };
    if (!validarDNI(dniLimpio)) return { ok: false, campo: 'dni', motivo: 'Ingresá un DNI válido (7 u 8 números).' };
    if (String(password || '').length < 6) return { ok: false, campo: 'password', motivo: 'La contraseña debe tener al menos 6 caracteres.' };
    if (!ROLES_SOLICITABLES.includes(rolSolicitado)) return { ok: false, campo: 'rol', motivo: 'Elegí si sos alumno o docente.' };

    const usuarios = leerUsuarios();
    if (usuarios.some(u => u.email === email)) {
      return { ok: false, campo: 'email', motivo: 'Ya existe una cuenta con ese correo.' };
    }
    if (usuarios.some(u => u.dni && u.dni === dniLimpio)) {
      return { ok: false, campo: 'dni', motivo: 'Ya existe una cuenta con ese DNI.' };
    }

    const nuevo = normalizarUsuario({ nombre, email, dni: dniLimpio, password, rol: 'alumno', rolSolicitado, estado: 'pendiente' });
    usuarios.push(nuevo);
    guardarUsuarios(usuarios);
    return { ok: true, usuario: publico(nuevo) };
  }

  function iniciarSesion(email, password, recordar = false) {
    const e = String(email || '').trim().toLowerCase();
    const usuario = leerUsuarios().find(u => u.email === e);

    if (!usuario || usuario.password !== password) return { ok: false, motivo: 'credenciales' };
    if (usuario.estado === 'pendiente') return { ok: false, motivo: 'pendiente' };
    if (usuario.estado === 'rechazado') return { ok: false, motivo: 'rechazado', detalle: usuario.motivoRechazo };

    guardarSesion(usuario, recordar);
    return { ok: true, usuario: publico(usuario) };
  }

  function modificarUsuario(id, fn) {
    const lista = leerUsuarios();
    const u = lista.find(x => x.id === id);
    if (!u) return { ok: false, motivo: 'No se encontró la cuenta.' };
    const r = fn(u);
    if (r && r.ok === false) return r;
    guardarUsuarios(lista);
    return { ok: true, usuario: publico(u) };
  }

  function cambiarEstadoUsuario(id, nuevoEstado, { motivo = '', rol = null } = {}) {
    return modificarUsuario(id, (u) => {
      if (u.rol === 'admin') return { ok: false, motivo: 'No se puede cambiar el estado de un administrador.' };
      if (!ESTADOS[nuevoEstado]) return { ok: false, motivo: 'Estado inválido.' };
      u.estado = nuevoEstado;
      u.motivoRechazo = nuevoEstado === 'rechazado' ? String(motivo || '').trim() : '';
      if (nuevoEstado === 'aprobado' && rol) {
        if (!ROLES_SOLICITABLES.includes(rol)) return { ok: false, motivo: 'Rol inválido.' };
        u.rol = rol;
      }
    });
  }

  function cambiarRol(id, rol) {
    return modificarUsuario(id, (u) => {
      if (u.rol === 'admin') return { ok: false, motivo: 'No se puede cambiar el rol de un administrador.' };
      if (!ROLES_SOLICITABLES.includes(rol)) return { ok: false, motivo: 'Rol inválido.' };
      u.rol = rol;
    });
  }

  function guardarExcepciones(id, excepciones) {
    return modificarUsuario(id, (u) => {
      u.excepciones = sanitizarPolitica(excepciones);
    });
  }

  // ---------------------------------------------------------------
  // Políticas de almacenamiento
  // ---------------------------------------------------------------

  function parsearExtensiones(texto) {
    const partes = String(texto || '').split(/[\s,;]+/).map(p => p.replace(/^\./, '').toLowerCase()).filter(Boolean);
    const lista = [];
    const invalidas = [];
    partes.forEach(p => {
      if (!/^[a-z0-9]+$/.test(p)) invalidas.push(p);
      else if (!lista.includes(p)) lista.push(p);
    });
    return { lista, invalidas };
  }

  function sanitizarPolitica(p) {
    const limpia = {};
    if (!p || typeof p !== 'object') return limpia;
    if (typeof p.cuotaMB === 'number' && p.cuotaMB > 0) limpia.cuotaMB = p.cuotaMB;
    if (typeof p.maxArchivoMB === 'number' && p.maxArchivoMB > 0) limpia.maxArchivoMB = p.maxArchivoMB;
    if (p.extensiones && MODOS_EXT.includes(p.extensiones.modo)) {
      limpia.extensiones = {
        modo: p.extensiones.modo,
        lista: p.extensiones.modo === 'todas' ? [] : parsearExtensiones((p.extensiones.lista || []).join(',')).lista,
      };
    }
    return limpia;
  }

  function obtenerPoliticas() {
    let guardadas = null;
    try { guardadas = JSON.parse(localStorage.getItem(KEY_POLITICAS)); } catch { guardadas = null; }
    const base = clonar(POLITICAS_POR_DEFECTO);
    if (guardadas && typeof guardadas === 'object') {
      if (guardadas.global) base.global = { ...base.global, ...sanitizarPolitica(guardadas.global) };
      if (guardadas.roles) {
        Object.keys(ROLES).forEach(k => {
          if (guardadas.roles[k]) base.roles[k] = sanitizarPolitica(guardadas.roles[k]);
        });
      }
    }
    return base;
  }

  function escribirPoliticas(p) {
    localStorage.setItem(KEY_POLITICAS, JSON.stringify(p));
  }

  function guardarPoliticaGlobal(politica) {
    const p = obtenerPoliticas();
    p.global = { ...p.global, ...sanitizarPolitica(politica) };
    escribirPoliticas(p);
    return { ok: true };
  }

  function guardarPoliticaRol(rol, politica) {
    if (!ROLES[rol]) return { ok: false, motivo: 'Rol inválido.' };
    const p = obtenerPoliticas();
    p.roles[rol] = sanitizarPolitica(politica);
    escribirPoliticas(p);
    return { ok: true };
  }

  function restaurarPoliticas() {
    localStorage.removeItem(KEY_POLITICAS);
  }

   
  function politicaEfectiva(usuario) {
    const pol = obtenerPoliticas();
    const capas = [
      ['global', pol.global],
      ['rol', pol.roles[usuario && usuario.rol] || {}],
      ['usuario', (usuario && usuario.excepciones) || {}],
    ];
    const ef = { origen: {} };
    ['cuotaMB', 'maxArchivoMB', 'extensiones'].forEach(campo => {
      capas.forEach(([nombre, capa]) => {
        if (capa && capa[campo] != null) {
          ef[campo] = clonar(capa[campo]);
          ef.origen[campo] = nombre;
        }
      });
    });
    return ef;
  }

  function extensionDe(nombre) {
    const s = String(nombre || '');
    const i = s.lastIndexOf('.');
    if (i <= 0 || i === s.length - 1) return '';
    return s.slice(i + 1).toLowerCase();
  }

  function verificarExtension(nombre, ext) {
    if (!ext || ext.modo === 'todas') return null;
    const e = extensionDe(nombre);
    if (ext.modo === 'permitidas') {
      if (!e) return 'Esta cuenta solo admite archivos con extensión.';
      if (!ext.lista.includes(e)) return `Los archivos .${e} no están permitidos (solo ${ext.lista.map(x => '.' + x).join(', ')}).`;
    }
    if (ext.modo === 'bloqueadas' && e && ext.lista.includes(e)) {
      return `Los archivos .${e} están bloqueados por la política de esta cuenta.`;
    }
    return null;
  }

  function describirExtensiones(ext) {
    if (!ext || ext.modo === 'todas') return 'Se permiten todas';
    const txt = ext.lista.map(x => '.' + x).join(', ') || '—';
    return ext.modo === 'permitidas' ? `Solo ${txt}` : `Bloqueadas: ${txt}`;
  }

  // ---------------------------------------------------------------
  // Token simulado con forma de JWT (header.payload.firma en base64url)
  // ---------------------------------------------------------------

  function b64uCodificar(obj) {
    const bytes = new TextEncoder().encode(JSON.stringify(obj));
    let bin = '';
    bytes.forEach(b => { bin += String.fromCharCode(b); });
    return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }

  function b64uDecodificar(str) {
    let s = str.replace(/-/g, '+').replace(/_/g, '/');
    while (s.length % 4) s += '=';
    const bin = atob(s);
    return new TextDecoder().decode(Uint8Array.from(bin, c => c.charCodeAt(0)));
  }

  function generarTokenSimulado(usuario) {
    const ahora = Math.floor(Date.now() / 1000);
    const header = { alg: 'none', typ: 'JWT' };
    const payload = { sub: usuario.id, nombre: usuario.nombre, rol: usuario.rol, iat: ahora, exp: ahora + DURACION_TOKEN_SEG };
    return `${b64uCodificar(header)}.${b64uCodificar(payload)}.simulado`;
  }

  function decodificarToken(token) {
    if (!token) return null;
    const partes = token.split('.');
    if (partes.length !== 3) return null;
    try { return JSON.parse(b64uDecodificar(partes[1])); } catch { return null; }
  }

  function tokenValido(token) {
    const payload = decodificarToken(token);
    return !!(payload && payload.exp && payload.exp > Math.floor(Date.now() / 1000));
  }

  // ---------------------------------------------------------------
  // Sesión. Con "Recordarme" vive en localStorage; sin eso, en
  // sessionStorage (se pierde al cerrar la pestaña).
  // ---------------------------------------------------------------

  function leerClave(clave) {
    const s = sessionStorage.getItem(clave);
    return s !== null ? s : localStorage.getItem(clave);
  }

  function obtenerToken() {
    return leerClave(KEY_TOKEN);
  }

  function headerAutorizacion() {
    const token = obtenerToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  function guardarSesion(usuario, recordar = false) {
    cerrarSesion();
    const almacen = recordar ? localStorage : sessionStorage;
    const { id, nombre, email, rol } = usuario;
    almacen.setItem(KEY_SESION, JSON.stringify({ id, nombre, email, rol }));
    almacen.setItem(KEY_TOKEN, generarTokenSimulado(usuario));
  }

  function obtenerSesion() {
    const crudo = leerClave(KEY_SESION);
    if (!crudo) return null;
    try { return JSON.parse(crudo); } catch { return null; }
  }

  function cerrarSesion() {
    [localStorage, sessionStorage].forEach(a => {
      a.removeItem(KEY_SESION);
      a.removeItem(KEY_TOKEN);
    });
  }

  function validarSesion(rolRequerido) {
    const ses = obtenerSesion();
    const token = obtenerToken();
    if (!ses || !token) return { ok: false, motivo: 'sinsesion' };
    if (!tokenValido(token)) return { ok: false, motivo: 'expirada' };
    const payload = decodificarToken(token);
    if (!payload || payload.sub !== ses.id) return { ok: false, motivo: 'invalida' };
    const usuario = obtenerUsuario(ses.id);
    if (!usuario) return { ok: false, motivo: 'invalida' };
    if (usuario.estado !== 'aprobado') return { ok: false, motivo: usuario.estado };
    // rolRequerido puede ser un rol ('admin') o una lista (['docente', 'admin']).
    if (rolRequerido) {
      const permitidos = Array.isArray(rolRequerido) ? rolRequerido : [rolRequerido];
      if (!permitidos.includes(usuario.rol)) return { ok: false, motivo: 'rol', usuario };
    }
    return { ok: true, usuario };
  }

  function requerirSesion(rolRequerido) {
    const r = validarSesion(rolRequerido);
    if (r.ok) return r.usuario;
    if (r.motivo === 'rol') {
      irA('index.html');
      return null;
    }
    cerrarSesion();
    irA(r.motivo === 'sinsesion' ? 'login.html' : `login.html?e=${encodeURIComponent(r.motivo)}`);
    return null;
  }

  function sesionActiva(rolRequerido) {
    const r = validarSesion(rolRequerido);
    return r.ok ? r.usuario : null;
  }

  // ---------------------------------------------------------------
  // Helpers de formulario
  // ---------------------------------------------------------------

  function marcarCampo(fieldEl, inputEl, esValido, mensaje) {
    fieldEl.classList.toggle('has-error', !esValido);
    inputEl.setAttribute('aria-invalid', esValido ? 'false' : 'true');
    const err = fieldEl.querySelector('.field-error');
    if (err) {
      if (!err.dataset.default) err.dataset.default = err.textContent;
      err.textContent = !esValido && mensaje ? mensaje : err.dataset.default;
    }
  }

  function attachPasswordToggle(toggleBtn, inputEl) {
    toggleBtn.addEventListener('click', () => {
      const vaAMostrar = inputEl.type === 'password';
      inputEl.type = vaAMostrar ? 'text' : 'password';
      toggleBtn.setAttribute('aria-pressed', String(vaAMostrar));
      toggleBtn.setAttribute('aria-label', vaAMostrar ? 'Ocultar contraseña' : 'Mostrar contraseña');
    });
  }

  function mostrarAlerta(alertBox, alertText, mensaje) {
    alertText.textContent = mensaje;
    alertBox.style.display = 'flex';
  }

  function ocultarAlerta(alertBox) {
    alertBox.style.display = 'none';
  }

  return {
    ROLES, ROLES_SOLICITABLES, ESTADOS, MOTIVOS_RECHAZO, CAPACIDADES, CAPACIDAD_SERVIDOR_MB, CUENTAS_DEMO,
    generarId, irA, puede,
    validarEmail, validarDNI, validarIdentificador, limpiarDNI, formatearDNI,
    registrarUsuario, iniciarSesion, cerrarSesion, obtenerSesion, requerirSesion, sesionActiva,
    listarUsuarios, obtenerUsuario, usuarioPorEmail, usuarioPorIdentificador, obtenerPendientes,
    cambiarEstadoUsuario, cambiarRol, guardarExcepciones,
    obtenerPoliticas, guardarPoliticaGlobal, guardarPoliticaRol, restaurarPoliticas, politicaEfectiva,
    parsearExtensiones, extensionDe, verificarExtension, describirExtensiones,
    obtenerToken, decodificarToken, tokenValido, headerAutorizacion,
    marcarCampo, attachPasswordToggle, mostrarAlerta, ocultarAlerta,
  };
})();