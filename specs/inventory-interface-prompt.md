# Interfaz de inventario

Ya creamos la base de datos, lógica, y todo lo necesario para crear un stock de la compañía, ahora necesito crear la interfaz dentro del backoffice.

# Tarea

## Objetivo:
    - Crear un módulo(`uis/backoffice/lib/inventory.ts`) que centralice las llamadas a los endpoints /inventory.
    - todas las llamadas necesitarán autorización. deben incluir la cabecera Authorization: Bearer <token>.
    - gestiona errores que devuelva la API de forma explicita
## Modulo inventory.ts
    - Centraliza las llamadas a los endpoints /inventory.

## Estructura de la interfaz
Crear una nueva herramienta dentro de `uis/backoffice` con 4 páginas:
    - una página principal donde se muestre el stock(`/backoffice/inventory/products`)
    - una página de formulario de entrada (`/backoffice/inventory/orders/inbound`)
    - una páginade formulario de salida (`backoffice/inventory/orders/outboun`)
    - una página de historial de entradas y salidas (`uis/backoffice/inventory/orders`)

### Página principal (`/backoffice/inventory/products`):
    - lista todos los articulos del inventario, con la cantidad en stock, y demás datos del modelo
    - diferenciar cantidades entre suficiente y poco. Usa colorografía para contrastar 
    - incluye un botón en cada articulo que lleve al formulario de entrada

### Formulario de entrada (`/backoffice/inventory/orders/inbound`):
    - El formulario debe usar el endpoint `POST/inventory/orders/inbound`
    - debe estar protegido. Cualquier usuario no autenticado debe ser redirigido a la página del login
    - al oprimir el boton submit
        - enviar los datos al endpoint, utilizando los servicios de `uis/backoffice/lib/inventory.ts`
        - el formulario de limpia.
        -se indica que se completó con éxito.
        - Cualquier error debe ser indicado con un mensaje entendible, no con un error de consola.
    
### Formulario de Salida (`backoffice/inventory/orders/outboun`):
    - el formulario debe trabajarse con `POST/inventory/ordes/outbound`
    - Solo se puede completar el formulario si la cantidad introducida en la salida es menor al número de productos en stock. De lo contrario, bloquea el botón de submit, e indica al usuario debajo de la cantidad
    - al oprimir el boton submit
        - enviar los datos al endpoint, utilizando los servicios de `uis/backoffice/lib/inventory.ts`
        - el formulario de limpia.
        -se indica que se completó con éxito.
        - Cualquier error debe ser indicado con un mensaje entendible, no con un error de consola.

### Historial de entrada y salida (`uis/backoffice/inventory/orders`):
    - muestra datos como: que usuario lo creó, cuando, que tipo fue( entrada o salida), que producto fue, y que cantidad entró o salió
    - En esta página agrega todas las entradas y salidas registradas, y ordenalas de más reciente a más antigua.
    - diferencia visualmente las salidas de las entradas
    - arriba del historial, coloca una barra de filtrado por tiempo. Coloca también, una opción para mostrar solo las entradas o solo las salidas
    - esta página es solo de lectura, no puede editarse

### Protección de la interfaz
    - Todas las páginas de la interfaz, deben estar bloqueadas para usuario no autenticados. Si no está autenticado, enviarla a la página del login