import time
import json
import os
import urllib.parse
import smtplib
from email.message import EmailMessage

import feedparser
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
        # Ojo: si puedes, mejor usar variable de entorno, pero tú decides:
        # os.environ.get("OPENAI_API_KEY") o ponerla directamente:
        "api_key": "PON_AQUI_TU_API_KEY",
        "model": "gpt-4.1-mini",   # o gpt-4o-mini, o el que prefieras
        "language": "es",          # idioma del resumen
        "max_chars": 8000,         # recorte máximo de texto a enviar al modelo
    },

    # Configuración de email (SMTP)
    "email": {
        "from": "tu_email@example.com",
        "to": ["destinatario@example.com"],  # puedes poner varios
        "subject_template": "[YouTube] Resumen nuevo vídeo - {channel} - {title}",

        # SMTP típico de Gmail (ejemplo)
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "username": "tu_email@example.com",
        "password": "TU_APP_PASSWORD_O_PASSWORD_SMTP",

        # TLS/SSL (para Gmail: TLS = True, SSL = False)
        "use_tls": True,
        "use_ssl": False,
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
Quiero que resumas el contenido de un vídeo de YouTube a partir de su {source_info}.

Título del vídeo: {video['title']}
Canal: {video['channel']}
Fecha de publicación (si está disponible): {video.get('published','')}

Texto a resumir:
\"\"\"{base_text}\"\"\"

Necesito un resumen estructurado en {language} con este formato (usa siempre encabezados y viñetas):

1. Idea principal (2-3 frases)
2. Puntos clave (viñetas, 5-10 bullets cortos)
3. Conceptos técnicos o definiciones importantes (si aplica)
4. Aplicaciones prácticas / ideas accionables
5. Advertencias, limitaciones o sesgos del contenido (si se perciben)

Máximo ~300 palabras. Sé directo y evita relleno inútil.
"""

    response = client.chat.completions.create(
        model=model,
        temperature=0.3,
        messages=[
            {
                "role": "system",
                "content": (
                    "Eres un asistente que resume vídeos de YouTube de forma clara, "
                    "concisa y estructurada para un inversor ocupado."
                ),
            },
            {"role": "user", "content": prompt_user},
        ],
    )

    return response.choices[0].message.content.strip()


def send_email(email_cfg, subject, body):
    """Envía un email sencillo de texto plano con el resumen."""
    msg = EmailMessage()
    msg["From"] = email_cfg["from"]
    msg["To"] = ", ".join(email_cfg["to"])
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        if email_cfg.get("use_ssl"):
            with smtplib.SMTP_SSL(email_cfg["smtp_server"], email_cfg["smtp_port"]) as server:
                server.login(email_cfg["username"], email_cfg["password"])
                server.send_message(msg)
        else:
            with smtplib.SMTP(email_cfg["smtp_server"], email_cfg["smtp_port"]) as server:
                if email_cfg.get("use_tls"):
                    server.starttls()
                server.login(email_cfg["username"], email_cfg["password"])
                server.send_message(msg)
        print("[INFO] Email enviado correctamente.")
    except Exception as e:
        print(f"[ERROR] Error enviando email: {e}")


# ==========================
# BUCLE PRINCIPAL
# ==========================

def run_forever():
    cfg = CONFIG
    email_cfg = cfg["email"]
    openai_cfg = cfg["openai"]

    if not openai_cfg.get("api_key"):
        raise RuntimeError("Configura tu API key de OpenAI en CONFIG['openai']['api_key'].")

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

                    body = (
                        f"Canal: {video['channel']}\n"
                        f"Título: {video['title']}\n"
                        f"Publicado: {video.get('published','')}\n"
                        f"Enlace: {video['link']}\n\n"
                        f"===== RESUMEN =====\n\n"
                        f"{summary}\n"
                    )

                    subject = email_cfg["subject_template"].format(
                        channel=video["channel"],
                        title=video["title"],
                    )

                    send_email(email_cfg, subject, body)

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
