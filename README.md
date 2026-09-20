# RepositorioInterno - CampusCloud ☁️

**CampusCloud** es una plataforma institucional de almacenamiento y gestión de archivos en la nube (inspirada en la experiencia de *Google Drive*). Permite a los miembros de la comunidad educativa almacenar, organizar, compartir y gestionar sus recursos digitales de forma segura y controlada.

---

## 📌 Visión General del Servicio y Módulos

### 🚀 Concepto Principal
Los usuarios se registran en la web y quedan en estado pendiente hasta ser aprobados por los administradores vía **Telegram**. Una vez activados, acceden a un entorno privado donde pueden subir archivos, crear carpetas virtuales y colaborar con otros usuarios dentro de los límites y políticas configuradas por la administración.

### 🧩 Módulos de la Plataforma

| Módulo | Descripción y Funcionalidades Clave |
| :--- | :--- |
| 📁 **Mis Archivos** modulo | Explorador central de archivos y carpetas propias. Incluye un **sistema de paginación** que segmenta las consultas para optimizar el tráfico y evitar saturar el navegador con grandes volúmenes de datos. Permite ordenar, buscar y mover archivos entre carpetas virtuales. |
| 📂 **Carpetas Virtuales** funcionalidad| Organización jerárquica tipo árbol sin impacto en disco físico (la BD gestiona las relaciones mientras el disco permanece plano). |
| 🔗 **Compartir Archivos** funcionalidad| Capacidad de compartir documentos o recursos específicos con otros usuarios registrados de la plataforma, otorgándoles acceso de lectura/descarga. |
| 👥 **Compartidos Conmigo** modulo| Vista dedicada donde el usuario puede explorar, filtrar y descargar los archivos que otros compañeros o docentes le han compartido. |
| 🗑️ **Papelera de Reciclaje** modulo| Sistema de borrado seguro en 2 pasos: los elementos eliminados van a la papelera (soft delete) donde pueden ser **restablecidos** o **eliminados definitivamente** (hard delete en disco y BD). |
| 👤 **Mi Perfil** modulo| Panel de usuario con métricas de almacenamiento en tiempo real: porcentaje de disco ocupado, **cuota máxima asignada**, tamaño máximo por archivo y **extensiones/formatos permitidos** para su cuenta. |
| 🛡️ **Panel de Administración** modulo| Configuración avanzada de políticas de almacenamiento y cuotas. El administrador puede definir límites y extensiones a tres niveles: **Global**, por **Rol** (`DOCENTE`, `ALUMNO`), o por **Usuario específico** (excepciones individuales).podra gestionar la congiracion respecto a los archivo, cuanto puede pesar como maximo un archivo individual, y el tamaño total de espacio que puede ocupar cada usuario en el sistema, las extenciones de archivos permitidos y ademas podra aprovar o rechazar los registros de usuarios nuevos que se registren en la plataforma pero esto seria un modulo nuevo|
| 🤖 **Bot de Telegram** | Enlace móvil del sistema para aprobaciones de altas en tiempo real para administradores, notificaciones de estado respecto a su registro, consulta de estatus de su cuenta y consultas express/subidas para los usuarios. |

---

## Arquitectura y Circuitos del Sistema

### 1. Circuito de Registro y Aprobación (Onboarding Seguro)

Este flujo resuelve el problema de la autenticación de roles sin depender de un servidor de correos ni confiar ciegamente en lo que el usuario declara:

1. **Solicitud en la Web:** El usuario completa sus datos en el formulario web (Nombre, DNI, Email, Contraseña) y selecciona el rol que asegura tener (`ALUMNO` o `DOCENTE`).
2. **Persistencia protegida:** El backend hashea la contraseña con `bcrypt` y guarda el registro en la tabla `usuarios` con `activo = FALSE` y `estado = 'PENDIENTE'`.
3. **Respuesta inmediata al frontend:** El frontend le informa al usuario:  
   > *"Tu registro fue enviado a revisión. Te notificaremos cuando el administrador lo autorice."*  
   Si el usuario intenta iniciar sesión en este estado, la API responde con `403 Forbidden: Cuenta no activada`.
4. **Alerta interactiva para el Administrador (Telegram):** FastAPI dispara un mensaje al grupo/chat de administradores con los datos del postulante y botones interactivos: `[Aprobar Alumno]`, `[Aprobar Docente]`, `[Rechazar]`.
5. **Activación:** Cuando un administrador pulsa un botón en Telegram, el bot realiza una petición a la API que ejecuta:
   ```sql
   UPDATE usuarios 
   SET activo = TRUE, rol_id = :rol_elegido, estado = 'ACTIVO' 
   WHERE id = :user_id;
   ```
6. **Notificación al Usuario:** El sistema envía una alerta directa al usuario por Telegram confirmándole si fue **aprobado** (habilitando su ingreso) o **rechazado** con el motivo correspondiente.

---

### 2. Circuito de Autenticación y Sesión (JWT)

1. El usuario envía sus credenciales mediante `POST /api/auth/login`.
2. El backend busca al usuario por email o nombre de usuario:
   - Verifica con `bcrypt.verify` que el hash coincida.
   - Verifica que `activo == TRUE` (cuenta aprobada).
3. Si todo es correcto, genera un **Token JWT** firmado con la clave secreta (`JWT_SECRET`) que contiene en su payload:
   ```json
   {
     "sub": "uuid-del-usuario",
     "rol": "ALUMNO",
     "exp": 1758156000
   }
   ```
4. El navegador guarda ese token en `localStorage`. A partir de ese momento, en cada petición de JavaScript (`fetch`), se agrega la cabecera:
   ```javascript
   headers: {
     "Authorization": `Bearer ${token}`
   }
   ```
5. En el backend, un middleware o dependencia en FastAPI decodifica el token en cada llamada. Si el token expiró o fue adulterado, rechaza la petición con `401 Unauthorized`.

---

### 3. El Corazón del Sistema: Motor de Cuotas, Políticas y Subida de Archivos

El sistema garantiza que nadie sature el disco de la VPS mediante políticas de control configurables por el administrador a tres niveles jerárquicos:

#### ⚙️ Jerarquía de Políticas de Almacenamiento
1. **Nivel Usuario (Específico):** Reglas individuales asignadas a un usuario en particular (override prioritario para excepciones académicas o becarios).
2. **Nivel Rol (Docente / Alumno):** Políticas predeterminadas por tipo de usuario (ej. Docentes: 500 MB cuota / 50 MB por archivo; Alumnos: 100 MB cuota / 10 MB por archivo).
3. **Nivel Global:** Parámetros base del sistema en caso de no existir una regla específica.

*Cada política define: cuota total máxima (MB), tamaño tope individual por archivo (MB) y lista blanca/negra de extensiones permitidas.*

#### 🔄 Algoritmo de Validación de Subida:

```text
                           [ Petición de Subida: POST /api/archivos ]
                                               │
                                               ▼
                              ¿Extensión en lista prohibida?
                              (o no permitida según la política, ej: exe, sh, etc)
                                   ├── SÍ ──> [ Error 400 Bad Request: Tipo de archivo no permitido ]
                                   │
                                   └── NO
                                       │
                                       ▼
                              ¿Tamaño archivo > tope_maximo (Usuario/Rol)?
                                   ├── SÍ ──> [ Error 413 Payload Too Large: Archivo individual supera el tope ]
                                   │
                                   └── NO
                                       │
                                       ▼
               Consultar espacio ya usado en PostgreSQL:
               SELECT COALESCE(SUM(tamano_bytes), 0) FROM archivos WHERE usuario_id = :uid(es un ejemplo)
                                       │
                                       ▼
         ¿(Espacio Usado + Tamaño del Archivo Nuevo) > Cuota Total Asignada?
                                   ├── SÍ ──> [ Error 413 Payload Too Large: Cuota de almacenamiento agotada ]
                                   │
                                   └── NO (Aprobado)
                                       │
                                       ├── 1. Generar UUIDv4 para el archivo en disco (ej. a3f1c9...bin)
                                       ├── 2. Escribir stream de bytes en: /storage/users/{user_uuid}/{file_uuid}.bin
                                       ├── 3. INSERT en tabla 'archivos' con el nombre original, ruta, bytes y carpeta_id
                                       └── 4. Retornar 201 Created con el nuevo espacio consumido
```

> [!TIP]
> **¿Por qué este orden?**  
> Porque las validaciones más "baratas" en costo computacional (extensión y tamaño de cabecera) se hacen primero. Si el archivo es un `.exe` no permitido o pesa más de lo autorizado, el servidor lo rechaza en milisegundos sin consultar la base de datos ni escribir un solo byte en el disco.

---

### 4. Lógica de Carpetas Virtuales (Organización sin I/O en Disco)

Para no complicar el sistema operativo ni lidiar con permisos de carpetas anidadas en Linux:

- **En el disco físico:** Todos los archivos de un usuario residen en una sola carpeta plana: `/storage/users/{user_uuid}/`. No se crean subcarpetas reales en el disco.
- **En la base de datos:** Se modela una estructura de árbol en la tabla `carpetas`:
  - Una carpeta tiene: `id`, `nombre`, `usuario_id` y `carpeta_padre_id`.
  - Si `carpeta_padre_id IS NULL`, la carpeta está en la raíz.
  - Si tiene un ID, es una subcarpeta dentro de otra.
- **En la tabla `archivos`:** Solo tiene una columna `carpeta_id`.
  - **Para ver el contenido de la raíz:**
    ```sql
    SELECT * FROM archivos WHERE usuario_id = :uid AND carpeta_id IS NULL;
    SELECT * FROM carpetas WHERE usuario_id = :uid AND carpeta_padre_id IS NULL;
    ```
  - **Para entrar a una carpeta:** El frontend hace fetch pasando el ID de esa carpeta:
    ```http
    GET /api/archivos?carpeta_id=uuid-de-carpeta
    ```

> **Ventaja competitiva:** Si el usuario renombra una carpeta o mueve 100 archivos adentro, la operación tarda milisegundos porque solo ejecuta un `UPDATE` en SQL. El disco físico ni se entera.

---

### 5. Lógica de Paginación y Exploración Central (`/api/archivos`)

Para evitar saturar la memoria del navegador y el ancho de banda cuando un usuario acumula cientos de documentos:
- El endpoint `GET /api/archivos` implementa **paginación optimizada**
- El frontend renderiza controles de paginación que cargan bloques específicos bajo demanda sin sobrecargar la interfaz.

---

### 6. Lógica de Compartición de Archivos (Módulo "Compartidos Conmigo")

Permite a los usuarios colaborar y compartir documentos sin duplicar el archivo físico en el disco:
- **Modelo Relacional:** Se utiliza una tabla intermedia `archivos_compartidos`: ESTA TABLA ES UN EJEMPLO ANALIZAR BIEN SI SERIA CORRECTO
  - `id`: UUID único del registro.
  - `archivo_id`: Referencia al archivo en la tabla `archivos`.
  - `usuario_destino_id`: Referencia al usuario destinatario en `usuarios`.
  - `fecha_compartido`: Timestamp de creación.
  - `permisos`: Nivel de acceso otorgado (`LECTURA`, `DESCARGA`).
- **Módulo "Compartidos Conmigo" (`GET /api/archivos/compartidos`):**
  - Consulta los registros donde `usuario_destino_id == :mi_usuario_id`.
  - El usuario receptor puede explorar, previsualizar y descargar el archivo de forma directa.
- **Políticas de Seguridad y Cuota:**
  - El archivo compartido **solo consume almacenamiento del usuario propietario original** (no descuenta espacio de la cuota del receptor).
  - El receptor no tiene permisos para renombrar, mover a la papelera o eliminar definitivamente el archivo compartido.

---

### 7. Lógica de Descarga y Gestión de Eliminación (Papelera y Borrado Definitivo)

#### A. Descarga (`GET /api/archivos/{id}/descargar`)
1. El backend recibe el ID del archivo y el JWT del usuario autenticado.
2. Valida permisos: el usuario debe ser el propietario directo (`archivo.usuario_id == usuario_actual.id`) o contar con un permiso válido en `archivos_compartidos`.
3. Utiliza la clase `FileResponse` de FastAPI:
   - Abre el archivo físico (`/storage/users/.../{uuid}.bin`).
   - Inyecta la cabecera HTTP:
     ```http
     Content-Disposition: attachment; filename="nombre_original_con_espacios.pdf"
     ```
4. El navegador inicia la descarga con su nombre legible original.

#### B. Gestión de Eliminación: Papelera (Soft Delete) y Borrado Definitivo (Hard Delete)

Siguiendo las buenas prácticas y para evitar la pérdida accidental de datos, el sistema implementa un ciclo de vida en dos etapas para la eliminación de archivos y carpetas:

##### 1. Mover a la Papelera (Soft Delete / Eliminación Lógica)
Cuando el usuario pulsa "Eliminar" desde su vista principal:
- **No se destruye el archivo físico en disco ni se borra el registro de la base de datos.**
- Se realiza una eliminación lógica marcando el recurso (`PATCH /api/archivos/{id}/papelera` o `PATCH /api/carpetas/{id}/papelera`):
  ```sql
  UPDATE archivos 
  SET en_papelera = TRUE, fecha_eliminacion = NOW() 
  WHERE id = :id AND usuario_id = :uid;
  ```
  *(Si se envía una carpeta a la papelera, sus subcarpetas y archivos contenidos también se marcan con `en_papelera = TRUE` en cascada).*
- **Resultado:** El elemento desaparece de la vista activa de archivos/carpetas y pasa a listarse exclusivamente en el módulo de la **Papelera**.

---

##### 2. Módulo de Papelera de Reciclaje
Dentro de la sección de la papelera, el usuario puede gestionar los elementos descartados mediante dos caminos:
**Mientras un archivo esté en la papelera, debe seguir consumiendo cuota. Si no, un alumno podría llenar sus 250 MB, mandar todo a la papelera y subir otros 250 MB infinitamente. EN EL CASO DE QUE ESTE EN LA PAPELERA NO SE DEBE MOSTRAR EN EL EXPLORADOR DE ARCHIVOS Y DEBE SEGUIR OCUPANDO ESPACIO EN LA CUOTA DEL USUARIO**
* **Opción A: Restablecer / Restaurar (`POST /api/papelera/{id}/restaurar`)**
  - Devuelve el archivo o carpeta a su estado activo:
    ```sql
    UPDATE archivos 
    SET en_papelera = FALSE, fecha_eliminacion = NULL 
    WHERE id = :id AND usuario_id = :uid;
    ```
  - *(Si la carpeta contenedora original ya fue destruida, el recurso se restaura en la raíz).*
  - Vuelve a figurar inmediatamente en el explorador de archivos.

* **Opción B: Eliminación Definitiva (`DELETE /api/papelera/{id}/definitivo`)** CUIDADO AL MOMENTO DE TESTEAR Y SOLO SE PODRA REALIZAR EN LA VPS LO TESTEAN LOS LIDERES
  - Esta acción es permanente e irreversible:
    1. Se valida que el recurso pertenezca al usuario autenticado.
    2. **Si es un archivo individual:**
       - Se ejecuta `os.remove(ruta_fisica)` en el disco de la VPS para liberar los bloques reales de almacenamiento.
       - Se ejecuta la eliminación en PostgreSQL:
         ```sql
         DELETE FROM archivos WHERE id = :id AND usuario_id = :uid;
         ```
    3. **Si es una carpeta:**
       - Se recorren todos los archivos contenidos (y en subcarpetas) para eliminarlos físicamente del disco con `os.remove()`.
       - Se eliminan recursivamente los registros de `archivos` y `carpetas` en PostgreSQL.
    4. **Efecto automático:** En la próxima llamada a `/api/usuarios/me`, la sumatoria `SUM(tamano_bytes)` reflejará la reducción real de almacenamiento y la barra de progreso del frontend liberará espacio.

---

### 8. Módulo de Perfil y Monitoreo de Cuota (`/api/usuarios/me`)

Permite al usuario tener transparencia total sobre los límites y estado de su cuenta:
- **Respuesta con métricas en tiempo real:**
- **Visualización en Frontend:** Barra de progreso interactiva con cambio de color según el porcentaje de ocupación (verde, amarillo y rojo al superar el 85%) y listado legible de formatos habilitados.

---

### 9. El Bot de Telegram: Puente Móvil y Operativo

El bot actúa como un puente directo entre la mensajería móvil y la API de FastAPI. Se divide en dos módulos funcionales:

#### 🛡️ Módulo 1: Administrador (Núcleo Operativo del Registro)
* **Notificación en tiempo real:** Cuando un usuario nuevo completa el formulario web, el backend envía un mensaje inmediato al grupo o chat privado de administradores con el Nombre, DNI, Correo y Rol pretendido.
* **Aprobación en un clic:** Mediante botones interactivos (`Inline Keyboards`), el admin pulsa `[Aprobar Alumno]`, `[Aprobar Docente]` o `[Rechazar]`.
* **Impacto directo en BD:** Al presionar el botón, Telegram envía la acción a FastAPI, que ejecuta el `UPDATE` en PostgreSQL pasando el estado a `ACTIVO` y asignando la cuota correspondiente. El administrador no necesita abrir la web para dar altas.
* **Notificación al solicitante:** Se dispara un mensaje automático al usuario confirmando si fue aceptado o rechazado.

#### 📱 Módulo 2: Alumno / Usuario (Asistente Móvil de Bolsillo)
* **Aprobación de registro:** El usuario recibe un mensaje de confirmación o rechazo de su registro en la plataforma.
* **Consulta de estatus de cuenta (`/status`):** El usuario consulta cuánto almacenamiento le queda disponible y el bot responde con el porcentaje consumido y espacio libre restante.
* **Listado rápido (`/archivos` o `/mis_archivos`):** Lista los últimos archivos subidos con fecha y tamaño.
* **Subida Express:** El usuario le reenvía una foto, PDF o apunte al chat del bot; este descarga el archivo temporal de Telegram y se lo transfiere a la API de FastAPI para guardarlo en su carpeta personal previa validación de cuota y extensiones.


---


## Estructura del proyecto

```
campuscloud/
├── docker-compose.yml       → orquesta los 3 contenedores
├── .env.                    → variables de entorno
├── backend/                  → API en FastAPI (Python) — desarrolla 2° año
│   └── app/
│       ├── main.py            → arranque de la app (ya funciona, es la base)
│       ├── config.py          → contiene las variables de entorno de la API
│       ├── routers/           → acá van los endpoints (auth, archivos, admin...)
│       └── services/          → acá va la lógica de negocio (cuotas, etc.)
├── bot/                       → bot de Telegram — desarrolla 2° año
├── frontend/                  → HTML + Bootstrap + JS sin frameworks — desarrolla 1° año
└── nginx/                     → reverse proxy (ya configurado, no hace falta tocarlo)
```

## Cómo levantar el esqueleto

1. Crear un archivo .env en la misma carpeta donde se encuentra el docker-compose.yml:
   ```bash
   nano .env
   ```
   Crear la red:
   ```bash
   docker network create campuscloud_net
   ```

2. Levantar todo con Docker Compose:
   ```bash
   docker compose up --build
   ```

3. Verificar que el backend responde: `localhost:PUBLIC_PORT/api/salud` (reemplazar PUBLIC_PORT por el puerto que corresponda)
   Debería devolver `{"status": "ok", ...}`.

4. Verificar que el frontend carga: `localhost:PUBLIC_PORT` (reemplazar PUBLIC_PORT por el puerto que corresponda)

5. La documentación interactiva de la API (Swagger) va a estar en `http://localhost:PUBLIC_PORT/api/docs` a medida que se agreguen endpoints.

## Cómo trabaja cada subequipo

- **1° año (frontend):** trabaja solo adentro de `frontend/`. **No hace falta que toquen Docker ni el backend** — solo escriben HTML/CSS/JS y consumen la API con `fetch` a través de `/api/...`.
- **2° año (backend + bot):** trabaja adentro de `backend/app/` (creando sus propios `models.py`, `schemas.py`, `routers/*.py`, etc.) y adentro de `bot/bot.py`. El `docker-compose.yml` ya está armado para que los cambios de código en `backend/app/` se vean sin necesidad de reconstruir la imagen (gracias al volumen montado).
- **Líderes:** mantienen `docker-compose.yml`, `nginx.conf` y la configuración general. Revisan Pull Requests antes de mergear a la rama principal.

## Buenas prácticas ya aplicadas en esta base

- `.env` fuera de git (`.gitignore`) y fuera de las imágenes Docker (`.dockerignore`).
- Ninguna URL, usuario, contraseña o token hardcodeado en el código — todo se lee desde variables de entorno.
- Backend expuesto solo internamente (`expose`, no `ports`); todo el tráfico externo pasa por Nginx.

-EN EL BACKEND LA PARTE DE DESARROLLO DE CODIGO EVITAR HARCODEO EN TODO MOMENTO, TODO DEBE SER DINAMICO CON BASE DE DATOS , POR EJEMPLO NO SE SABE SI EL ARCHIVO SE LLAMA FINAL O FINAL_FINAL1, FINAL_FINAL2,ETC ENTONCES EN ESOS CASOS SE DEBE REALIZAR EN BASE DE DATOS Y NO EN EL CODIGO, SERA MUY UTIL Y LO HAN USADO EN PROYECTOS

