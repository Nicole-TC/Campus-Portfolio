const Drive = (() => {
  'use strict';

  const KEY = 'campuscloud_drive_v1';
  const ACCIONES = {
    propietario: ['ver', 'descargar', 'renombrar', 'mover', 'compartir', 'eliminar', 'subir', 'crear'],
    editor: ['ver', 'descargar', 'renombrar', 'subir', 'crear'],
    lector: ['ver', 'descargar'],
  };
  const CARACTERES_INVALIDOS = /[\\/:*?"<>|]/;

  let cache = null;
  window.addEventListener('storage', (e) => { if (e.key === KEY) cache = null; });

  const ok = (extra = {}) => ({ ok: true, ...extra });
  const err = (motivo) => ({ ok: false, motivo });
  const ahora = () => new Date().toISOString();

  function db() {
    if (cache) return cache;
    let datos = null;
    try { datos = JSON.parse(localStorage.getItem(KEY)); } catch { datos = null; }
    if (!datos || typeof datos !== 'object') datos = {};
    cache = {
      version: 1,
      nodos: Array.isArray(datos.nodos) ? datos.nodos : [],
      shares: Array.isArray(datos.shares) ? datos.shares : [],
      inicializados: Array.isArray(datos.inicializados) ? datos.inicializados : [],
    };
    return cache;
  }

  function persistir() {
    localStorage.setItem(KEY, JSON.stringify(db()));
  }

  const nodo = (id) => db().nodos.find(n => n.id === id) || null;

  // ---------------------------------------------------------------
  // Árbol
  // ---------------------------------------------------------------

  function descendientes(id) {
    const porPadre = new Map();
    db().nodos.forEach(n => {
      if (!n.padreId) return;
      if (!porPadre.has(n.padreId)) porPadre.set(n.padreId, []);
      porPadre.get(n.padreId).push(n);
    });
    const res = [];
    const cola = [id];
    while (cola.length) {
      const actual = cola.shift();
      (porPadre.get(actual) || []).forEach(h => {
        res.push(h);
        if (h.tipo === 'carpeta') cola.push(h.id);
      });
    }
    return res;
  }

  function ruta(id) {
    const r = [];
    let n = nodo(id);
    let guardia = 0;
    while (n && guardia++ < 100) {
      r.unshift(n);
      n = n.padreId ? nodo(n.padreId) : null;
    }
    return r;
  }

  function rutaTexto(padreId) {
    return padreId ? ruta(padreId).map(n => n.nombre).join(' / ') : 'Mis archivos';
  }

  function hijosDe(padreId) {
    return db().nodos.filter(n => n.padreId === padreId && !n.eliminado);
  }

  function tamanioCarpetaMB(id) {
    return descendientes(id).reduce((a, d) => a + (d.tipo === 'archivo' && !d.eliminado ? d.tamanioMB : 0), 0);
  }

  function usoMB(userId) {
    return db().nodos.reduce((a, n) => a + (n.propietarioId === userId && n.tipo === 'archivo' ? n.tamanioMB : 0), 0);
  }

  function usoPapeleraMB(userId) {
    return db().nodos.reduce((a, n) => a + (n.propietarioId === userId && n.tipo === 'archivo' && n.eliminado ? n.tamanioMB : 0), 0);
  }

  // ---------------------------------------------------------------
  // Permisos
  // ---------------------------------------------------------------

  function esRaizCompartida(userId, n) {
    return db().shares.some(s => s.itemId === n.id && s.conId === userId);
  }

  function permisoSobre(userId, n) {
    if (!n) return null;
    if (n.propietarioId === userId) return 'propietario';
    if (n.eliminado) return null;
    const mias = db().shares.filter(s => s.conId === userId);
    if (!mias.length) return null;
    let mejor = null;
    for (const a of ruta(n.id)) {
      const s = mias.find(x => x.itemId === a.id);
      if (s) {
        if (s.permiso === 'editor') return 'editor';
        mejor = 'lector';
      }
    }
    return mejor;
  }

  function acciones(userId, n) {
    const p = permisoSobre(userId, n);
    if (!p || !n) return [];
    let a = ACCIONES[p].slice();
    if (n.tipo === 'archivo') a = a.filter(x => x !== 'subir' && x !== 'crear');
    else a = a.filter(x => x !== 'descargar');
    if (p === 'editor' && esRaizCompartida(userId, n)) a = a.filter(x => x !== 'renombrar');
    // Compartir depende también del ROL de la cuenta (los alumnos no comparten).
    if (a.includes('compartir') && !Auth.puede(Auth.obtenerUsuario(userId), 'compartir')) {
      a = a.filter(x => x !== 'compartir');
    }
    return a;
  }

  const puede = (userId, n, accion) => acciones(userId, n).includes(accion);

  // ---------------------------------------------------------------
  // Nombres
  // ---------------------------------------------------------------

  function validarNombre(nombre) {
    const n = String(nombre || '').trim();
    if (!n) return 'El nombre no puede estar vacío.';
    if (n.length > 120) return 'El nombre no puede tener más de 120 caracteres.';
    if (n === '.' || n === '..') return 'Ese nombre no es válido.';
    if (CARACTERES_INVALIDOS.test(n)) return 'El nombre no puede contener \\ / : * ? " < > |';
    return null;
  }

  function nombreEnUso(propietarioId, padreId, nombre, excluirId) {
    const k = String(nombre).trim().toLowerCase();
    return db().nodos.some(n => n.propietarioId === propietarioId && (n.padreId || null) === (padreId || null)
      && !n.eliminado && n.id !== excluirId && n.nombre.toLowerCase() === k);
  }

  function nombreLibre(propietarioId, padreId, nombre, esArchivo) {
    if (!nombreEnUso(propietarioId, padreId, nombre)) return nombre;
    const punto = esArchivo ? nombre.lastIndexOf('.') : -1;
    const base = punto > 0 ? nombre.slice(0, punto) : nombre;
    const ext = punto > 0 ? nombre.slice(punto) : '';
    let i = 1;
    let candidato;
    do { candidato = `${base} (${i++})${ext}`; } while (nombreEnUso(propietarioId, padreId, candidato));
    return candidato;
  }

  function nuevoNodo(props) {
    const t = ahora();
    return {
      id: Auth.generarId('n'),
      tipo: 'archivo',
      nombre: '',
      padreId: null,
      propietarioId: '',
      creadoPorId: '',
      tamanioMB: 0,
      ext: '',
      creado: t,
      modificado: t,
      eliminado: false,
      eliminadoEn: null,
      eliminadoRaiz: null,
      ...props,
    };
  }

  // ---------------------------------------------------------------
  // Listados
  // ---------------------------------------------------------------

  function listarHijos(userId, padreId) {
    if (!padreId) return db().nodos.filter(n => n.propietarioId === userId && !n.padreId && !n.eliminado);
    const p = nodo(padreId);
    if (!p || p.eliminado || !puede(userId, p, 'ver')) return [];
    return hijosDe(padreId);
  }

  function propios(userId, tipo) {
    return db().nodos.filter(n => n.propietarioId === userId && !n.eliminado && (!tipo || n.tipo === tipo));
  }

  function recientes(userId, tipo, cantidad) {
    return propios(userId, tipo)
      .sort((a, b) => Date.parse(b.modificado) - Date.parse(a.modificado))
      .slice(0, cantidad);
  }

  function buscarPropios(userId, texto) {
    const q = UI.normalizar(texto);
    return propios(userId).filter(n => UI.normalizar(n.nombre).includes(q));
  }

  function carpetasDestino(userId, excluirId) {
    const excluidos = new Set(excluirId ? [excluirId, ...descendientes(excluirId).map(d => d.id)] : []);
    return propios(userId, 'carpeta')
      .filter(n => !excluidos.has(n.id))
      .map(n => ({ id: n.id, etiqueta: ruta(n.id).map(x => x.nombre).join(' / ') }))
      .sort((a, b) => a.etiqueta.localeCompare(b.etiqueta, 'es'));
  }

  // ---------------------------------------------------------------
  // Crear / subir / renombrar / mover
  // ---------------------------------------------------------------

  function resolverEspacio(actorId, padreId) {
    if (!padreId) return ok({ propietarioId: actorId, padre: null });
    const padre = nodo(padreId);
    if (!padre || padre.tipo !== 'carpeta' || padre.eliminado) return err('La carpeta de destino ya no existe.');
    if (!puede(actorId, padre, 'crear')) return err('No tenés permiso para agregar contenido en esta carpeta.');
    return ok({ propietarioId: padre.propietarioId, padre });
  }

  function crearCarpeta(actorId, padreId, nombre) {
    const esp = resolverEspacio(actorId, padreId);
    if (!esp.ok) return esp;
    nombre = String(nombre || '').trim();
    const m = validarNombre(nombre);
    if (m) return err(m);
    if (nombreEnUso(esp.propietarioId, padreId || null, nombre)) {
      return err(`Ya existe un elemento llamado "${nombre}" en esta ubicación.`);
    }
    const n = nuevoNodo({ tipo: 'carpeta', nombre, padreId: padreId || null, propietarioId: esp.propietarioId, creadoPorId: actorId });
    db().nodos.push(n);
    persistir();
    return ok({ nodo: n });
  }

  

  function evaluarSubida(actorId, padreId, archivo) {
    const esp = resolverEspacio(actorId, padreId);
    if (!esp.ok) return esp;

    const dueno = Auth.obtenerUsuario(esp.propietarioId);
    if (!dueno) return err('No se encontró el espacio de destino.');
    const pol = Auth.politicaEfectiva(dueno);

    const nombre = String(archivo.name || '').replace(CARACTERES_INVALIDOS, '_').trim() || 'archivo';
    const m = validarNombre(nombre);
    if (m) return err(m);

    const motivoExt = Auth.verificarExtension(nombre, pol.extensiones);
    if (motivoExt) return err(motivoExt);

    const sizeMB = (archivo.size || 0) / (1024 * 1024);
    if (sizeMB > pol.maxArchivoMB) {
      return err(`Pesa ${UI.formatoTamanio(sizeMB)} y el máximo por archivo es ${UI.formatoTamanio(pol.maxArchivoMB)}.`);
    }

    const usado = usoMB(dueno.id);
    if (usado + sizeMB > pol.cuotaMB) {
      const quien = dueno.id === actorId ? 'Tu espacio' : `El espacio de ${dueno.nombre}`;
      return err(`${quien} no tiene lugar suficiente (${UI.formatoTamanio(Math.max(0, pol.cuotaMB - usado), { cero: '0 MB' })} libres de ${UI.formatoTamanio(pol.cuotaMB)}).`);
    }

    return ok({ dueno, nombre, sizeMB });
  }

  function validarSubida(actorId, padreId, archivo) {
    const r = evaluarSubida(actorId, padreId, archivo);
    return r.ok ? null : r.motivo;
  }

  function subirArchivo(actorId, padreId, archivo) {
    const ev = evaluarSubida(actorId, padreId, archivo);
    if (!ev.ok) return ev;

    const final = nombreLibre(ev.dueno.id, padreId || null, ev.nombre, true);
    const n = nuevoNodo({
      tipo: 'archivo', nombre: final, padreId: padreId || null, propietarioId: ev.dueno.id, creadoPorId: actorId,
      tamanioMB: ev.sizeMB, ext: Auth.extensionDe(final),
    });
    db().nodos.push(n);
    if (padreId) { const p = nodo(padreId); if (p) p.modificado = n.modificado; }
    persistir();
    return ok({ nodo: n, renombrado: final !== ev.nombre });
  }

  function renombrar(actorId, id, nuevoNombre) {
    const n = nodo(id);
    if (!n || n.eliminado) return err('El elemento ya no existe.');
    if (!puede(actorId, n, 'renombrar')) return err('No tenés permiso para renombrar este elemento.');
    nuevoNombre = String(nuevoNombre || '').trim();
    const m = validarNombre(nuevoNombre);
    if (m) return err(m);
    if (nuevoNombre === n.nombre) return ok();
    if (nombreEnUso(n.propietarioId, n.padreId || null, nuevoNombre, n.id)) {
      return err(`Ya existe un elemento llamado "${nuevoNombre}" en esta ubicación.`);
    }
    if (n.tipo === 'archivo') {
      const dueno = Auth.obtenerUsuario(n.propietarioId);
      const motivo = dueno ? Auth.verificarExtension(nuevoNombre, Auth.politicaEfectiva(dueno).extensiones) : null;
      if (motivo) return err(motivo);
      n.ext = Auth.extensionDe(nuevoNombre);
    }
    n.nombre = nuevoNombre;
    n.modificado = ahora();
    persistir();
    return ok();
  }

  function mover(actorId, id, destinoId) {
    const n = nodo(id);
    if (!n || n.eliminado) return err('El elemento ya no existe.');
    if (!puede(actorId, n, 'mover')) return err('No tenés permiso para mover este elemento.');
    destinoId = destinoId || null;
    if (destinoId) {
      const d = nodo(destinoId);
      if (!d || d.tipo !== 'carpeta' || d.eliminado || d.propietarioId !== actorId) return err('La carpeta de destino no es válida.');
      if (destinoId === id || descendientes(id).some(x => x.id === destinoId)) return err('No podés mover una carpeta adentro de sí misma.');
    }
    if ((n.padreId || null) === destinoId) return err('El elemento ya está en esa ubicación.');
    if (nombreEnUso(n.propietarioId, destinoId, n.nombre, n.id)) {
      return err(`Ya existe un elemento llamado "${n.nombre}" en la carpeta de destino.`);
    }
    n.padreId = destinoId;
    n.modificado = ahora();
    persistir();
    return ok();
  }

  // ---------------------------------------------------------------
  // Papelera (con cascada)
  // ---------------------------------------------------------------

  function eliminar(actorId, id) {
    const n = nodo(id);
    if (!n || n.eliminado) return err('El elemento ya no existe.');
    if (!puede(actorId, n, 'eliminar')) return err('Solo el propietario puede eliminar este elemento.');
    const t = ahora();
    [n, ...descendientes(id).filter(d => !d.eliminado)].forEach(x => {
      x.eliminado = true;
      x.eliminadoEn = t;
      x.eliminadoRaiz = id;
    });
    persistir();
    return ok();
  }

  function listarPapelera(userId) {
    return db().nodos.filter(n => n.propietarioId === userId && n.eliminado && n.eliminadoRaiz === n.id);
  }

  function tamanioEnPapelera(n) {
    if (n.tipo === 'archivo') return n.tamanioMB;
    return descendientes(n.id).filter(d => d.tipo === 'archivo' && d.eliminadoRaiz === n.id).reduce((a, d) => a + d.tamanioMB, 0);
  }

  function restaurar(actorId, id) {
    const n = nodo(id);
    if (!n || n.propietarioId !== actorId || !n.eliminado || n.eliminadoRaiz !== n.id) return err('Ese elemento no está en la papelera.');
    let destino = n.padreId || null;
    let alRaiz = false;
    if (destino) {
      const padre = nodo(destino);
      if (!padre || padre.eliminado) { destino = null; alRaiz = true; }
    }
    const nombre = nombreLibre(n.propietarioId, destino, n.nombre, n.tipo === 'archivo');
    [n, ...descendientes(id).filter(d => d.eliminadoRaiz === id)].forEach(x => {
      x.eliminado = false;
      x.eliminadoEn = null;
      x.eliminadoRaiz = null;
    });
    const renombrado = nombre !== n.nombre;
    n.padreId = destino;
    n.nombre = nombre;
    n.modificado = ahora();
    persistir();
    return ok({ alRaiz, renombrado });
  }

  function borrarSubarbol(id) {
    const ids = new Set([id, ...descendientes(id).map(d => d.id)]);
    const d = db();
    d.nodos = d.nodos.filter(x => !ids.has(x.id));
    d.shares = d.shares.filter(s => !ids.has(s.itemId));
  }

  function eliminarDefinitivo(actorId, id) {
    const n = nodo(id);
    if (!n || n.propietarioId !== actorId || !n.eliminado) return err('Ese elemento no está en la papelera.');
    borrarSubarbol(id);
    persistir();
    return ok();
  }

  function vaciarPapelera(actorId) {
    const raices = listarPapelera(actorId);
    raices.forEach(r => borrarSubarbol(r.id));
    persistir();
    return ok({ cantidad: raices.length });
  }

  // ---------------------------------------------------------------
  // Compartición
  // ---------------------------------------------------------------

  function compartir(actorId, itemId, identificador, permiso) {
    if (!Auth.puede(Auth.obtenerUsuario(actorId), 'compartir')) return err('Tu rol no permite compartir archivos.');
    const n = nodo(itemId);
    if (!n || n.eliminado) return err('El elemento ya no existe.');
    if (!puede(actorId, n, 'compartir')) return err('Solo el propietario puede compartir este elemento.');
    if (!['lector', 'editor'].includes(permiso)) return err('Permiso inválido.');
    if (!Auth.validarIdentificador(identificador)) return err('Ingresá un correo o un DNI válido.');
    const objetivo = Auth.usuarioPorIdentificador(identificador); // el compañero se busca por correo o por DNI
    if (!objetivo) return err('No encontramos una cuenta con ese correo o DNI.');
    if (objetivo.estado !== 'aprobado') return err('Esa cuenta todavía no está activa.');
    if (objetivo.id === actorId) return err('Ya sos el propietario de este elemento.');

    const existente = db().shares.find(s => s.itemId === itemId && s.conId === objetivo.id);
    if (existente) existente.permiso = permiso;
    else db().shares.push({ id: Auth.generarId('s'), itemId, propietarioId: n.propietarioId, conId: objetivo.id, permiso, creado: ahora() });
    persistir();
    return ok({ nombre: objetivo.nombre });
  }

  function comparticionesDe(itemId) {
    return db().shares.filter(s => s.itemId === itemId).map(s => {
      const u = Auth.obtenerUsuario(s.conId);
      return { id: s.id, conId: s.conId, nombre: u ? u.nombre : '(cuenta eliminada)', email: u ? u.email : '', permiso: s.permiso };
    });
  }

  const cantidadComparticiones = (itemId) => db().shares.filter(s => s.itemId === itemId).length;

  function comparticionDe(userId, itemId) {
    const s = db().shares.find(x => x.itemId === itemId && x.conId === userId);
    return s ? s.id : null;
  }

  function cambiarPermisoComparticion(actorId, shareId, permiso) {
    const s = db().shares.find(x => x.id === shareId);
    if (!s || s.propietarioId !== actorId) return err('No se encontró esa compartición.');
    if (!['lector', 'editor'].includes(permiso)) return err('Permiso inválido.');
    s.permiso = permiso;
    persistir();
    return ok();
  }

  function quitarComparticion(actorId, shareId) {
    const s = db().shares.find(x => x.id === shareId);
    if (!s) return err('No se encontró esa compartición.');
    if (s.propietarioId !== actorId && s.conId !== actorId) return err('No tenés permiso para hacer eso.');
    db().shares = db().shares.filter(x => x.id !== shareId);
    persistir();
    return ok();
  }

  function compartidosConmigo(userId) {
    const mios = db().shares.filter(s => s.conId === userId);
    const res = [];
    mios.forEach(s => {
      const n = nodo(s.itemId);
      if (!n || n.eliminado) return;
      const ancestros = ruta(n.id).slice(0, -1);
      if (ancestros.some(a => mios.some(x => x.itemId === a.id))) return;
      res.push({ share: s, nodo: n, propietario: Auth.obtenerUsuario(n.propietarioId), permiso: s.permiso });
    });
    return res;
  }

  function rutaCompartida(userId, id) {
    const r = ruta(id);
    const i = r.findIndex(n => esRaizCompartida(userId, n));
    return i >= 0 ? r.slice(i) : r;
  }

  // ---------------------------------------------------------------
  // Descarga simulada
  // ---------------------------------------------------------------

  function descargar(actorId, id) {
    const n = nodo(id);
    if (!n || n.tipo !== 'archivo' || n.eliminado) return err('El archivo ya no existe.');
    if (!puede(actorId, n, 'descargar')) return err('No tenés permiso para descargar este archivo.');
    const dueno = Auth.obtenerUsuario(n.propietarioId);
    const texto = [
      'CampusCloud — descarga simulada',
      '',
      `Archivo: ${n.nombre}`,
      `Tamaño registrado: ${UI.formatoTamanio(n.tamanioMB)}`,
      `Propietario: ${dueno ? dueno.nombre : '—'}`,
      `Última modificación: ${new Date(n.modificado).toLocaleString('es-AR')}`,
      '',
      'CampusCloud todavía no guarda el contenido real de los archivos.',
      'Cuando exista el backend, esta descarga va a devolver el archivo original.',
    ].join('\r\n');
    const url = URL.createObjectURL(new Blob([texto], { type: 'text/plain;charset=utf-8' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = n.nombre;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
    return ok();
  }

  // ---------------------------------------------------------------
  // Inicialización por usuario: siembra archivos de ejemplo según el rol
  // ---------------------------------------------------------------

  function sembrarEjemplos(usuario) {
    const hace = (dias) => new Date(Date.now() - dias * 86400000).toISOString();
    const nodos = db().nodos;
    const carpeta = (nombre, dias, padreId = null) => {
      const n = nuevoNodo({ tipo: 'carpeta', nombre, padreId, propietarioId: usuario.id, creadoPorId: usuario.id, creado: hace(dias), modificado: hace(dias) });
      nodos.push(n);
      return n;
    };
    const archivo = (nombre, mb, dias, padreId = null) => {
      nodos.push(nuevoNodo({
        tipo: 'archivo', nombre, padreId, propietarioId: usuario.id, creadoPorId: usuario.id,
        tamanioMB: mb, ext: Auth.extensionDe(nombre), creado: hace(dias), modificado: hace(dias),
      }));
    };

    if (usuario.rol === 'docente') {
      const catedra = carpeta('Material de cátedra', 12);
      const so = carpeta('Sistemas Operativos', 10, catedra.id);
      const bd = carpeta('Bases de Datos', 9, catedra.id);
      const recursos = carpeta('Recursos de clase', 8, catedra.id);
      carpeta('Exámenes 2026', 20);
      carpeta('Planificaciones', 30);
      archivo('Guia_Practica_Unidad_4.pdf', 2.4, 1, catedra.id);
      archivo('entrega_final_sistemas.zip', 18.6, 2, catedra.id);
      archivo('consultas_bd3.sql', 0.02, 3, catedra.id);
      archivo('apuntes_unidad_2.pdf', 3.1, 5, catedra.id);
      archivo('procesos-y-planificacion.pdf', 4.2, 10, so.id);
      archivo('practica-shell.pdf', 1.1, 11, so.id);
      archivo('modelo-relacional.pdf', 2.8, 9, bd.id);
      archivo('plantilla-diapositivas.pptx', 5.4, 8, recursos.id);
      archivo('programa-2026.pdf', 0.9, 25);
     
      const alumno = Auth.usuarioPorEmail(Auth.CUENTAS_DEMO.alumno.email);
      if (alumno) {
        db().shares.push({ id: Auth.generarId('s'), itemId: catedra.id, propietarioId: usuario.id, conId: alumno.id, permiso: 'lector', creado: hace(4) });
      }
    } else if (usuario.rol === 'admin') {
      const doc = carpeta('Documentación', 15);
      carpeta('Backups', 30);
      archivo('politicas-de-uso.pdf', 0.6, 6, doc.id);
      archivo('manual-administrador.pdf', 1.8, 12, doc.id);
      archivo('backup-usuarios.zip', 14.2, 20);
    } else {
      const tps = carpeta('Trabajos prácticos', 9);
      const apuntes = carpeta('Apuntes', 14);
      archivo('TP1-analisis-de-requerimientos.docx', 1.2, 2, tps.id);
      archivo('entrega-tp2.zip', 8.6, 4, tps.id);
      archivo('diagrama-er.png', 0.8, 9, tps.id);
      archivo('resumen-unidad-3.pdf', 2.4, 6, apuntes.id);
      archivo('cronograma-cursada.xlsx', 0.3, 20);
    }
  }

  function asegurar(usuario) {
    const d = db();
    if (d.inicializados.includes(usuario.id)) return;
    sembrarEjemplos(usuario);
    d.inicializados.push(usuario.id);
    persistir();
  }

  return {
    nodo, ruta, rutaTexto, rutaCompartida, hijosDe, descendientes,
    tamanioCarpetaMB, tamanioEnPapelera, usoMB, usoPapeleraMB,
    permisoSobre, acciones, puede, esRaizCompartida,
    validarNombre,
    listarHijos, recientes, buscarPropios, carpetasDestino,
    crearCarpeta, validarSubida, subirArchivo, renombrar, mover,
    eliminar, listarPapelera, restaurar, eliminarDefinitivo, vaciarPapelera,
    compartir, comparticionesDe, cantidadComparticiones, comparticionDe,
    cambiarPermisoComparticion, quitarComparticion, compartidosConmigo,
    descargar, asegurar,
  };
})();