# ⚙️ Capa de Servicios (`app/services/`)

Este directorio contiene la **lógica de negocio** y los algoritmos pesados de CampusCloud. 

---

## 🎯 ¿Cuál es el propósito de esta carpeta?

En una arquitectura limpia, los **routers** (controladores) solo deben encargarse de recibir peticiones HTTP, validar que los datos lleguen bien y devolver una respuesta. **No deben contener cálculos complejos ni operaciones de disco.**

Todo el procesamiento real se delega a los **servicios**:
* **Separación de responsabilidades:** El código queda modular, fácil de leer y testear.
* **Reutilización:** Una misma función de negocio puede ser consumida tanto por la API web (`routers/`) como por el Bot de Telegram (`bot/`) sin duplicar lógica.

---

## 🚫 ¿Va incluido en `main.py`?

**No.** Los servicios **nunca se incluyen en `main.py`**.  
Se importan directamente adentro del router o módulo que los necesite.

---

## 💡 Ejemplo de cómo se usa un servicio dentro de un router

```python
# app/routers/archivos.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.cuota import validar_espacio_disponible
from app.services.almacenamiento import guardar_archivo_en_disco

router = APIRouter(prefix="/archivos", tags=["Archivos"])

@router.post("/subir")
async def subir_archivo(file: UploadFile, db: Session = Depends(get_db)):
    # 1. El router delega la validación pesada al servicio
    puede_subir = validar_espacio_disponible(usuario_actual.id, file.size, db)
    if not puede_subir:
        raise HTTPException(status_code=413, detail="Cuota de almacenamiento agotada")

    # 2. El router delega el guardado físico en disco
    ruta = await guardar_archivo_en_disco(usuario_actual.id, file)
    
    # 3. Guarda en base de datos y responde al cliente
    ...
