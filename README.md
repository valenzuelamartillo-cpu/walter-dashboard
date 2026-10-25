# Panel de Walter

Un panel en una sola página con: mensajes (notas que se guardan en `mensajes.json`), alertas del clima (NWS Broward/Miami-Dade/Palm Beach) y de última hora, rutas en Florida (tráfico FL511 en I-95, I-595, Turnpike, US-1, I-75 y vuelos de FLL: llegadas, salidas, demoras FAA y aviones aterrizando ahora), noticias internacionales (Fox, CNN, ABC, Univision; economía primero), aeropuerto FLL, barcos y Port Everglades, eventos en Fort Lauderdale y en Florida, noticias de Florida y principales, noticias nacionales (EE.UU.), noticias del mundo (Fox, CNN, ABC, Univision), noticias internacionales por tema (Casa Blanca, Donald Trump, Europa, China, Japón, Asia, Rusia), alertas económicas y noticias de Ecuador/Guayaquil (al final).

Nota: el conteo de aviones es un estimado con datos ADS-B de OpenSky. El conteo de barcos en vivo no está disponible gratis (las fuentes AIS piden clave); se muestran los cruceros programados y un enlace al mapa AIS.
Solo necesitas Python 3, sin instalar nada más y sin iniciar sesión. Se actualiza solo cada 5 minutos.

## Windows
1. Instala Python 3 desde https://www.python.org/downloads/ (marca "Add Python to PATH").
2. Descomprime `walter-dashboard.zip`, abre la carpeta, escribe `cmd` en la barra de dirección y pulsa Enter.
3. Ejecuta: `python app.py`
4. Abre en el navegador: http://localhost:8000

## Mac
1. Abre Terminal y entra a la carpeta: `cd ~/Downloads/walter-dashboard`
2. Ejecuta: `python3 app.py`
3. Abre: http://localhost:8000

## Android (Termux)
1. Instala Termux desde F-Droid.
2. En Termux: `pkg install python` y luego `termux-setup-storage`
3. `cd ~/storage/downloads/walter-dashboard` (después de descomprimir el zip ahí)
4. `python app.py`
5. Abre en Chrome: http://localhost:8000

Para cerrar: Ctrl+C. Datos en JSON: http://localhost:8000/api/data (agrega `?refresh=1` para forzar la actualización).

## Personalizar
- Alertas: edita la lista `ALERT_RULES` en `app.py` (nombre, palabras clave, nivel).
- Temas internacionales: diccionario `INTL` en `app.py`.
- Mensajes: se guardan en `mensajes.json` en la misma carpeta.
- Fuentes: diccionarios `NEWS` y `ECUADOR` en `app.py`.
- Si una fuente falla, esa sección muestra un aviso ⚠️ y el resto sigue funcionando.

## Menú principal
Al abrir, verás un menú con botones del 1 al 9 (1 Clima, 2 Barcos y puerto, 3 Vuelos y Aeropuerto FLL, 4 Tráfico, 5 Alertas, 6 Alertas económicas, 7 Eventos, 8 Noticias, 9 Ecuador / Guayaquil) y un enlace a Mensajes. Cada sección tiene el botón "⬅️ Menú". Para cambiar el orden, edita la lista `MENU` en `index.html`.

## Publicar en Render (opcional)
El proyecto incluye `render.yaml` y `requirements.txt` (vacío). En Render: New → Blueprint (o Web Service) con este repositorio; comando de inicio `python app.py`. La app usa la variable `PORT` automáticamente. Ojo: Mensajes queda visible para cualquiera con el enlace.
