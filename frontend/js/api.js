/**
 * api.js
 * API simulada. Todas las páginas hablan con el "servidor" a través de
 * este módulo: cada función es asíncrona, tarda un poco (latencia),
 * exige sesión válida (como si mandara el JWT en Authorization) y
 * valida el ROL en el lado "servidor". Devuelve siempre
 *   { ok: true, status: 200, ...datos }   o   { ok: false, status, motivo }
 *
 * Roles y qué puede hacer cada uno:
 *   alumno   → sus archivos (subir, carpetas, papelera) y ver lo que le comparten.
 *   docente  → todo lo del alumno + compartir carpetas y archivos.
 *   admin    → todo lo del docente + panel de administración (cuentas, cuotas, políticas).
 * Un rol sin permiso recibe 403; sin sesión, 401.
 *
 * El día que exista el backend real, se reemplaza el cuerpo de cada
 * función por un pedido a Http (js/http.js) al endpoint indicado en el
 * comentario, y las páginas no cambian. Http ya manda el token
 * (Authorization: Bearer), maneja el 401, los cortes de red y devuelve el
 * mismo formato { ok, status, ... } / { ok:false, status, motivo }. Ejemplo:
 *
 *   const login = (email, password, recordar) =>
 *     Http.post('auth/login', { email, password }, { publico: true });
 *   const crearCarpeta = (padreId, nombre) =>
 *     Http.post('drive/folders', { padreId, nombre });
 *
 * Requiere auth.js, ui.js y drive.js cargados antes.
 */
const Api = (() => {
    'use strict';

    const LATENCIA_MS = 300;
    const esperar = (ms = LATENCIA_MS) => new Promise(r => setTimeout(r, ms));

    // Avisa a la barra de carga de ui.js que hay un pedido en curso.
    const avisarCarga = (delta) => {
        document.dispatchEvent(new CustomEvent('cc:carga', { detail: { delta } }));
    };
    async function enCarga(fn) {
        avisarCarga(1);
        try { return await fn(); } finally { avisarCarga(-1); }
    }

    const ROLES_QUE_COMPARTEN = Auth.CAPACIDADES.compartir; // ['docente', 'admin']

    /**
     * Ejecuta una operación como si fuera un endpoint protegido:
     * espera la "red", valida la sesión (401) y el rol (403), y
     * normaliza la respuesta. rolRequerido puede ser null (cualquier
     * rol), un rol ('admin') o una lista de roles (['docente', 'admin']).
     */
    const llamar = (rolRequerido, fn, ms) => enCarga(() => ejecutar(rolRequerido, fn, ms));

    async function ejecutar(rolRequerido, fn, ms) {
        await esperar(ms);
        const usuario = Auth.sesionActiva();
        if (!usuario) return { ok: false, status: 401, motivo: 'Tu sesión expiró. Volvé a iniciar sesión.' };
        if (rolRequerido) {
            const permitidos = Array.isArray(rolRequerido) ? rolRequerido : [rolRequerido];
            if (!permitidos.includes(usuario.rol)) return { ok: false, status: 403, motivo: 'Tu rol no tiene permiso para hacer esto.' };
        }
        let r;
        try {
            r = await fn(usuario);
        } catch (e) {
            return { ok: false, status: 500, motivo: 'Ocurrió un error inesperado. Probá de nuevo.' };
        }
        return r.ok ? { status: 200, ...r } : { status: 400, ...r };
    }

    // ---------------------------------------------------------------
    // Autenticación (públicas)
    // ---------------------------------------------------------------

    /**
     * POST /auth/login → guarda el JWT y trae los datos del usuario con GET /usuarios/me.
     * Devuelve { ok, usuario } al igual que el flujo simulado, para que login.html no cambie.
     */
    const login = (email, password, recordar = false) => enCarga(async () => {
        const r = await Http.post('auth/login', { email, password }, { publico: true });
        if (!r.ok) return r;

        const perfil = await Http.get('usuarios/me', { headers: { Authorization: `Bearer ${r.access_token}` } });
        if (!perfil.ok) return { ok: false, status: perfil.status, motivo: perfil.motivo };

        // El backend usa roles en mayúsculas (ALUMNO); el resto del frontend los espera en minúsculas.
        const usuario = {
            id: perfil.id,
            nombre: `${perfil.nombre} ${perfil.apellido}`.trim(),
            email: perfil.email,
            rol: String(perfil.rol || '').toLowerCase(),
        };
        Auth.guardarSesion(usuario, recordar, r.access_token);
        return { ok: true, status: 200, usuario, token: r.access_token };
    });

    /** GET /api/usuarios/me */
    const miPerfil = () => enCarga(async () => {
        return Http.get('usuarios/me');
    });

    /** PATCH /api/usuarios/password */
    const cambiarPassword = (password_actual, password_nueva) => enCarga(async () => {
        return Http.patch('usuarios/password', { password_actual, password_nueva });
    });

    /**
     * POST /auth/registro → el backend deja al usuario en estado PENDIENTE hasta la aprobación.
     * El frontend envía "rolSolicitado" en minúsculas; el backend espera "rol" en mayúsculas.
     */
    const registrar = (datos) => enCarga(async () => {
        const cuerpo = {
            nombre: datos.nombre,
            apellido: datos.apellido,
            dni: datos.dni,
            email: datos.email,
            password: datos.password,
            rol: String(datos.rolSolicitado || '').toUpperCase(),
        };
        return Http.post('auth/registro', cuerpo, { publico: true });
    });

    /**
     * POST /auth/forgot-password  { email }
     * Responde siempre lo mismo exista o no la cuenta (así no se revela qué
     * correos están registrados). El envío del mail lo hace el backend.
     */
    const recuperarPassword = (email) => enCarga(async () => {
        await esperar();
        if (!Auth.validarEmail(String(email || '').trim())) return { ok: false, status: 400, motivo: 'Ingresá un correo válido.' };
        return { ok: true, status: 202 };
    });

    // ---------------------------------------------------------------
    // Drive (backend real FastAPI con fallback)
    // ---------------------------------------------------------------

    /** POST /api/carpetas  { nombre, carpeta_padre_id } */
    const crearCarpeta = (padreId, nombre) => enCarga(async () => {
        const idPadreNum = padreId ? Number(padreId) : null;
        const res = await Http.post('carpetas', {
            nombre: String(nombre || '').trim(),
            carpeta_padre_id: isNaN(idPadreNum) ? null : idPadreNum
        });
        if (res.ok) {
            return { ok: true, status: 201, ...res };
        }
        // Fallback local si el endpoint no está disponible
        return llamar(null, u => Drive.crearCarpeta(u.id, padreId, nombre));
    });

    /**
     * POST /api/archivos  (multipart: archivo + carpeta_id opcional).
     * Soporta onProgress(0-100) para mostrar avance real de subida.
     */
    const subirArchivo = async (padreId, archivo, onProgress = null) => {
        const formData = new FormData();
        formData.append('archivo', archivo);
        if (padreId) {
            const idNum = Number(padreId);
            if (!isNaN(idNum)) formData.append('carpeta_id', idNum);
        }

        const res = await Http.subir('archivos', formData, { onProgress });
        if (res.status !== 0) {
            return res.ok ? { ok: true, status: 201, ...res } : res;
        }

        // Fallback local simulado en caso de error de red o backend no alcanzable
        const duracion = LATENCIA_MS + Math.min(1500, Math.round((archivo.size || 0) / (1024 * 1024)) * 15);
        let timer = null;
        if (onProgress) {
            const inicio = Date.now();
            onProgress(0);
            timer = setInterval(() => onProgress(Math.min(95, Math.round(((Date.now() - inicio) / duracion) * 100))), 80);
        }
        const r = await llamar(null, u => Drive.subirArchivo(u.id, padreId, archivo), duracion);
        if (timer) clearInterval(timer);
        if (onProgress && r.ok) onProgress(100);
        return r;
    };

    /** GET /api/archivos?carpeta_id=...&pagina=1&limite=50&q=... */
    const listarContenido = (carpetaId = null, pagina = 1, limite = 50, q = null) => enCarga(async () => {
        let ruta = `archivos?pagina=${pagina}&limite=${limite}`;
        if (carpetaId) {
            const idNum = Number(carpetaId);
            if (!isNaN(idNum)) ruta += `&carpeta_id=${idNum}`;
        }
        if (q && String(q).trim()) {
            ruta += `&q=${encodeURIComponent(String(q).trim())}`;
        }
        return Http.get(ruta);
    });

    /** GET /api/carpetas */
    const listarTodasCarpetas = () => enCarga(async () => {
        return Http.get('carpetas');
    });

    /** PATCH /api/archivos/:id/renombrar o /api/carpetas/:id/renombrar */
    const renombrar = (id, nombre, tipo = 'archivo') => enCarga(async () => {
        const endpoint = tipo === 'carpeta' ? `carpetas/${id}/renombrar` : `archivos/${id}/renombrar`;
        const res = await Http.patch(endpoint, { nombre: String(nombre).trim() });
        if (res.status === 0) return llamar(null, u => Drive.renombrar(u.id, id, nombre));
        return res;
    });

    /** PATCH /api/archivos/:id/mover o /api/carpetas/:id/mover */
    const mover = (id, destinoId, tipo = 'archivo') => enCarga(async () => {
        const endpoint = tipo === 'carpeta' ? `carpetas/${id}/mover` : `archivos/${id}/mover`;
        const dest = (destinoId && String(destinoId).trim() !== '') ? Number(destinoId) : null;
        const res = await Http.patch(endpoint, { carpeta_destino_id: dest });
        if (res.status === 0) return llamar(null, u => Drive.mover(u.id, id, destinoId));
        return res;
    });

    /** PATCH /api/archivos/:id/papelera o /api/carpetas/:id/papelera */
    const eliminar = (id, tipo = 'archivo') => enCarga(async () => {
        const endpoint = tipo === 'carpeta' ? `carpetas/${id}/papelera` : `archivos/${id}/papelera`;
        const res = await Http.patch(endpoint);
        if (res.status === 0) return llamar(null, u => Drive.eliminar(u.id, id));
        return res;
    });

    /** PATCH /api/archivos/:id/restaurar o /api/carpetas/:id/restaurar */
    const restaurar = (id, tipo = 'archivo') => enCarga(async () => {
        const endpoint = tipo === 'carpeta' ? `carpetas/${id}/restaurar` : `archivos/${id}/restaurar`;
        const res = await Http.patch(endpoint);
        if (res.status === 0) return llamar(null, u => Drive.restaurar(u.id, id));
        return res;
    });

    /** DELETE /api/archivos/:id o /api/carpetas/:id */
    const eliminarDefinitivo = (id, tipo = 'archivo') => enCarga(async () => {
        const endpoint = tipo === 'carpeta' ? `carpetas/${id}` : `archivos/${id}`;
        const res = await Http.delete(endpoint);
        if (res.status === 0) return llamar(null, u => Drive.eliminarDefinitivo(u.id, id));
        return res;
    });

    /** DELETE /api/archivos/papelera/vaciar */
    const vaciarPapelera = () => enCarga(async () => {
        const res = await Http.delete('archivos/papelera/vaciar');
        if (res.status === 0) return llamar(null, u => Drive.vaciarPapelera(u.id));
        return res;
    });

    /** GET /api/archivos/papelera */
    const listarPapelera = () => enCarga(async () => {
        const res = await Http.get('archivos/papelera');
        if (res.status === 0) return llamar(null, u => ({ ok: true, archivos: Drive.listarPapelera(u.id) }));
        if (res.ok) {
            const carpetas = Array.isArray(res.carpetas) ? res.carpetas : [];
            const archivos = Array.isArray(res.archivos) ? res.archivos : [];
            return { ok: true, status: 200, items: [...carpetas, ...archivos], carpetas, archivos };
        }
        return res;
    });

    /** GET /api/archivos/:id/descargar */
    const descargar = async (id) => {
        try {
            const token = Auth.obtenerToken();
            const resp = await fetch(`/api/archivos/${id}/descargar`, {
                headers: token ? { Authorization: `Bearer ${token}` } : {}
            });
            if (!resp.ok) {
                return llamar(null, u => Drive.descargar(u.id, id));
            }
            const blob = await resp.blob();
            let nombre = 'archivo';
            const disposition = resp.headers.get('Content-Disposition') || resp.headers.get('content-disposition');
            if (disposition && disposition.includes('filename=')) {
                nombre = disposition.split('filename=')[1].replace(/["']/g, '').trim();
            }
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = nombre;
            document.body.appendChild(a);
            a.click();
            a.remove();
            setTimeout(() => URL.revokeObjectURL(url), 1500);
            return { ok: true };
        } catch (e) {
            return llamar(null, u => Drive.descargar(u.id, id));
        }
    };

    // ---------------------------------------------------------------
    // Compartir
    // ---------------------------------------------------------------

    /**
     * GET /api/archivos/compartidos
     */
    const compartidosConmigo = () => enCarga(async () => {
        const res = await Http.get('archivos/compartidos');
        if (res.status === 0) return llamar(null, u => ({ ok: true, items: Drive.compartidosConmigo(u.id) }));
        return res;
    });

    /**
     * POST /api/permisos  { archivo_id, destinatario }
     * "destinatario" es el correo o el DNI de la otra persona.
     */
    const compartir = (id, destinatario, permiso = 'lector') => enCarga(async () => {
        const res = await Http.post('permisos', {
            archivo_id: Number(id),
            destinatario: String(destinatario).trim(),
        });
        if (res.status === 0) return llamar(ROLES_QUE_COMPARTEN, u => Drive.compartir(u.id, id, destinatario, permiso));
        return res;
    });

    /** GET /api/permisos/archivo/:id */
    const listarPermisosArchivo = (archivoId) => enCarga(async () => {
        const res = await Http.get(`permisos/archivo/${archivoId}`);
        if (res.status === 0) return { ok: true, datos: Drive.comparticionesDe(archivoId) };
        return res;
    });

    /** DELETE /api/permisos/:permisoId */
    const revocarPermiso = (permisoId) => enCarga(async () => {
        const res = await Http.delete(`permisos/${permisoId}`);
        if (res.status === 0) return llamar(null, u => Drive.quitarComparticion(u.id, permisoId));
        return res;
    });

    /** DELETE /api/permisos/archivo/:archivoId/renunciar */
    const quitarDeMisCompartidos = (archivoId) => enCarga(async () => {
        const res = await Http.delete(`permisos/archivo/${archivoId}/renunciar`);
        if (res.status === 0) return llamar(null, u => Drive.quitarComparticion(u.id, archivoId));
        return res;
    });

    /** PATCH /drive/shares/:shareId  { permiso } */
    const cambiarPermisoComparticion = (shareId, permiso) =>
        llamar(ROLES_QUE_COMPARTEN, u => Drive.cambiarPermisoComparticion(u.id, shareId, permiso));

    /** DELETE /drive/shares/:shareId  (el dueño la revoca o quien la recibió se la quita de la lista) */
    const quitarComparticion = (shareId) => revocarPermiso(shareId);

    // ---------------------------------------------------------------
    // Administración (conectado con backend real /admin)
    // ---------------------------------------------------------------

    /** GET /api/admin/usuarios/pendientes */
    const obtenerPendientes = () => enCarga(async () => {
        const res = await Http.get('admin/usuarios/pendientes');
        if (res.ok) {
            // Http.js guarda arreglos en res.datos o en res directamente si fuera objeto
            const lista = Array.isArray(res.datos) ? res.datos : (Array.isArray(res) ? res : (res.items || []));
            return { ok: true, status: 200, items: lista };
        }
        return { ok: false, status: res.status, motivo: res.motivo, items: [] };
    });

    /** PATCH /api/admin/usuarios/:id/aprobar  { id_rol } */
    const aprobarUsuario = (id, idRol) => enCarga(async () => {
        return Http.patch(`admin/usuarios/${id}/aprobar`, { id_rol: Number(idRol) });
    });

    /** PATCH /api/admin/usuarios/:id/rechazar */
    const rechazarUsuario = (id) => enCarga(async () => {
        return Http.patch(`admin/usuarios/${id}/rechazar`, {});
    });

    /** GET /api/admin/usuarios?estado=... */
    const obtenerUsuariosAdmin = (estado = null) => enCarga(async () => {
        let ruta = 'admin/usuarios';
        if (estado && estado !== 'todos') ruta += `?estado=${encodeURIComponent(estado)}`;
        const res = await Http.get(ruta);
        if (res.ok) {
            const lista = Array.isArray(res.datos) ? res.datos : (Array.isArray(res) ? res : (res.items || []));
            return { ok: true, status: 200, items: lista };
        }
        if (res.status === 0) {
            const mock = Auth.listarUsuarios().filter(u => u.estado !== 'pendiente');
            return { ok: true, status: 200, items: mock };
        }
        return { ok: false, status: res.status, motivo: res.motivo, items: [] };
    });

    /** GET /api/admin/estadisticas */
    const obtenerEstadisticasAdmin = () => enCarga(async () => {
        const res = await Http.get('admin/estadisticas');
        if (res.ok) return { ok: true, status: 200, ...res };
        return res;
    });

    /** GET /api/admin/roles */
    const obtenerRolesAdmin = () => enCarga(async () => {
        const res = await Http.get('admin/roles');
        if (res.ok) {
            const lista = Array.isArray(res.datos) ? res.datos : (Array.isArray(res) ? res : (res.items || []));
            return { ok: true, status: 200, items: lista };
        }
        return res;
    });

    /** PATCH /api/admin/roles/:idRol */
    const actualizarRolAdmin = (idRol, cuotaMB, maxFileMB) => enCarga(async () => {
        const payload = {};
        if (cuotaMB !== undefined) payload.cuota_total_mb = cuotaMB;
        if (maxFileMB !== undefined) payload.max_file_size_mb = maxFileMB;
        return Http.patch(`admin/roles/${idRol}`, payload);
    });

    /** GET /api/admin/extensiones */
    const obtenerExtensionesAdmin = () => enCarga(async () => {
        const res = await Http.get('admin/extensiones');
        if (res.ok) {
            const lista = Array.isArray(res.datos) ? res.datos : (Array.isArray(res) ? res : (res.items || []));
            return { ok: true, status: 200, items: lista };
        }
        return res;
    });

    /** GET /api/admin/roles/:idRol/extensiones-bloqueadas */
    const obtenerExtensionesBloqueadasRol = (idRol) => enCarga(async () => {
        const res = await Http.get(`admin/roles/${idRol}/extensiones-bloqueadas`);
        if (res.ok) {
            const lista = Array.isArray(res.datos) ? res.datos : (Array.isArray(res) ? res : (res.items || []));
            return { ok: true, status: 200, items: lista };
        }
        return res;
    });

    /** PUT /api/admin/roles/:idRol/extensiones-bloqueadas */
    const reemplazarExtensionesBloqueadasRol = (idRol, ids) => enCarga(async () => {
        return Http.put(`admin/roles/${idRol}/extensiones-bloqueadas`, { ids_extensiones: ids });
    });

    /** GET /api/admin/usuarios/:id/extensiones-prohibidas */
    const obtenerExtensionesProhibidasUsuario = (id) => enCarga(async () => {
        const res = await Http.get(`admin/usuarios/${id}/extensiones-prohibidas`);
        if (res.ok) {
            const lista = Array.isArray(res.datos) ? res.datos : (Array.isArray(res) ? res : (res.items || []));
            return { ok: true, status: 200, items: lista };
        }
        return res;
    });

    /** PUT /api/admin/usuarios/:id/extensiones-prohibidas */
    const reemplazarExtensionesProhibidasUsuario = (id, ids) => enCarga(async () => {
        return Http.put(`admin/usuarios/${id}/extensiones-prohibidas`, { ids_extensiones: ids });
    });

    /** PATCH /api/admin/usuarios/:id/estado */
    const cambiarEstadoUsuario = (id, estado, opciones = {}) => enCarga(async () => {
        const res = await Http.patch(`admin/usuarios/${id}/estado`, { estado: String(estado).toUpperCase() });
        if (res.status === 0) return llamar('admin', () => Auth.cambiarEstadoUsuario(id, estado, opciones));
        return res;
    });

    /** PATCH /api/admin/usuarios/:id/rol */
    const cambiarRol = (id, idRol) => enCarga(async () => {
        const res = await Http.patch(`admin/usuarios/${id}/rol`, { id_rol: Number(idRol) });
        if (res.status === 0) {
            return llamar('admin', () => {
                const u = Auth.obtenerUsuario(id);
                if (!u) return { ok: false, motivo: 'No se encontró la cuenta.' };
                return Auth.cambiarRol(id, idRol);
            });
        }
        return res;
    });

    /** PATCH /api/admin/usuarios/:id/cuota */
    const cambiarCuota = (id, cuotaMB, maxFileMB = undefined) => enCarga(async () => {
        const payload = {
            cuota_personalizada_mb: cuotaMB == null ? null : Number(cuotaMB),
        };
        if (maxFileMB !== undefined) {
            payload.max_file_personalizado_mb = maxFileMB == null ? null : Number(maxFileMB);
        }
        const res = await Http.patch(`admin/usuarios/${id}/cuota`, payload);
        if (res.status === 0) {
            return llamar('admin', () => {
                const u = Auth.obtenerUsuario(id);
                if (!u) return { ok: false, motivo: 'No se encontró la cuenta.' };
                const excepciones = { ...u.excepciones };
                if (cuotaMB == null) delete excepciones.cuotaMB; else excepciones.cuotaMB = cuotaMB;
                return Auth.guardarExcepciones(id, excepciones);
            });
        }
        return res;
    });

    /** PUT /admin/users/:id/overrides */
    const guardarExcepciones = (id, excepciones) =>
        llamar('admin', () => {
            const u = Auth.obtenerUsuario(id);
            if (!u) return { ok: false, motivo: 'No se encontró la cuenta.' };
            const pol = Auth.politicaEfectiva({ ...u, excepciones });
            const uso = Drive.usoMB(id);
            if (uso > pol.cuotaMB) {
                return { ok: false, motivo: `La cuenta ya usa ${UI.formatoTamanio(uso)}, más que el espacio que quedaría (${UI.formatoTamanio(pol.cuotaMB)}).` };
            }
            return Auth.guardarExcepciones(id, excepciones);
        });

    /** PUT /admin/policies/global */
    const guardarPoliticaGlobal = (politica) =>
        llamar('admin', () => Auth.guardarPoliticaGlobal(politica));

    /** PUT /admin/policies/roles/:rol */
    const guardarPoliticaRol = (rol, politica) =>
        llamar('admin', () => Auth.guardarPoliticaRol(rol, politica));

    /** DELETE /admin/policies */
    const restaurarPoliticas = () =>
        llamar('admin', () => { Auth.restaurarPoliticas(); return { ok: true }; });

    return {
        login, registrar, recuperarPassword, miPerfil, cambiarPassword,
        crearCarpeta, listarTodasCarpetas, subirArchivo, listarContenido, renombrar, mover, eliminar, restaurar,
        eliminarDefinitivo, vaciarPapelera, listarPapelera, descargar,
        compartir, compartidosConmigo, cambiarPermisoComparticion, quitarComparticion,
        listarPermisosArchivo, revocarPermiso, quitarDeMisCompartidos,
        obtenerPendientes, aprobarUsuario, rechazarUsuario,
        obtenerUsuariosAdmin, obtenerEstadisticasAdmin, obtenerRolesAdmin, actualizarRolAdmin,
        obtenerExtensionesAdmin, obtenerExtensionesBloqueadasRol, reemplazarExtensionesBloqueadasRol,
        obtenerExtensionesProhibidasUsuario, reemplazarExtensionesProhibidasUsuario,
        cambiarEstadoUsuario, cambiarRol, guardarExcepciones, cambiarCuota,
        guardarPoliticaGlobal, guardarPoliticaRol, restaurarPoliticas,
    };
})();