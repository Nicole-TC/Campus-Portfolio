@router.post("", status_code=201)
async def subir_archivo(
    archivo: UploadFile = File(...),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not archivo.filename:
        raise HTTPException(
            status_code=400,
            detail="El archivo debe tener un nombre",
        )

    # Sacar la extensión del archivo
    extension_nombre = Path(archivo.filename).suffix.lower().lstrip(".")

    if not extension_nombre:
        raise HTTPException(
            status_code=400,
            detail="El archivo no tiene una extensión válida",
        )

    # Revisar si la extensión está permitida
    permitidas = {
        extension.lower().lstrip(".")
        for extension in extensiones_permitidas(usuario, db)
    }

    if extension_nombre not in permitidas:
        raise HTTPException(
            status_code=400,
            detail="Tipo de archivo no permitido",
        )

    # Buscar la extensión en la BD
    extension = db.scalar(
        select(Extension).where(
            Extension.nombre == extension_nombre
        )
    )

    if extension is None:
        raise HTTPException(
            status_code=400,
            detail="La extensión no está registrada en el sistema",
        )

    # Leer el archivo y obtener el tamaño
    contenido = await archivo.read()
    tamano_bytes = len(contenido)

    # Obtener cuota y tamaño máximo
    cuota_mb, max_archivo_mb = cuota_y_limite_mb(usuario)

    cuota_bytes = cuota_mb * BYTES_POR_MB
    max_archivo_bytes = max_archivo_mb * BYTES_POR_MB

    # Validar tamaño máximo
    if tamano_bytes > max_archivo_bytes:
        raise HTTPException(
            status_code=413,
            detail="El archivo supera el tamaño máximo permitido",
        )

    # Validar cuota disponible
    usado = bytes_usados(usuario.id, db)

    if usado + tamano_bytes > cuota_bytes:
        raise HTTPException(
            status_code=413,
            detail="No hay suficiente espacio disponible",
        )

    # Carpeta donde se guardan los archivos del usuario
    carpeta_usuario = Path("/storage/users") / str(usuario.id)
    carpeta_usuario.mkdir(parents=True, exist_ok=True)

    # Nombre seguro para guardar en disco
    nombre_disco = uuid4().hex

    ruta_archivo = carpeta_usuario / nombre_disco

    # Guardar archivo en disco
    ruta_archivo.write_bytes(contenido)

    # Guardar datos del archivo en la BD
    nuevo_archivo = Archivo(
        usuario_id=usuario.id,
        carpeta_id=None,
        id_extension=extension.id,
        nombre_disco=nombre_disco,
        nombre_original=archivo.filename,
        ruta=str(ruta_archivo),
        tamano_bytes=tamano_bytes,
        en_papelera=False,
    )

    db.add(nuevo_archivo)

    try:
        db.commit()
        db.refresh(nuevo_archivo)
    except Exception:
        db.rollback()

        if ruta_archivo.exists():
            ruta_archivo.unlink()

        raise

    return {
        "id": nuevo_archivo.id,
        "nombre": nuevo_archivo.nombre_original,
        "tamano_bytes": nuevo_archivo.tamano_bytes,
        "mensaje": "Archivo subido correctamente",
    }