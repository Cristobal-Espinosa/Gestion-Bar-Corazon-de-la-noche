# Corazón de la noche — guía para conectar el frontend con Django + MySQL

## 0. Organización del proyecto

```
bar_django/
├── manage.py
├── config/            ← settings.py, urls.py (el "proyecto")
├── usuarios/          ← Usuario de Django con 2 apellidos
├── inventario/        ← Insumo, CategoriaInsumo, TipoMovimiento, MovimientoInventario,
│                         Compra, DetalleCompra  + páginas: inicio y stock
├── carta/             ← CategoriaCoctel, Coctel, RecetaCoctel + página: catálogo (+ lógica de disponibilidad)
├── ventas/            ← Venta, DetalleVenta + página: venta (se activa el sprint siguiente)
├── templates/         ← inventario/index.html, menu.html, venta.html, stock.html  +  404.html
└── static/            ← css/, js/, lib/, img/ (los del frontend)
```

Criterio: una app por "tema" del negocio, y las dependencias van en un solo sentido
(`usuarios` ← `inventario` ← `carta` ← `ventas`), así nunca hay referencias circulares.
`templates/` y `static/` están a nivel de proyecto para no tocar el HTML del frontend
(`render(request, "inventario/menu.html")` sigue funcionando tal cual).

## 1. Preparar MySQL

```sql
CREATE DATABASE bcdln CHARACTER SET utf8mb4;
CREATE USER 'bcdln_user'@'localhost' IDENTIFIED BY 'tu_clave';
GRANT ALL PRIVILEGES ON bcdln.* TO 'bcdln_user'@'localhost';
-- (para correr `manage.py test` además: GRANT ALL ON test_bcdln.* ...)
SELECT VERSION();   -- los CHECK se aplican desde MySQL 8.0.16 / MariaDB 10.2; antes se ignoran
```

## 2. Entorno y dependencias

```bash
cd bar_django
python -m venv venv
venv\Scripts\activate          # Windows   (Linux/Mac: source venv/bin/activate)
pip install -r requirements.txt
```
Si `mysqlclient` no instala en tu equipo: `pip install pymysql` y agrega al inicio de
`config/__init__.py`:  `import pymysql; pymysql.install_as_MySQLdb()`

## 3. Copiar el frontend

- `templates/inventario/`  ← index.html, menu.html, venta.html, stock.html
- `templates/404.html`      ← 404.html
- `static/`                 ← las carpetas css/, js/, lib/, img/

## 4. Configurar y migrar

1. En `config/settings.py` cambia `PASSWORD` (y `USER`/`NAME` si usaste otros).
2. **`AUTH_USER_MODEL` ya está definido: debe estar ANTES del primer `migrate`.**
   Si ya habías migrado con el usuario por defecto, borra y recrea la base `bcdln`.
3. Los archivos de migración ya vienen generados. Ejecuta:
```bash
python manage.py migrate
python manage.py createsuperuser     # pedirá usuario, correo, nombre, 1er y 2º apellido
python manage.py runserver
```
(Si cambias un modelo más adelante: `python manage.py makemigrations` y luego `migrate`.)

## 5. Cargar datos en el admin (http://127.0.0.1:8000/admin/)

Orden obligatorio (cada cosa depende de la anterior):
1. Categorías de insumo (Licores, Frutas…) → 2. **Insumos** (nombre, unidad, stock actual, stock mínimo)
3. Categorías de cóctel (Clásicos, Con espumante, Sin alcohol, De autor) →
4. **Cócteles** con su receta en la misma pantalla (tabla "Receta" al final).
La lista de cócteles muestra la columna "Disponible (según stock)".

Páginas: `/` inicio · `/carta/` carta · `/stock/` stock · `/venta/` (aviso de próximo sprint).

## 6. Restricciones: qué se pide, de qué tipo es y cómo se prueba

La clase distingue: **PK** (identifica, no se repite ni queda vacía), **FK** (apunta a una fila que
existe), **cardinalidad** (cuántos de cada lado) y **reglas del negocio** (lo que PK/FK/cardinalidad
no garantizan, p. ej. que no se crucen horarios). Aplicado a este modelo:

| Restricción | Tipo | Cómo se implementa | Éxito | Rechazo / dato inválido |
|---|---|---|---|---|
| Id de cada tabla | PK | `id` automático | — | — |
| Cóctel→categoría, receta→cóctel/insumo, etc. | FK (obligatoria) | `ForeignKey` (`PROTECT`) | Categoría existente | Borrar una categoría con cócteles |
| Receta: un insumo una vez por cóctel | PK compuesta del diagrama | `UniqueConstraint(coctel, insumo)` | Mismo insumo en otro cóctel | Repetir insumo en la misma receta |
| Nombre de cóctel / insumo (licor) único | regla de unicidad | `unique=True` | "Mojito" nuevo | Otro "Mojito" (o "mojito") |
| Precio ≥ 0 | regla de dominio | validador + `CheckConstraint` | 5500 · caso límite: 0 | -1 |
| Cantidad en receta > 0 | regla de dominio | validador + `CheckConstraint` | 60 | 0 y negativos |
| Stock actual / mínimo ≥ 0 | regla de dominio | validador + `CheckConstraint` | 500 · límite: 0 | -5 |
| Cóctel con ≥ 1 ingrediente | regla de negocio | `min_num` + `validate_min` en el admin | Receta con 1+ | Guardar sin ingredientes |
| Cantidad en compras/ventas > 0; costos y precios ≥ 0; total ≥ 0 | regla de dominio | igual que arriba | — | — |
| Apellidos | dato obligatorio | `apellido_2` obligatorio | Dos apellidos | Segundo apellido vacío |

Cada regla se aplica en **dos niveles**: el validador (mensaje amable en el admin) y la restricción
de la base (te protege aunque alguien use `shell` o SQL). `python manage.py test` ejecuta 14 pruebas
que cubren éxito, rechazo y caso límite de estas reglas.

## 7. Demo de disponibilidad (cómo mostrarlo)

La disponibilidad **no se guarda**: se calcula en cada visita de `/carta/` comparando el stock de cada
insumo con lo que pide la receta.
1. Carga datos de modo que haya cócteles disponibles y NO disponibles (un insumo con stock menor a lo que pide la receta).
2. En vivo: abre `/carta/` en una pestaña y el admin en otra; baja el stock de un insumo; refresca la carta y ese cóctel pasa a "no disponible" (y vuelve a subir al reponerlo).
3. Muestra un rechazo: crea un cóctel con precio -1 o repite un insumo en la receta.

Para no recargar todo en la sala:  `python manage.py dumpdata --indent 2 -o datos_demo.json`
y en otro equipo:  `python manage.py loaddata datos_demo.json` (las imágenes subidas se copian aparte, carpeta `media/`).

## 8. Pendiente / decisiones

- `Insumo.porcentaje` (barra de stock.html): el modelo no tiene capacidad de botella; por ahora "100 %" = 3 veces el stock mínimo (`FACTOR_NIVEL_LLENO` en inventario/models.py).
- `stock.html` espera la variable `licores`: se le pasan todos los insumos (también frutas). Si no quieren frutas, filtrar por categoría en `inventario/views.py`.
- Fotos: el campo `imagen` ya existe. En menu.html se puede usar `{{ c.obj.imagen.url }}` cuando `c.obj.imagen` tenga archivo.
- `MovimientoInventario.cantidad`: supuesto positivo suma / negativo resta (distinta de 0). Confirmar en el sprint de ajuste de stock.
