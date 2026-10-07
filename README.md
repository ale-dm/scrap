# cableworld-epg

Lee la parrilla de <https://hlsnov.cableworld.es/> (Cableworld Crevillent) y genera un XMLTV para Dispatcharr. Solo librería estándar de Python 3.9+.

## Uso rápido

```bash
python cableworld_epg.py -o epg.xml
```

## Docker (recomendado, junto a Dispatcharr)

```bash
docker compose up -d --build
```

Regenera el XML cada 6 h y lo sirve en `http://<host>:8099/epg.xml`. Si la web falla, conserva el último XML válido.

## Dispatcharr

1. **EPG → Add EPG**: tipo *XMLTV*, URL `http://cableworld-epg:8080/epg.xml` (misma red Docker) o `http://<ip-servidor>:8099/epg.xml`.
2. En el canal, asigna ese EPG. Si el `tvg-id` del m3u coincide con `CHANNEL_ID`, se enlaza solo; si no, cámbialo en `docker-compose.yml` o asígnalo a mano.

## Notas

- La web solo da la hora de inicio: el fin de cada programa es el inicio del siguiente. El último dura `LAST_MINUTES` (60 por defecto).
- La parrilla cubre ~2 días, por eso se refresca varias veces al día.
- Zona horaria `Europe/Madrid`.
- Tests: `python -m unittest discover -s tests`
