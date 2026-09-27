#  Kemp Voice Token Joiner

Mantiene múltiples cuentas de Discord conectadas en canales de voz de forma continua.  
Corre en **Render** (free tier) y se mantiene vivo con **UptimeRobot**.

---

## ¿Qué hace?

- Conecta cada token al Gateway de Discord (v10) simulando un cliente real
- Entra automáticamente al canal de voz asignado (muted + deafened)
- Si alguien saca una cuenta del VC, **reingresa al instante**
- Rota status (`online`, `idle`, `dnd`) y spoofa algunos tokens como dispositivos VR (Meta Quest, Valve Index, etc.)
- Cada token tiene su propio ciclo de sesión independiente con descansos aleatorios para parecer humano
- Expone un endpoint `/` con el estado en tiempo real de todos los tokens conectados

---

## Requisitos

- Cuenta en [Render](https://render.com) (free tier alcanza)
- Cuenta en [UptimeRobot](https://uptimerobot.com) (free tier alcanza)
- Tokens de Discord (user tokens, no bots)
- Python 3.10+

**Dependencia única:**
```
aiohttp
```

---

## Deploy en Render

### 1. Sube el código a GitHub

Crea un repo y sube `voice_joiner_render.py` + un archivo `requirements.txt`:

```
aiohttp
```

### 2. Crea el servicio en Render

1. Ve a [render.com](https://render.com) → **New** → **Web Service**
2. Conecta tu repo de GitHub
3. Configura así:

| Campo | Valor |
|---|---|
| **Environment** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `python voice_joiner_render.py` |
| **Instance Type** | Free |

### 3. Agrega las variables de entorno

En Render → tu servicio → **Environment** → agrega estas variables:

#### Variable obligatoria

| Variable | Descripción | Ejemplo |
|---|---|---|
| `GUILD_ID` | ID del servidor de Discord | `123456789012345678` |

#### Por cada grupo de tokens

Puedes tener tantos grupos como quieras. Cada grupo apunta a un canal de voz distinto.

| Variable | Descripción | Ejemplo |
|---|---|---|
| `GROUP_1_TOKENS` | Tokens del grupo 1, uno por línea | `token1`↵`token2`↵`token3` |
| `GROUP_1_CHANNEL` | ID del canal de voz para el grupo 1 | `987654321098765432` |
| `GROUP_2_TOKENS` | Tokens del grupo 2 | `token4`↵`token5` |
| `GROUP_2_CHANNEL` | ID del canal de voz para el grupo 2 | `111222333444555666` |

> Puedes agregar `GROUP_3`, `GROUP_4`, etc. sin límite.

#### ¿Cómo poner múltiples tokens en una variable?

En Render, en el campo de valor, presiona **Shift+Enter** para hacer salto de línea dentro del mismo campo. Cada token va en su propia línea:

```
MiToken1AquiCompleto
MiToken2AquiCompleto
MiToken3AquiCompleto
```

### 4. Deploy

Render desplegará automáticamente. En los logs vas a ver algo así:

```
[12:00:01] + Grupo 1: 3 tokens → canal 987654321098765432
[12:00:01] + Grupo 2: 2 tokens → canal 111222333444555666
[12:00:01] → Health server en puerto 8080
[12:00:03] + [G1] Token 1 iniciando sesión...
[12:00:04] → [G1] Username1 READY, joining VC... [VR (Meta Quest 3)]
[12:00:04] ✓ [G1] Username1 joined VC ✓
```

---

## Configurar UptimeRobot (mantener vivo en Render free)

Render free suspende el servicio después de 15 minutos sin tráfico. UptimeRobot lo previene pingueando cada 5 minutos.

1. Ve a [uptimerobot.com](https://uptimerobot.com) → **Add New Monitor**
2. Configura:

| Campo | Valor |
|---|---|
| **Monitor Type** | `HTTP(s)` |
| **Friendly Name** | `Voice Joiner` (o lo que quieras) |
| **URL** | La URL de tu servicio en Render (ej: `https://tu-servicio.onrender.com`) |
| **Monitoring Interval** | `5 minutes` |

3. Guarda. UptimeRobot va a mantener el servicio activo 24/7.

La URL raíz `/` responde con el estado actual:

```
connected: 5
Username1 → CH:987654321098765432
Username2 → CH:987654321098765432
Username3 → CH:111222333444555666
```

---

## Comportamiento de los tokens

| Característica | Detalle |
|---|---|
| **Spoof VR** | ~60% de los tokens aparecen como Meta Quest, Valve Index, PS VR2, etc. |
| **Status rotation** | Cambia entre `online`, `idle`, `dnd` cada 1–3 horas |
| **Sesiones** | 2–5 horas activo, luego 45–90 min de descanso (solo si estuvo 2h+) |
| **Reconexión** | Automática si el WS cae o lo sacan del VC |
| **Delay escalonado** | Los tokens no entran todos al mismo tiempo |

---

## Compatibilidad con variables legacy

Si antes usabas `TOKENS` y `CHANNEL_ID` (sin grupos), el script las sigue leyendo como `GROUP_1` automáticamente. No necesitas cambiar nada.

---
- Los tokens deben ser **user tokens** (los de cuentas normales, no bots de la Developer Portal)
- Para obtener tu `GUILD_ID` y `CHANNEL_ID`: activa **Modo Desarrollador** en Discord (Ajustes → Avanzado) y haz clic derecho en el servidor/canal → *Copiar ID*
- El servicio escucha en el puerto que Render asigne vía la variable `PORT` (automático)
