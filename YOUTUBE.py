import time
import json
import os
import urllib.parse

import feedparser
import requests
from openai import OpenAI
from youtube_transcript_api import YouTubeTranscriptApi

# ==========================
# CONFIGURACIÓN GENERAL
# ==========================
CONFIG = {
    # Lista de canales a vigilar (RSS de YouTube)
    "feeds": [
        {
            "name": "Trading Dominion",  # Nombre que aparecerá en el email
            "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCmJL2llHf2tEcDAjaz-LFgQ",
        },
        # Añade aquí más canales si quieres:
        # {
        #     "name": "Otro canal",
        #     "url": "https://www.youtube.com/feeds/videos.xml?channel_id=XXXXXXXXXXXXXXX",
        # },
    ],

    # Cada cuánto comprobar nuevos vídeos (en segundos)
    "poll_interval_seconds": 900,  # 15 minutos

    # Fichero donde se guardan los IDs de vídeos ya procesados
    "state_file": "processed_videos.json",

    # Config OpenAI (resumen)
    "openai": {
        # Mejor usar variable de entorno: os.environ.get("OPENAI_API_KEY")
        "api_key": os.environ.get("OPENAI_API_KEY", "PON_AQUI_TU_API_KEY"),
        "model": "gpt-4o-mini",    # o gpt-4-turbo, según tu presupuesto
        "language": "es",          # idioma del resumen
        "max_chars": 8000,         # recorte máximo de texto a enviar al modelo
    },

    # Configuración de Telegram
    "telegram": {
        # Token del bot (obtenerlo de @BotFather)
        "bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", "PON_AQUI_TU_BOT_TOKEN"),
        # Tu chat ID (puedes obtenerlo con @userinfobot)
        "chat_id": os.environ.get("TELEGRAM_CHAT_ID", "PON_AQUI_TU_CHAT_ID"),
        # Límite de caracteres por mensaje de Telegram
        "max_message_length": 4096,
    },
}


# ==========================
# FUNCIONES AUXILIARES
# ==========================

def load_state(path):
    """Carga el conjunto de IDs de vídeos ya procesados."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            ids = data.get("processed_video_ids", [])
            return set(ids)
    except FileNotFoundError:
        return set()
    except Exception as e:
        print(f"[WARN] No se pudo leer el fichero de estado ({e}). Se reinicia desde cero.")
        return set()


def save_state(path, processed_ids):
    """Guarda el conjunto de IDs procesados en disco."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {"processed_video_ids": sorted(list(processed_ids))},
                f,
                ensure_ascii=False,
                indent=2,
            )
    except Exception as e:
        print(f"[WARN] No se pudo guardar el estado: {e}")


def extract_video_id(entry):
    """Intenta extraer el ID del vídeo desde una entrada RSS de YouTube."""
    # 1) Campo específico de YouTube si existe
    if hasattr(entry, "yt_videoid"):
        return entry.yt_videoid

    # 2) Del campo id con formato yt:video:VIDEOID
    if hasattr(entry, "id") and isinstance(entry.id, str) and entry.id.startswith("yt:video:"):
        return entry.id.split(":")[-1]

    # 3) Como última opción, desde la URL (watch?v=VIDEOID)
    if hasattr(entry, "link"):
        try:
            parsed = urllib.parse.urlparse(entry.link)
            qs = urllib.parse.parse_qs(parsed.query)
            vid = qs.get("v", [None])[0]
            if vid:
                return vid
        except Exception:
            pass

    return None


def fetch_new_videos(feed_cfg, processed_ids):
    """Lee un feed RSS y devuelve la lista de vídeos nuevos (no procesados)."""
    print(f"[INFO] Comprobando feed: {feed_cfg['name']}...")
    try:
        feed = feedparser.parse(feed_cfg["url"])
    except Exception as e:
        print(f"[ERROR] Fallo al leer RSS de {feed_cfg['name']}: {e}")
        return []

    new_videos = []
    for entry in getattr(feed, "entries", []):
        video_id = extract_video_id(entry)
        if not video_id:
            continue
        if video_id in processed_ids:
            continue

        title = getattr(entry, "title", "(sin título)")
        link = getattr(entry, "link", "")
        published = getattr(entry, "published", "")
        description = getattr(entry, "summary", None) or getattr(entry, "media_description", None)

        new_videos.append(
            {
                "id": video_id,
                "title": title,
                "link": link,
                "published": published,
                "description": description,
                "channel": feed_cfg["name"],
            }
        )

    if new_videos:
        print(f"[INFO] Encontrados {len(new_videos)} vídeo(s) nuevo(s) en {feed_cfg['name']}.")
    return new_videos


def get_transcript_text(video_id, preferred_languages=None, ytt_api=None, max_chars=None):
    """Intenta obtener la transcripción del vídeo (subtítulos) y la devuelve como texto plano."""
    if preferred_languages is None:
        preferred_languages = ["es", "en"]
    if ytt_api is None:
        ytt_api = YouTubeTranscriptApi()

    try:
        fetched = ytt_api.fetch(video_id, languages=preferred_languages)
        text_parts = [snippet.text for snippet in fetched]
        full_text = " ".join(text_parts)
        if max_chars is not None and len(full_text) > max_chars:
            return full_text[:max_chars]
        return full_text
    except Exception as e:
        print(f"[WARN] No se pudo obtener transcripción para {video_id}: {e}")
        return None


def build_summary(client, cfg_openai, video, transcript_text):
    """Llama al modelo de OpenAI para generar un resumen estructurado."""
    language = cfg_openai.get("language", "es")
    model = cfg_openai["model"]

    if transcript_text:
        base_text = transcript_text
        source_info = "transcripción del vídeo"
    else:
        base_text = video.get("description") or ""
        source_info = "descripción del vídeo (no hay transcripción disponible)"

    # Si no hay nada que resumir, salimos con mensaje informativo
    if not base_text:
        return (
            "No se pudo generar un resumen porque el vídeo no tiene transcripción ni descripción accesible.\n\n"
            f"Título: {video['title']}\nEnlace: {video['link']}"
        )

    max_chars = cfg_openai.get("max_chars") or len(base_text)
    base_text = base_text[:max_chars]

    prompt_user = f"""
Analiza este vídeo de YouTube y genera un RESUMEN EJECUTIVO sin paja.

📹 VÍDEO: {video['title']}
📢 CANAL: {video['channel']}
📅 FECHA: {video.get('published','')}

CONTENIDO ({source_info}):
\"\"\"{base_text}\"\"\"

INSTRUCCIONES ESTRICTAS:
- SOLO información de alto valor
- DATOS concretos, cifras, estadísticas
- CONCLUSIONES clave y aplicables
- INSIGHTS únicos o contraintuitivos
- SIN introducciones, SIN relleno, SIN obviedades

FORMATO REQUERIDO:

🎯 IDEA CENTRAL (1 frase máximo)
[la tesis principal del vídeo]

💡 PUNTOS CLAVE
• [dato/conclusión concreta 1]
• [dato/conclusión concreta 2]
• [dato/conclusión concreta 3]
[entre 3-7 bullets, cada uno debe aportar valor real]

📊 DATOS DE VALOR (si aplica)
• [cifras, estadísticas, números concretos]

⚠️ ADVERTENCIAS (si aplica)
• [sesgos, limitaciones, contraindicaciones]

🔑 ACCIÓN RECOMENDADA (1-2 frases)
[qué hacer con esta información]

Máximo 250 palabras. Idioma: {language}. Prioriza densidad de información sobre extensión.
"""

    response = client.chat.completions.create(
        model=model,
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": (
                    "Eres un analista experto que extrae SOLO información de alto valor. "
                    "Eliminas paja, relleno y obviedades. Priorizas datos concretos, "
                    "conclusiones accionables e insights únicos. Máxima densidad informativa."
                ),
            },
            {"role": "user", "content": prompt_user},
        ],
    )

    return response.choices[0].message.content.strip()


def send_telegram(telegram_cfg, message):
    """Envía un mensaje a Telegram usando la Bot API."""
    bot_token = telegram_cfg["bot_token"]
    chat_id = telegram_cfg["chat_id"]
    max_length = telegram_cfg.get("max_message_length", 4096)

    # Si el mensaje es muy largo, dividirlo en partes
    if len(message) > max_length:
        parts = []
        current_part = ""
        for line in message.split("\n"):
            if len(current_part) + len(line) + 1 <= max_length:
                current_part += line + "\n"
            else:
                if current_part:
                    parts.append(current_part)
                current_part = line + "\n"
        if current_part:
            parts.append(current_part)
    else:
        parts = [message]

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    try:
        for i, part in enumerate(parts):
            payload = {
                "chat_id": chat_id,
                "text": part,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            }
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()

            if len(parts) > 1:
                print(f"[INFO] Mensaje enviado a Telegram (parte {i+1}/{len(parts)}).")
            else:
                print("[INFO] Mensaje enviado a Telegram correctamente.")

            # Pequeña pausa entre mensajes si hay múltiples partes
            if i < len(parts) - 1:
                time.sleep(1)

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Error enviando mensaje a Telegram: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"[ERROR] Respuesta: {e.response.text}")


# ==========================
# BUCLE PRINCIPAL
# ==========================

def run_forever():
    cfg = CONFIG
    telegram_cfg = cfg["telegram"]
    openai_cfg = cfg["openai"]

    # Validaciones de configuración
    if not openai_cfg.get("api_key") or openai_cfg["api_key"] == "PON_AQUI_TU_API_KEY":
        raise RuntimeError("Configura tu API key de OpenAI en CONFIG['openai']['api_key'] o como variable de entorno OPENAI_API_KEY.")

    if not telegram_cfg.get("bot_token") or telegram_cfg["bot_token"] == "PON_AQUI_TU_BOT_TOKEN":
        raise RuntimeError("Configura tu bot token de Telegram en CONFIG['telegram']['bot_token'] o como variable de entorno TELEGRAM_BOT_TOKEN.")

    if not telegram_cfg.get("chat_id") or telegram_cfg["chat_id"] == "PON_AQUI_TU_CHAT_ID":
        raise RuntimeError("Configura tu chat ID de Telegram en CONFIG['telegram']['chat_id'] o como variable de entorno TELEGRAM_CHAT_ID.")

    client = OpenAI(api_key=openai_cfg["api_key"])
    ytt_api = YouTubeTranscriptApi()

    processed_ids = load_state(cfg["state_file"])
    print(f"[INFO] IDs ya procesados: {len(processed_ids)}")

    while True:
        try:
            for feed_cfg in cfg["feeds"]:
                new_videos = fetch_new_videos(feed_cfg, processed_ids)
                for video in new_videos:
                    print(f"[INFO] Procesando vídeo: {video['title']} ({video['id']})")
                    transcript_text = get_transcript_text(
                        video["id"],
                        preferred_languages=["es", "en"],
                        ytt_api=ytt_api,
                        max_chars=openai_cfg.get("max_chars"),
                    )
                    summary = build_summary(client, openai_cfg, video, transcript_text)

                    # Formatear mensaje para Telegram con HTML básico
                    message = (
                        f"📺 <b>{video['channel']}</b>\n"
                        f"🎬 {video['title']}\n"
                        f"🔗 <a href=\"{video['link']}\">Ver vídeo</a>\n"
                        f"📅 {video.get('published','')}\n\n"
                        f"━━━━━━━━━━━━━━━━━━\n\n"
                        f"{summary}\n"
                    )

                    send_telegram(telegram_cfg, message)

                    # Marcamos el vídeo como procesado
                    processed_ids.add(video["id"])
                    save_state(cfg["state_file"], processed_ids)

        except Exception as e:
            print(f"[ERROR] Error general en el bucle principal: {e}")

        wait = cfg["poll_interval_seconds"]
        print(f"[INFO] Esperando {wait} segundos antes de la próxima comprobación...\n")
        time.sleep(wait)


if __name__ == "__main__":
    run_forever()
