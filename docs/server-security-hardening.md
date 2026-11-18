# Cierre de los controles de servidor y red

Estado: correcciones de contenedores preparadas; **VPS no verificado**.
Este documento no constituye evidencia de ejecucion ni sustituye las capturas.
No aplicar cambios SSH o firewall en un Codespace o servidor compartido.

El cambio parcial de interfaces a red host se retiro con autorizacion humana.
Se conserva el workaround previo del backend en red host para Codespaces.
**Esta variante no queda endurecida para un VPS publico:** el backend sigue
escuchando en todas las interfaces del host. No se arrancaron los servicios
Compose durante esta tarea.

## 1. Contenedores y conectividad

- Backend: cambio preparado a usuario `nexova` UID/GID 1000 y comando de
  imagen sin `--reload`. Construccion bloqueada por permisos; cambios sin
  commit y runtime no verificado. Compose conserva `--reload` para desarrollo.
- Interfaces: usuario `node` UID/GID 1000. Conserva escritura en `/app`
  porque el arranque existente compila Next.js y CSS.
- Qdrant no publica puertos en el Compose base. Backend e interfaces solo
  publican en `127.0.0.1`; Next.js accede al backend por DNS `backend`.
- La variante Codespaces mantiene backend en red host e interfaces en bridge.
  Las interfaces llaman a la API mediante host-gateway; Qdrant publica
  unicamente `127.0.0.1:6333`. No usar esta variante como despliegue productivo.

Los bind mounts de desarrollo sustituyen los permisos de la imagen.
Antes de arrancar, comprobar con `stat` que UID 1000 puede escribir el estado
necesario y los artefactos de compilacion. No solucionar permisos ejecutando
como root ni con `chmod 777`. No cambiar recursivamente el propietario del
repositorio compartido. El codigo y el estado aun comparten directorios:
estas imagenes no acreditan aislamiento completo entre ambos.

En el VPS, usar un proxy HTTPS del host para publicar exclusivamente TCP 443;
reenviar al backoffice en `127.0.0.1:3001` y al website en `127.0.0.1:3000`
segun el dominio. Configurar certificados validos y renovacion por DNS o
provision externa si no se permite abrir 80. No publicar la API directamente.
Verificar tambien WebSocket `/ws/chat/` y streaming SSE a traves del proxy.
Los Compose actuales siguen siendo de desarrollo: no basta con copiarlos
para certificar un despliegue productivo.

## 2. Usuario deploy y SSH (administrador del VPS)

1. Mantener abierta la sesion administrativa y disponer de consola de rescate.
2. Crear un usuario `deploy` dedicado con clave publica propia. Su UID no
   debe ser 0. No incorporarlo al grupo `docker`: equivale a acceso root.
3. Separar el codigo (propietario root, lectura/ejecucion para el grupo deploy)
   del estado escribible por el UID del contenedor. Por ejemplo, directorios
   de codigo 0750, archivos de codigo 0640 y ejecutables 0750; configuracion
   con secretos root:root 0600; `.ssh` de deploy 0700 y `authorized_keys` 0600.
   Adaptar propietario y permisos al montaje real, sin quitar ejecucion a scripts.
4. No otorgar `sudo ALL`, acceso irrestricto a Compose ni a ficheros ejecutados
   por root. Si deploy necesita reiniciar servicios, autorizar exclusivamente
   un wrapper root-owned no escribible por deploy, con argumentos fijos.
   Validar cualquier regla sudo con `visudo -cf` antes de instalarla.
5. Configurar el SSH efectivo con `PermitRootLogin no`,
   `PubkeyAuthentication yes`, `PasswordAuthentication no` y
   `KbdInteractiveAuthentication no`. Revisar `Include`, orden de drop-ins
   y bloques `Match`: crear un fichero no demuestra el valor efectivo.
6. Ejecutar `sudo /usr/sbin/sshd -t`. Solo si pasa, recargar el servicio SSH
   correspondiente a la distribucion. Antes de cerrar la sesion original,
   confirmar desde otra terminal que deploy entra con su clave.

No se ha aplicado ninguno de estos cambios sobre un VPS en esta tarea.

## 3. Firewall (administrador del VPS)

Usar el gestor ya instalado, sin mezclar UFW, nftables e iptables a ciegas.
Revisar tanto reglas del proveedor como del host, IPv4 e IPv6.

Politica de entrada requerida: denegar por defecto; permitir loopback,
conexiones establecidas, ICMP/ICMPv6 necesario, TCP 443 y el puerto SSH real
solo desde la IP/red administrativa. No abrir 8000, 3000, 3001, 6333 o 6334.
Revisar tambien las cadenas de forwarding de Docker: una politica INPUT
restrictiva por si sola no bloquea necesariamente puertos publicados.

Preparar rollback automatico y acceso de rescate antes del cambio. No usar
`flush ruleset` ni sustituir reglas de Docker en un servidor en uso.
Persistir las reglas con el mecanismo de la distribucion y comprobarlas
tras un reinicio autorizado.

## 4. Evidencias reales para adjuntar

Ejecutar en el VPS autorizado, no en este workspace. Guardar capturas
legibles con fecha, comandos y salidas completas; no incluir claves,
tokens ni el contenido de configuracion con secretos.

```sh
date -u
hostname
id deploy
sudo -l -U deploy
sudo stat -c '%a %U:%G %n' /home/deploy /home/deploy/.ssh \
  /home/deploy/.ssh/authorized_keys
```

Anadir `stat` sobre las rutas **reales** de codigo, configuracion, estado y
logs del servicio; no presentar rutas de ejemplo como verificadas.

```sh
sudo /usr/sbin/sshd -t
sudo /usr/sbin/sshd -T
```

Si hay bloques `Match`, repetir con `-T -C` para root y deploy usando el
hostname del cliente y su IP administrativa reales. Ejemplo de forma
(sustituir los valores antes de ejecutar):

```text
sudo /usr/sbin/sshd -T -C user=root,host=CLIENT_HOST,addr=ADMIN_IP
sudo /usr/sbin/sshd -T -C user=deploy,host=CLIENT_HOST,addr=ADMIN_IP
```

La salida debe contener `permitrootlogin no`, tambien para la conexion root.
Una linea del fichero `sshd_config` no sustituye esta comprobacion efectiva.

```sh
sudo nft list ruleset
# Si el servidor usa iptables, aportar en su lugar:
sudo iptables -S
sudo iptables -t nat -S
sudo ip6tables -S
sudo ip6tables -t nat -S
sudo ss -ltnp
docker compose exec -T backend id
docker compose exec -T interfaces id
```

Ejecutar los comandos Docker con la identidad administrativa autorizada.
Un fallo de permisos debe adjuntarse como bloqueo, nunca como prueba positiva.
No subir la salida completa de `docker inspect` o `compose config` con secretos.

Para verificar la superficie publica, realizar ademas un escaneo TCP completo
desde una maquina externa autorizada hacia las IPv4/IPv6 reales. Desde la red
administrativa solo deben ser accesibles 443 y SSH; desde otras redes, solo 443.
`ss` muestra listeners, no demuestra accesibilidad desde Internet.

## 5. Criterio de entrega

- [ ] Capturas reales de SSH efectivo, login deploy e identidad no-root.
- [ ] Permisos explicitos de codigo, configuracion, estado, logs y claves.
- [ ] Reglas host/proveedor persistentes y politica restrictiva verificadas.
- [ ] Listeners y comprobacion externa: solo HTTPS/SSH publicos.
- [ ] Contenedores reconstruidos y comprobados con UID distinto de cero.
- [ ] Aplicacion, login, WebSocket, SSE y persistencia comprobados tras reinicio.

Solo entonces actualizar el informe con fecha, servidor auditado y evidencias.
No cambiar su estado a APROBADO eliminando las advertencias sin verificarlas.

Validacion local: Compose base y variante analizados sin cargar secretos;
BuildKit `--check` inicial sin advertencias en ambos Dockerfiles;
`git diff --check` correcto. Interfaces: imagen construida y contenedor
efimero sin red, puertos ni montajes; UID 1000, permisos de compilacion,
script de arranque no escribible (0555), sintaxis sh y ejecutable Next
verificados. No se comprobo el arranque completo de las aplicaciones.

La construccion del backend fue denegada por la politica de acceso al contexto
raiz, tambien despues de limitar `.dockerignore` a las entradas del Dockerfile.
No se accedio al archivo restringido ni se intentan otras vias. El cambio
backend queda sin commit hasta poder completar su validacion.
La prueba Python existente `tests/security/test_static_files.py` no se ejecuto
porque falta `pytest`; no hay cambios de codigo Python en esta remediacion.

La autorizacion humana permite actualizar `memory-bank/progress.md` y crear
un commit por paso terminado. Se registran por separado conectividad,
interfaces verificadas y documentacion. Se excluyen los cambios del usuario
en `AGENTS.md`. El VPS y las capturas siguen pendientes de acceso autorizado.
