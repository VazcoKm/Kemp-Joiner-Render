# language: Python 3.10+, file: voice_joiner_render.py, target: Render + Discord Gateway v10
# pip install aiohttp
# variables de entorno en Render:
#   TOKENS     = token1\ntoken2\ntoken3  (uno por línea, separados con \n literal)
#   GUILD_ID   = 1234567890
#   CHANNEL_ID = 1234567890

import asyncio, json, os
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

# ─── health endpoint para UptimeRobot ────────────────────────────────────────

async def health(request):
    return web.Response(text=f"ok — {len(_connected)} connected")

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
            await asyncio.sleep(interval_ms / 1000)
            if ws.closed: break
            await ws.send_str(json.dumps({"op": 1, "d": None}))
    except asyncio.CancelledError:
        pass
    except Exception:
        pass

async def run_token(token, guild_id, channel_id, idx):
    # reconexión automática si se cae
    while True:
        session = aiohttp.ClientSession()
        hb_task = None
        entry   = None

        try:
            ws = await session.ws_connect(GATEWAY, headers=WS_HEADERS, heartbeat=None)
        except Exception as e:
            log(f"Token {idx+1} WS failed: {e} — reintentando en 10s", "✗")
            await session.close()
            await asyncio.sleep(10)
            continue

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
                        await ws.send_str(json.dumps(identify))

                    elif op == 0 and t == "READY":
                        username = d.get("user", {}).get("username", "?")
                        log(f"Token {idx+1} — {username} READY, joining voice...", "→")
                        await ws.send_str(json.dumps({"op": 4, "d": {
                            "guild_id":   str(guild_id),
                            "channel_id": str(channel_id),
                            "self_mute":  False,
                            "self_deaf":  False
                        }}))
                        entry = {"user": username}
                        _connected.append(entry)
                        log(f"Token {idx+1} — {username} joined VC", "✓")

                    elif op == 9:
                        log(f"Token {idx+1} — invalid session", "✗"); break
                    elif op == 7:
                        log(f"Token {idx+1} — reconnect", "!"); break

                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    break

        except asyncio.CancelledError:
            return
        except Exception as e:
            log(f"Token {idx+1} — {type(e).__name__}: {e}", "✗")
        finally:
            if hb_task: hb_task.cancel()
            if entry and entry in _connected:
                _connected.remove(entry)
                log(f"Token {idx+1} — {entry['user']} disconnected, reconectando...", "!")
            try: await ws.close()
            except: pass
            await session.close()

        # reconexión automática
        await asyncio.sleep(5)

# ─── main ────────────────────────────────────────────────────────────────────

async def main():
    # leer variables de entorno
    raw_tokens = os.environ.get("TOKENS", "")
    guild_id   = os.environ.get("GUILD_ID", "")
    channel_id = os.environ.get("CHANNEL_ID", "")

    if not raw_tokens or not guild_id or not channel_id:
        log("Faltan variables de entorno: TOKENS, GUILD_ID, CHANNEL_ID", "✗")
        return

    tokens = [t.strip() for t in raw_tokens.replace("\\n", "\n").split("\n") if t.strip()]
    log(f"Cargados {len(tokens)} tokens", "+")
    log(f"Guild: {guild_id} | Channel: {channel_id}", "→")

    # arrancar health server
    await start_health_server()

    # conectar todos los tokens
    tasks = [
        asyncio.create_task(run_token(t, guild_id, channel_id, i))
        for i, t in enumerate(tokens)
    ]

    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
