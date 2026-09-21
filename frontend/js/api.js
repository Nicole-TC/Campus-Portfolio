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

    /** POST /auth/login  { email, password } → { token, usuario } */
    const login = (email, password, recordar = false) => enCarga(async () => {
        await esperar();
        const r = Auth.iniciarSesion(email, password, recordar);
        return r.ok ? { status: 200, ...r } : { status: 401, ...r };
    });

    /** POST /auth/register  { nombre, email, dni, password, rolSolicitado } */
    const registrar = (datos) => enCarga(async () => {
        await esperar();
        const r = Auth.registrarUsuario(datos);
        return r.ok ? { status: 201, ...r } : { status: 409, ...r };
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
    // Drive (requieren sesión; los tres roles)
    // ---------------------------------------------------------------

    /** POST /drive/folders  { padreId, nombre } */
    const crearCarpeta = (padreId, nombre) =>
        llamar(null, u => Drive.crearCarpeta(u.id, padreId, nombre));

    /**
     * POST /drive/files  (multipart: padreId + archivo). La latencia crece con el tamaño.
     * onProgress(0-100) es opcional. Acá el avance es simulado; con backend real
     * se usa Http.subir('drive/files', formData, { onProgress }), que da el
     * progreso real de la subida.
     */
    const subirArchivo = async (padreId, archivo, onProgress = null) => {
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

    /** PATCH /drive/items/:id  { nombre } */
    const renombrar = (id, nombre) =>
        llamar(null, u => Drive.renombrar(u.id, id, nombre));

    /** PATCH /drive/items/:id  { padreId } */
    const mover = (id, destinoId) =>
        llamar(null, u => Drive.mover(u.id, id, destinoId));

    /** DELETE /drive/items/:id  (a la papelera, en cascada) */
    const eliminar = (id) =>
        llamar(null, u => Drive.eliminar(u.id, id));

    /** POST /drive/trash/:id/restore */
    const restaurar = (id) =>
        llamar(null, u => Drive.restaurar(u.id, id));

    /** DELETE /drive/trash/:id */
    const eliminarDefinitivo = (id) =>
        llamar(null, u => Drive.eliminarDefinitivo(u.id, id));

    /** DELETE /drive/trash */
    const vaciarPapelera = () =>
        llamar(null, u => Drive.vaciarPapelera(u.id));

    /** GET /drive/files/:id/download */
    const descargar = (id) =>
        llamar(null, u => Drive.descargar(u.id, id));

    // ---------------------------------------------------------------
    // Compartir (solo docente y admin; el alumno recibe pero no comparte)
    // ---------------------------------------------------------------

    /**
     * GET /drive/shares/received  → { items: [{ share, nodo, propietario, permiso }] }
     * Lo que otras personas compartieron con quien tiene la sesión. Lo pueden
     * pedir los tres roles (el alumno recibe aunque no comparta).
     */
    const compartidosConmigo = () =>
        llamar(null, u => ({ ok: true, items: Drive.compartidosConmigo(u.id) }));

    /**
     * POST /drive/items/:id/shares  { destinatario, permiso }
     * "destinatario" es el correo o el DNI de la otra persona.
     */
    const compartir = (id, destinatario, permiso) =>
        llamar(ROLES_QUE_COMPARTEN, u => Drive.compartir(u.id, id, destinatario, permiso));

    /** PATCH /drive/shares/:shareId  { permiso } */
    const cambiarPermisoComparticion = (shareId, permiso) =>
        llamar(ROLES_QUE_COMPARTEN, u => Drive.cambiarPermisoComparticion(u.id, shareId, permiso));

    /** DELETE /drive/shares/:shareId  (el dueño la revoca o quien la recibió se la quita de la lista) */
    const quitarComparticion = (shareId) =>
        llamar(null, u => Drive.quitarComparticion(u.id, shareId));

    // ---------------------------------------------------------------
    // Administración (solo rol admin)
    // ---------------------------------------------------------------

    /** PATCH /admin/users/:id/status  { estado, motivo?, rol? }  (al aprobar se fija el rol final) */
    const cambiarEstadoUsuario = (id, estado, opciones) =>
        llamar('admin', () => Auth.cambiarEstadoUsuario(id, estado, opciones));

    /** PATCH /admin/users/:id/role  { rol }  — no deja bajar a un rol cuya cuota no alcance para lo ya guardado */
    const cambiarRol = (id, rol) =>
        llamar('admin', () => {
            const u = Auth.obtenerUsuario(id);
            if (!u) return { ok: false, motivo: 'No se encontró la cuenta.' };
            const pol = Auth.politicaEfectiva({ ...u, rol });
            const uso = Drive.usoMB(id);
            if (uso > pol.cuotaMB) {
                return { ok: false, motivo: `El rol ${Auth.ROLES[rol]} tiene ${UI.formatoTamanio(pol.cuotaMB)} de espacio y la cuenta ya usa ${UI.formatoTamanio(uso)}. Liberá espacio o cargá una excepción antes de cambiar el rol.` };
            }
            return Auth.cambiarRol(id, rol);
        });

    /** PUT /admin/users/:id/overrides  { cuotaMB?, maxArchivoMB?, extensiones? } */
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

    /** PATCH /admin/users/:id/quota  { cuotaMB }  — null vuelve al valor que corresponde al rol */
    const cambiarCuota = (id, cuotaMB) =>
        llamar('admin', () => {
            const u = Auth.obtenerUsuario(id);
            if (!u) return { ok: false, motivo: 'No se encontró la cuenta.' };
            const excepciones = { ...u.excepciones };
            if (cuotaMB == null) delete excepciones.cuotaMB; else excepciones.cuotaMB = cuotaMB;
            const pol = Auth.politicaEfectiva({ ...u, excepciones });
            const uso = Drive.usoMB(id);
            if (uso > pol.cuotaMB) {
                return { ok: false, motivo: `La cuenta ya usa ${UI.formatoTamanio(uso)}, más que la cuota que le querés dar (${UI.formatoTamanio(pol.cuotaMB)}).` };
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
        login, registrar, recuperarPassword,
        crearCarpeta, subirArchivo, renombrar, mover, eliminar, restaurar,
        eliminarDefinitivo, vaciarPapelera, descargar,
        compartir, compartidosConmigo, cambiarPermisoComparticion, quitarComparticion,
        cambiarEstadoUsuario, cambiarRol, guardarExcepciones, cambiarCuota,
        guardarPoliticaGlobal, guardarPoliticaRol, restaurarPoliticas,
    };
})();