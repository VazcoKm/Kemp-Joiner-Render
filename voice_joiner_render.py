# language: Python 3.10+, file: voice_joiner_render.py, target: Render + Discord Gateway v10
# pip install aiohttp
#
# variables de entorno en Render:
#   GUILD_ID        = id del servidor
#   GROUP_1_TOKENS  = token1\ntoken2\ntoken3
#   GROUP_1_CHANNEL = id del canal grupo 1
#   GROUP_2_TOKENS  = token4\ntoken5
#   GROUP_2_CHANNEL = id del canal grupo 2
#   (puedes agregar GROUP_3, GROUP_4, etc.)

import asyncio, json, os, random, time
from datetime import datetime
from aiohttp import web
import aiohttp

GATEWAY = "wss://gateway.discord.gg/?v=10&encoding=json"
WS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin": "https://discord.com"
}
IDENTIFY_TEMPLATE = {
    "op": 2,
    "d": {
        "token": None,
        "capabilities": 16381,
        "properties": {
            "os": "Windows", "browser": "Chrome", "device": "",
            "system_locale": "en-US",
            "browser_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "browser_version": "120.0.0.0", "os_version": "10",
            "referrer": "", "referring_domain": "",
            "referrer_current": "", "referring_domain_current": "",
            "release_channel": "stable", "client_build_number": 260805,
            "client_event_source": None
        },
        "presence": {"status": "online", "since": 0, "activities": [], "afk": False},
        "compress": False,
        "client_state": {"guild_versions": {}}
    }
}

_connected = []

def ts():
    return datetime.now().strftime("%H:%M:%S")

def log(msg, sym="+"):
    print(f"[{ts()}] {sym} {msg}", flush=True)

# ─── health endpoint ──────────────────────────────────────────────────────────

async def health(request):
    lines = [f"{c['user']} → CH:{c['channel_id']}" for c in _connected]
    body  = f"connected: {len(_connected)}\n" + "\n".join(lines)
    return web.Response(text=body)

async def start_health_server():
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    await web.TCPSite(runner, "0.0.0.0", port).start()
    log(f"Health server en puerto {port}", "→")

# ─── gateway ─────────────────────────────────────────────────────────────────

async def heartbeat_loop(ws, interval_ms):
    try:
        while True:
            # jitter ±500ms para no parecer bot
            jitter = random.uniform(-0.5, 0.5)
            await asyncio.sleep((interval_ms / 1000) + jitter)
            if ws.closed: break
            await ws.send_str(json.dumps({"op": 1, "d": None}))
    except asyncio.CancelledError:
        pass
    except Exception:
        pass

# builds cercanos al real para variar por token
BUILD_NUMBERS = [330490, 330491, 330492, 330493, 330494, 330495,
                 330500, 330501, 330502, 330503, 330504, 330505, 330510]
CAPABILITIES  = [16381, 16383, 16389, 16397, 16413, 16445, 16509]

async def run_token(token, guild_id, channel_id, idx, group):
    # delay escalonado pequeño — max 3s entre tokens
    await asyncio.sleep(random.uniform(0.5, 3) * (idx % 5))

    # cada token tiene su propio ciclo independiente
    session_duration = random.uniform(7200, 18000)
    rest_duration    = random.uniform(2700, 5400)

    while True:
        # ── sesión activa ────────────────────────────────────────────
        log(f"[G{group}] Token {idx+1} iniciando sesión...", "+")
        session      = aiohttp.ClientSession()
        hb_task      = None
        entry        = None
        session_start = time.time()  # resetear al inicio de cada sesión
        in_vc   = False          # True cuando está confirmado en el canal
        kicked  = asyncio.Event()  # se dispara cuando alguien lo saca

        try:
            ws = await session.ws_connect(GATEWAY, headers=WS_HEADERS, heartbeat=None)
        except Exception as e:
            log(f"[G{group}] Token {idx+1} WS failed: {e} — reintentando en 5s", "✗")
            await session.close()
            await asyncio.sleep(5)
            continue

        async def rejoin_watch():
            """Espera a que lo saquen del VC y lo mete de vuelta al instante."""
            while True:
                await kicked.wait()
                kicked.clear()
                if ws.closed: break
                log(f"[G{group}] {entry['user'] if entry else idx+1} — sacado del VC, reingresando...", "!")
                try:
                    await ws.send_str(json.dumps({"op": 4, "d": {
                        "guild_id":   str(guild_id),
                        "channel_id": str(channel_id),
                        "self_mute":  True,
                        "self_deaf":  True
                    }}))
                    log(f"[G{group}] {entry['user'] if entry else idx+1} — reingresó al VC ✓", "✓")
                except Exception as e:
                    log(f"[G{group}] Token {idx+1} rejoin error: {e}", "✗")
                    break

        rejoin_task = asyncio.create_task(rejoin_watch())

        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    op   = data.get("op")
                    t    = data.get("t")
                    d    = data.get("d") or {}

                    if op == 10:
                        hb_task = asyncio.create_task(heartbeat_loop(ws, d["heartbeat_interval"]))
                        identify = json.loads(json.dumps(IDENTIFY_TEMPLATE))
                        identify["d"]["token"] = token
                        identify["d"]["capabilities"] = CAPABILITIES[idx % len(CAPABILITIES)]
                        identify["d"]["properties"]["client_build_number"] = BUILD_NUMBERS[idx % len(BUILD_NUMBERS)]
                        log(f"[G{group}] Token {idx+1} identificando...", "~")

                        # ── status + actividad aleatorios ──────────────────
                        chosen = random.choice(["vr", "vr", "vr", "idle", "dnd"])

                        VR_HEADSETS = [
                            "Meta Quest 3",
                            "Meta Quest 2",
                            "Meta Quest Pro",
                            "Valve Index",
                            "PlayStation VR2",
                            "Apple Vision Pro",
                            "HTC Vive Pro 2",
                            "Oculus Rift S",
                            "Pico 4",
                        ]
                        if chosen == "vr":
                            headset = random.choice(VR_HEADSETS)
                            # payload exacto del PlatformSpoof plugin (k1ng0p/PlatformSpoof)
                            identify["d"]["properties"]["os"]              = "Android"
                            identify["d"]["properties"]["browser"]         = "Discord VR"
                            identify["d"]["properties"]["device"]          = headset
                            identify["d"]["properties"]["browser_version"] = ""
                            identify["d"]["properties"]["os_version"]      = ""
                            identify["d"]["presence"] = {
                                "status":     "online",
                                "since":      0,
                                "afk":        False,
                                "activities": []
                            }
                            status_label = f"VR ({headset})"
                        else:
                            identify["d"]["properties"]["os"]      = "Windows"
                            identify["d"]["properties"]["browser"] = "Discord Client"
                            identify["d"]["properties"]["device"]  = ""
                            identify["d"]["presence"] = {
                                "status":     chosen,
                                "since":      int(__import__("time").time() * 1000) if chosen == "idle" else 0,
                                "afk":        chosen == "idle",
                                "activities": []
                            }
                            status_label = chosen
                        await ws.send_str(json.dumps(identify))

                    elif op == 0 and t == "READY":
                        username = d.get("user", {}).get("username", "?")
                        user_id  = d.get("user", {}).get("id", "")
                        log(f"[G{group}] {username} READY, joining VC {channel_id} [{status_label}]...", "→")
                        await ws.send_str(json.dumps({"op": 4, "d": {
                            "guild_id":   str(guild_id),
                            "channel_id": str(channel_id),
                            "self_mute":  True,
                            "self_deaf":  True
                        }}))
                        entry = {"user": username, "user_id": user_id, "channel_id": channel_id, "group": group}
                        _connected.append(entry)
                        in_vc = True
                        log(f"[G{group}] {username} joined VC ✓ [{status_label}]", "✓")

                        # cambio de status ocasional cada 1-3 horas — permanece en VC
                        async def status_rotation(ws_ref, current_status):
                            await asyncio.sleep(random.uniform(3600, 10800))
                            while True:
                                if ws_ref.closed: break
                                new_st = random.choice(["idle", "dnd", "online"])
                                try:
                                    await ws_ref.send_str(json.dumps({
                                        "op": 3,
                                        "d": {
                                            "since":      int(time.time() * 1000) if new_st == "idle" else 0,
                                            "activities": [],
                                            "status":     new_st,
                                            "afk":        new_st == "idle"
                                        }
                                    }))
                                    log(f"[G{group}] {username} status → {new_st}", "→")
                                except: break
                                await asyncio.sleep(random.uniform(3600, 10800))

                        asyncio.create_task(status_rotation(ws, chosen))

                    elif op == 0 and t == "VOICE_STATE_UPDATE":
                        # detectar si nos sacaron del VC
                        uid     = d.get("user_id", "")
                        ch      = d.get("channel_id")
                        my_uid  = entry["user_id"] if entry else ""

                        if uid == my_uid and in_vc:
                            if ch is None:
                                # canal_id = None → alguien los sacó
                                log(f"[G{group}] {entry['user']} — detectado fuera del VC", "!")
                                kicked.set()
                            elif str(ch) != str(channel_id):
                                # los movieron a otro canal — volver al original
                                log(f"[G{group}] {entry['user']} — movido a otro canal, regresando...", "!")
                                kicked.set()

                    elif op == 9:
                        log(f"[G{group}] Token {idx+1} invalid session", "✗"); break
                    elif op == 7:
                        log(f"[G{group}] Token {idx+1} reconnect", "!"); break

                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    break

        except asyncio.CancelledError:
            rejoin_task.cancel()
            return
        except Exception as e:
            log(f"[G{group}] Token {idx+1} {type(e).__name__}: {e}", "✗")
        finally:
            rejoin_task.cancel()
            if hb_task: hb_task.cancel()
            if entry and entry in _connected:
                _connected.remove(entry)
            try: await ws.close()
            except: pass
            await session.close()

        # ── descanso solo si estuvo activo más de 2 horas ────────────
        tiempo_activo = time.time() - session_start

        if tiempo_activo >= 7200:   # 2+ horas → descansar
            rest_base   = random.uniform(2700, 5400)    # 45-90 min
            rest_offset = (idx % 5) * random.uniform(300, 600)  # offset por token
            rest_total  = rest_base + rest_offset
            log(f"[G{group}] Token {idx+1} — {entry['user'] if entry else ''} descansando {rest_total/60:.0f} min...", "!")
            await asyncio.sleep(rest_total)
            log(f"[G{group}] Token {idx+1} volviendo al VC...", "+")
            await asyncio.sleep(random.uniform(1, 5))
        else:
            # sesión corta — reconexión rápida sin descanso
            await asyncio.sleep(random.uniform(1, 5))

# ─── main ────────────────────────────────────────────────────────────────────

async def main():
    guild_id = os.environ.get("GUILD_ID", "")
    if not guild_id:
        log("Falta GUILD_ID", "✗"); return

    # leer grupos dinámicamente: GROUP_1, GROUP_2, GROUP_3...
    groups = []
    i = 1
    while True:
        raw_tokens = os.environ.get(f"GROUP_{i}_TOKENS", "")
        channel_id = os.environ.get(f"GROUP_{i}_CHANNEL", "")
        if not raw_tokens or not channel_id:
            break
        tokens = [t.strip() for t in raw_tokens.replace("\\n", "\n").split("\n") if t.strip()]
        groups.append({"tokens": tokens, "channel_id": channel_id, "num": i})
        log(f"Grupo {i}: {len(tokens)} tokens → canal {channel_id}", "+")
        i += 1

    # fallback: variables viejas TOKENS / CHANNEL_ID para compatibilidad
    if not groups:
        raw_tokens = os.environ.get("TOKENS", "")
        channel_id = os.environ.get("CHANNEL_ID", "")
        if raw_tokens and channel_id:
            tokens = [t.strip() for t in raw_tokens.replace("\\n", "\n").split("\n") if t.strip()]
            groups.append({"tokens": tokens, "channel_id": channel_id, "num": 1})
            log(f"Grupo 1 (legacy): {len(tokens)} tokens → canal {channel_id}", "+")

    if not groups:
        log("No hay grupos configurados. Agrega GROUP_1_TOKENS y GROUP_1_CHANNEL", "✗")
        return

    await start_health_server()

    tasks = []
    for g in groups:
        for idx, token in enumerate(g["tokens"]):
            tasks.append(asyncio.create_task(
                run_token(token, guild_id, g["channel_id"], idx, g["num"])
            ))

    log(f"Total tokens: {sum(len(g['tokens']) for g in groups)} en {len(groups)} grupo(s)", "→")
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
