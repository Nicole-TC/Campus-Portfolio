// Todo pasa por Nginx bajo el mismo dominio, en el prefijo /api/
const API_BASE = "/api";

// Ejemplo de cómo se va a llamar a la API una vez que el equipo de
// backend tenga los endpoints listos. Ir sumando funciones acá:
//
// async function login(usuario, contrasena) {
//   const resp = await fetch(`${API_BASE}/auth/login`, { ... });
//   ...
// }
