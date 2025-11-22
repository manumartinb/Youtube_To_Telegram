import time
import os
import urllib.parse
import json

import feedparser
import requests
from openai import OpenAI
from youtube_transcript_api import YouTubeTranscriptApi

################################################################################
#                          CONFIGURACIÓN USUARIO
################################################################################

CONFIG = {
    # ========================================================================
    # 1️⃣ CANALES DE YOUTUBE A MONITORIZAR
    # ========================================================================
    # Para añadir canales: https://www.youtube.com/@NOMBRE_CANAL → copiar ID del canal
    # Formato URL: https://www.youtube.com/feeds/videos.xml?channel_id=CHANNEL_ID

    "feeds": [
    {
        "name": "Cárpatos",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCmJL2llHf2tEcDAjaz-LFgQ",
    },
    {
        "name": "Option Omega",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCHFE_BeGKyV4qyQ3Q4dafmQ",
    },
    {
        "name": "José Luis Cava",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCvCCLJkQpRg0NdT3zNcI08A",
    },
    {
        "name": "Iceberg Fund",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCayvFMTzAubrfBy7ul_wHFw",
    },
    {
        "name": "Rodrigo Villanueva",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCS5LR9INN3Ly5EyV0NksbCA",
    },
    {
        "name": "Pablo Gil",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCPQ2dheMajZPnIleYZHzblg",
    },
    {
        "name": "Spread Greg",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UC02WvbtPYyMm1dG33UAHrDA",
    },
    {
        "name": "Óscar López",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCjKX-osBEQxj9CrZsK9ZM9g",
    },
    {
        "name": "LWS",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCCVIYA5kpLvEToE8Gj8Fszw",
    },
    {
        "name": "Vol. Vibes",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UC0o3EucHQKZCUagsZt6TRAA",
    },
    {
        "name": "Theta Profits",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCzGARfberQ8nRRbsjK90BHg",
    },
    {
        "name": "Hector Chamizo",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCfPrh2GfUkRFawG9whMacpA",
    },
    {
        "name": "Trading Litt",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCiGVu54iO0LYQSGUktEnQog",
    },
    {
        "name": "Quant Py",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UClT4BTqePQDxFHsnrSWQ8Wg",
    },
    # Puedes seguir añadiendo más canales copiando uno de estos bloques
    ],


    # ========================================================================
    # 2️⃣ FRECUENCIA DE COMPROBACIÓN
    # ========================================================================
    "poll_interval_seconds": 900,  # 900s = 15min | 1800s = 30min | 3600s = 1h

    # ========================================================================
    # 3️⃣ CREDENCIALES OPENAI (Resúmenes con IA)
    # ========================================================================
    # Obtén tu API key en: https://platform.openai.com/api-keys
    # Configúrala mediante variable de entorno OPENAI_API_KEY (recomendado)
    # o directamente aquí (menos seguro)

    "openai": {
        "api_key": os.environ.get("OPENAI_API_KEY", "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"),
        "model": "gpt-4o",        # Opciones: gpt-4o-mini (barato) | gpt-4o (mejor calidad)
        "language": "es",              # Idioma del resumen: es | en | fr | de | etc.
        "max_chars": 25000,            # Límite de caracteres a procesar (↑ = resúmenes más extensos)
    },

    # ========================================================================
    # 4️⃣ CREDENCIALES TELEGRAM (Notificaciones)
    # ========================================================================
    # Paso 1: Habla con @BotFather en Telegram → /newbot → copia el BOT_TOKEN
    # Paso 2: Habla con @userinfobot en Telegram → copia tu CHAT_ID
    # Configúralos mediante variables de entorno (recomendado) o aquí directamente

    "telegram": {
        "bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", "8289595775:AAGiGrfe1hJIlNa5yF8UM9jQHvGxi39Lm-U"),
        "chat_id": os.environ.get("TELEGRAM_CHAT_ID", "25523643"),
        "max_message_length": 4096,    # Límite de Telegram (NO modificar)
    },

    # ========================================================================
    # 5️⃣ AVANZADO (normalmente no hace falta tocar)
    # ========================================================================
    "state_file": os.path.join(os.path.expanduser("~"), "Desktop", "processed_videos.json"),  # Archivo JSON con los IDs de los últimos videos procesados por canal
    "transcript_delay_seconds": 5,              # Pausa antes de pedir transcripción (evita bloqueos de YouTube)

    # ========================================================================
    # 6️⃣ ANTI-BLOQUEO (para evitar bloqueos de YouTube)
    # ========================================================================
    "cookies_file": None,                   # Ruta al archivo cookies.txt (formato Netscape) - Ver docs
    "use_oauth": False,                     # Usar autenticación OAuth (más seguro que cookies)
}

################################################################################
#                    FIN CONFIGURACIÓN - NO EDITAR ABAJO
################################################################################


# ==========================
# FUNCIONES AUXILIARES
# ==========================

def load_processed_videos(path):
    """Carga el diccionario de videos procesados desde un archivo JSON.

    Args:
        path: Ruta al archivo JSON con el estado

    Returns:
        dict: Diccionario con formato {nombre_canal: video_id}
    """
    try:
        if not os.path.exists(path):
            print(f"[INFO] Archivo de estado no existe, se creará uno nuevo: {path}")
            return {}

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"[INFO] Estado cargado: {len(data)} canales en seguimiento")
            return data
    except json.JSONDecodeError as e:
        print(f"[WARN] Error al leer JSON ({e}). Creando estado nuevo.")
        return {}
    except Exception as e:
        print(f"[WARN] No se pudo leer el archivo de estado ({e}).")
        return {}


def save_processed_videos(path, processed_videos):
    """Guarda el diccionario de videos procesados en un archivo JSON.

    Args:
        path: Ruta al archivo JSON
        processed_videos: Diccionario con formato {nombre_canal: video_id}
    """
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(processed_videos, f, indent=2, ensure_ascii=False)
        print(f"[INFO] Estado guardado: {len(processed_videos)} canales registrados")
    except Exception as e:
        print(f"[WARN] No se pudo guardar el estado: {e}")


def get_last_processed_video_for_channel(processed_videos, channel_name):
    """Obtiene el último video procesado para un canal específico.

    Args:
        processed_videos: Diccionario con todos los videos procesados
        channel_name: Nombre del canal

    Returns:
        str: ID del último video procesado, o None si no hay ninguno
    """
    return processed_videos.get(channel_name)


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


def get_latest_video(feed_cfg):
    """Lee un feed RSS y devuelve SOLO el video más reciente.

    Args:
        feed_cfg: Configuración del feed

    Returns:
        dict: Información del video más reciente, o None si no hay videos
    """
    print(f"[INFO] Comprobando feed: {feed_cfg['name']}...")
    try:
        feed = feedparser.parse(feed_cfg["url"])
    except Exception as e:
        print(f"[ERROR] Fallo al leer RSS de {feed_cfg['name']}: {e}")
        return None

    entries = getattr(feed, "entries", [])
    if not entries:
        print(f"[WARN] No se encontraron videos en el feed de {feed_cfg['name']}")
        return None

    # El primer entry es el más reciente
    entry = entries[0]
    video_id = extract_video_id(entry)

    if not video_id:
        print(f"[WARN] No se pudo extraer ID del video más reciente")
        return None

    title = getattr(entry, "title", "(sin título)")
    link = getattr(entry, "link", "")
    published = getattr(entry, "published", "")
    description = getattr(entry, "summary", None) or getattr(entry, "media_description", None)

    return {
        "id": video_id,
        "title": title,
        "link": link,
        "published": published,
        "description": description,
        "channel": feed_cfg["name"],
    }


def get_transcript_text(video_id, preferred_languages=None, ytt_api=None, max_chars=None, retry_delay=5, cookies_path=None):
    """Intenta obtener la transcripción del vídeo (subtítulos) y la devuelve como texto plano.

    Args:
        video_id: ID del video de YouTube
        preferred_languages: Lista de idiomas preferidos (default: ["es", "en"])
        ytt_api: Instancia de YouTubeTranscriptApi
        max_chars: Máximo de caracteres a devolver
        retry_delay: Segundos de pausa antes de intentar (para evitar bloqueos)
        cookies_path: Ruta al archivo cookies.txt (formato Netscape) para autenticación

    Returns:
        tuple: (transcript_text, error_reason) - Si falla, devuelve (None, "motivo del error")
    """
    if preferred_languages is None:
        preferred_languages = ["es", "en"]

    # Pausa preventiva para evitar bloqueos de YouTube
    if retry_delay > 0:
        print(f"[INFO] Esperando {retry_delay}s antes de solicitar transcripción...")
        time.sleep(retry_delay)

    try:
        print(f"[INFO] Obteniendo transcripción del video {video_id}...")

        # Si se proporcionan cookies, usarlas para autenticación
        if cookies_path and os.path.exists(cookies_path):
            print(f"[INFO] Usando cookies de {cookies_path} para autenticación")
            transcript_obj = YouTubeTranscriptApi().fetch(
                video_id,
                languages=preferred_languages,
                cookies=cookies_path
            )
        else:
            # Sin cookies (modo normal)
            transcript_obj = YouTubeTranscriptApi().fetch(
                video_id,
                languages=preferred_languages
            )

        # Convertir a lista y extraer texto
        text_parts = [snippet.text for snippet in transcript_obj]
        full_text = " ".join(text_parts)

        print(f"[INFO] ✅ Transcripción obtenida exitosamente ({len(full_text)} caracteres)")

        if max_chars is not None and len(full_text) > max_chars:
            return (full_text[:max_chars], None)
        return (full_text, None)
    except Exception as e:
        error_msg = str(e)

        # Determinar la causa específica del error
        if "Could not retrieve a transcript" in error_msg:
            if "your IP" in error_msg or "IP" in error_msg:
                reason = "YouTube bloqueó la IP por demasiadas peticiones o IP de proveedor cloud"
                print(f"[WARN] ❌ {reason}")
            else:
                reason = "El video no tiene subtítulos/transcripción disponible"
                print(f"[WARN] ❌ {reason}")
        elif "TranscriptsDisabled" in error_msg:
            reason = "Las transcripciones están desactivadas para este video"
            print(f"[WARN] ❌ {reason}")
        elif "NoTranscriptFound" in error_msg:
            reason = f"No se encontró transcripción en los idiomas: {', '.join(preferred_languages)}"
            print(f"[WARN] ❌ {reason}")
        else:
            reason = f"Error desconocido: {str(e)[:100]}"
            print(f"[WARN] ❌ {reason}")

        return (None, reason)


def build_summary(client, cfg_openai, video, transcript_text):
    """Llama al modelo de OpenAI para generar un resumen estructurado.

    Args:
        client: Cliente de OpenAI
        cfg_openai: Configuración de OpenAI
        video: Diccionario con información del video
        transcript_text: Texto de la transcripción (REQUERIDO, no puede ser None)

    Returns:
        str: Resumen generado por OpenAI
    """
    language = cfg_openai.get("language", "es")
    model = cfg_openai["model"]

    max_chars = cfg_openai.get("max_chars") or len(transcript_text)
    base_text = transcript_text[:max_chars]

    prompt_user = f"""
Analiza la transcripción de este vídeo de YouTube y genera un RESUMEN EJECUTIVO DE ALTO VALOR.

📹 VÍDEO: {video['title']}
📢 CANAL: {video['channel']}
📅 FECHA: {video.get('published','')}

TRANSCRIPCIÓN:
\"\"\"{base_text}\"\"\"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 TU OBJETIVO PRINCIPAL

Extraer solo lo que realmente importa para un inversor informado:
ideas, tesis, implicaciones, riesgos, señales de mercado, nuevos datos, consecuencias prácticas.

Tu tarea es separar el grano de la paja y detectar gold nuggets (ideas profundas, señales relevantes, insights accionables, datos importantes o conclusiones clave).

Ignora totalmente:
– relleno verbal
– frases genéricas
– introducciones
– repeticiones
– quejas, bromas o ruido

🧠 TU CRITERIO DE IMPORTANCIA

Considera como ALTA IMPORTANCIA todo lo que sea:
• un dato concreto, cifra o estadística
• una señal de mercado
• un insight nuevo
• una conclusión fuerte del autor
• una explicación que cambie cómo interpretar algo
• una advertencia real
• algo que pueda influir en decisiones de trading o inversión
• un patrón histórico
• una causa-efecto relevante

Considera como PAJA todo lo que sea:
• relleno verbal
• frases obvias
• opiniones genéricas
• explicaciones redundantes
• comentarios anecdóticos

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📄 FORMATO DEL RESULTADO (OBLIGATORIO)

Usa este formato EXACTO con emojis y viñetas para mejor legibilidad:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 <b>IDEA CENTRAL</b>

[Escribe aquí 1-3 frases que resuman la tesis principal del vídeo]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 <b>GOLD NUGGETS</b>

Usa viñetas con formato:
  ▪️ <b>[Concepto clave]:</b> Explicación concreta del hallazgo (1-2 líneas)
  ▪️ <b>[Otro concepto]:</b> Más contexto y por qué importa

Lista 6-10 insights más valiosos con este formato.
Resalta términos importantes en <b>negrita</b>.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 <b>DATOS CLAVE</b>

Usa viñetas con formato:
  • <b>[Métrica]:</b> valor exacto — contexto y relevancia
  • <b>[Otra métrica]:</b> cifra precisa — por qué es importante

Incluye 5-8 datos significativos.
Resalta cifras y porcentajes en <b>negrita</b>.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 <b>IMPLICACIONES</b>

Usa viñetas con formato:
  🔸 <b>[Área de impacto]:</b> Causa → efecto y consecuencias prácticas
  🔸 <b>[Otra área]:</b> Relación y efectos en mercados/sectores

Lista 4-6 implicaciones desarrolladas (1-3 líneas cada una).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ <b>RIESGOS Y ADVERTENCIAS</b>

Usa viñetas con formato:
  ❗ <b>[Tipo de riesgo]:</b> Descripción clara del riesgo e impacto potencial
  ❗ <b>[Otro riesgo]:</b> Incertidumbre identificada y consecuencias

Lista 3-5 riesgos clave (1-2 líneas cada uno).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔑 <b>CONCLUSIÓN</b>

<i>[2-4 frases con las conclusiones más importantes. Usa cursiva aquí para darle énfasis especial a los takeaways finales]</i>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🛡️ <b>ESTRATEGIAS MENCIONADAS</b>

⚠️ <u>CRÍTICO</u>: Solo incluye estrategias que el autor mencione <b>TEXTUALMENTE</b>. NO inventes ni infíeras.

Si HAY estrategias mencionadas explícitamente:
Usa este formato para cada una:

  🎯 <b>Estrategia [nombre/descripción breve]</b>
     • <b>Instrumento:</b> [tipo exacto mencionado]
     • <b>Activo:</b> [qué se tradea]
     • <b>Dirección:</b> [largo/corto/neutral]
     • <b>Horizonte:</b> [timeline si lo menciona]
     • <b>Contexto:</b> [razón textual del autor]
     • <b>Señales:</b> [condiciones de entrada/salida si las menciona]

Si NO HAY estrategias mencionadas:

  <i>El autor no menciona estrategias específicas de trading. El contenido es informativo/analítico.</i>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

REGLAS ESTRICTAS:

📏 <b>EXTENSIÓN Y DENSIDAD</b>
  ✓ Resumen EXTENSO y DETALLADO (mínimo 2500-3500 caracteres)
  ✓ Máxima densidad de información - cada línea debe aportar valor
  ✓ NO resumas superficialmente - desarrolla cada punto con contexto
  ✓ Incluye TODOS los datos relevantes mencionados en el vídeo
  ✓ Respeta los MÍNIMOS indicados en cada sección

🎨 <b>FORMATO Y PRESENTACIÓN</b>
  ✓ USA EXACTAMENTE el formato mostrado arriba con emojis y separadores
  ✓ Usa <b>negrita</b> para: títulos de sección, conceptos clave, cifras importantes
  ✓ Usa <i>cursiva</i> para: conclusiones finales y énfasis especial
  ✓ Usa <u>subrayado</u> solo para advertencias críticas
  ✓ Incluye emojis de viñetas: ▪️ • 🔸 ❗ 🎯 (según la sección)
  ✓ Usa separadores ━━━━━━ entre secciones para claridad visual
  ✓ NUNCA uses: <code>, <pre>, <!doctype>, <html>, <head>, <body>, <div>, <span>, <p>

📝 <b>CONTENIDO</b>
  ✓ Sin introducciones genéricas ("en este vídeo habla de...")
  ✓ Sin frases relleno o redundancias
  ✓ Cada bullet debe ser específico y sustancioso
  ✓ Prioriza profundidad sobre brevedad
  ✓ CRÍTICO: En estrategias, NUNCA inventes. Solo lo que el autor dice TEXTUALMENTE
  ✓ Responde en {language}
"""

    response = client.chat.completions.create(
        model=model,
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": (
                    "Eres un analista financiero senior que genera informes EXTENSOS, DETALLADOS y VISUALMENTE ATRACTIVOS. "
                    "Tu objetivo es extraer TODA la información de valor del contenido original, sin añadir interpretaciones propias. "
                    "Priorizas datos concretos, conclusiones accionables, insights profundos y análisis exhaustivo. "
                    "Eliminas paja y obviedades, pero NUNCA sacrificas profundidad por brevedad. "
                    "Tus informes deben ser completos, sustanciosos y ricos en contenido valioso. "
                    "IMPORTANTE: Genera resúmenes LARGOS (2500-4000 caracteres mínimo) con alta densidad informativa. "
                    "FORMATO VISUAL: Usa el formato exacto especificado con emojis, viñetas Unicode, separadores y HTML. "
                    "Usa <b>negrita</b> para términos clave y cifras, <i>cursiva</i> para conclusiones finales, <u>subrayado</u> para advertencias. "
                    "Incluye emojis de viñetas (▪️ • 🔸 ❗ 🎯) y separadores (━━━━━━) como se indica en el formato. "
                    "NUNCA uses: <code>, <pre>, <!doctype>, <html>, <head>, <body>, <div>, <span>, <p>."
                ),
            },
            {"role": "user", "content": prompt_user},
        ],
    )

    return response.choices[0].message.content.strip()


def sanitize_html_for_telegram(text):
    """Limpia el HTML para que solo contenga etiquetas permitidas por Telegram.

    Telegram solo permite: <b>, <strong>, <i>, <em>, <u>, <ins>, <s>, <strike>,
    <del>, <code>, <pre>, <a href="">, <tg-spoiler>

    Esta función elimina cualquier otra etiqueta HTML no permitida y balancea etiquetas.
    """
    import re

    # SOLUCIÓN SIMPLIFICADA: Eliminar las etiquetas problemáticas <pre> y <code>
    # porque OpenAI no las está cerrando bien y causan errores en Telegram
    text = re.sub(r'</?pre[^>]*>', '', text)
    text = re.sub(r'</?code[^>]*>', '', text)

    # Lista de etiquetas permitidas por Telegram (versión simplificada)
    # Solo permitimos las más seguras: b, i, u, s, a
    allowed_tags = ['b', 'strong', 'i', 'em', 'u', 'ins', 's', 'strike',
                   'del', 'a', 'tg-spoiler']

    # Paso 1: Eliminar etiquetas no permitidas
    pattern = r'<(/?)(\w+)([^>]*)>'

    def replace_tag(match):
        closing = match.group(1)  # "/" si es cierre, "" si es apertura
        tag = match.group(2).lower()
        attrs = match.group(3)

        if tag in allowed_tags:
            # Si es <a>, mantener solo href
            if tag == 'a' and not closing:
                href_match = re.search(r'href=["\']([^"\']*)["\']', attrs)
                if href_match:
                    return f'<a href="{href_match.group(1)}">'
                else:
                    return ''  # <a> sin href, eliminar
            # Para el resto de etiquetas permitidas, mantener sin atributos
            return f'<{closing}{tag}>'
        else:
            # Eliminar etiqueta no permitida
            return ''

    cleaned = re.sub(pattern, replace_tag, text)

    # Paso 2: Balancear etiquetas (cerrar las que quedaron abiertas)
    def balance_tags(text):
        """Asegura que todas las etiquetas estén balanceadas."""
        stack = []
        result = []

        # Encontrar todas las etiquetas
        tag_pattern = r'<(/?)(\w+)(?:\s+[^>]*)?>|([^<]+)'

        for match in re.finditer(tag_pattern, text):
            full_match = match.group(0)
            is_closing = match.group(1) == '/'
            tag_name = match.group(2)
            text_content = match.group(3)

            if text_content:
                # Es texto plano
                result.append(text_content)
            elif tag_name:
                tag_lower = tag_name.lower()
                if is_closing:
                    # Etiqueta de cierre
                    if stack and stack[-1] == tag_lower:
                        stack.pop()
                        result.append(full_match)
                    # Si no coincide, ignorar la etiqueta de cierre
                else:
                    # Etiqueta de apertura
                    stack.append(tag_lower)
                    result.append(full_match)

        # Cerrar etiquetas que quedaron abiertas
        while stack:
            tag = stack.pop()
            result.append(f'</{tag}>')

        return ''.join(result)

    balanced = balance_tags(cleaned)

    return balanced


def send_telegram(telegram_cfg, message):
    """Envía un mensaje a Telegram usando la Bot API."""
    bot_token = telegram_cfg["bot_token"]
    chat_id = telegram_cfg["chat_id"]
    max_length = telegram_cfg.get("max_message_length", 4096)

    # Sanitizar HTML antes de enviar
    original_length = len(message)
    message = sanitize_html_for_telegram(message)
    sanitized_length = len(message)

    if original_length != sanitized_length:
        print(f"[INFO] HTML sanitizado: {original_length} → {sanitized_length} caracteres")

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
    if not openai_cfg.get("api_key") or openai_cfg["api_key"].startswith("sk-XXX"):
        raise RuntimeError(
            "❌ FALTA CONFIGURAR: OpenAI API Key\n"
            "→ Opción 1: Variable de entorno OPENAI_API_KEY\n"
            "→ Opción 2: Edita CONFIG['openai']['api_key'] en el script"
        )

    if not telegram_cfg.get("bot_token") or telegram_cfg["bot_token"].startswith("123456789:XXX"):
        raise RuntimeError(
            "❌ FALTA CONFIGURAR: Telegram Bot Token\n"
            "→ Opción 1: Variable de entorno TELEGRAM_BOT_TOKEN\n"
            "→ Opción 2: Edita CONFIG['telegram']['bot_token'] en el script\n"
            "→ Obténlo hablando con @BotFather en Telegram"
        )

    if not telegram_cfg.get("chat_id") or telegram_cfg["chat_id"] == "123456789":
        raise RuntimeError(
            "❌ FALTA CONFIGURAR: Telegram Chat ID\n"
            "→ Opción 1: Variable de entorno TELEGRAM_CHAT_ID\n"
            "→ Opción 2: Edita CONFIG['telegram']['chat_id'] en el script\n"
            "→ Obténlo hablando con @userinfobot en Telegram"
        )

    client = OpenAI(api_key=openai_cfg["api_key"])
    transcript_delay = cfg.get("transcript_delay_seconds", 5)

    while True:
        try:
            # Cargar el estado de todos los canales al inicio de cada ciclo
            processed_videos = load_processed_videos(cfg["state_file"])

            for feed_cfg in cfg["feeds"]:
                # Obtener el último video del feed
                latest_video = get_latest_video(feed_cfg)

                if not latest_video:
                    print(f"[WARN] No se pudo obtener el último video de {feed_cfg['name']}\n")
                    continue

                # Obtener el ID del último video procesado para ESTE canal específico
                channel_name = feed_cfg["name"]
                last_processed_id = get_last_processed_video_for_channel(processed_videos, channel_name)

                # Verificar si ya fue procesado
                if latest_video["id"] == last_processed_id:
                    print(f"[INFO] ✅ Último video ya procesado: {latest_video['title']} (Canal: {channel_name})\n")
                    continue

                # Nuevo video detectado
                print(f"\n[INFO] ══════════════════════════════════════")
                print(f"[INFO] 🆕 NUEVO VIDEO DETECTADO")
                print(f"[INFO] Procesando: {latest_video['title']}")
                print(f"[INFO] Canal: {latest_video['channel']}")
                print(f"[INFO] ID: {latest_video['id']}")
                print(f"[INFO] ══════════════════════════════════════\n")

                transcript_text, error_reason = get_transcript_text(
                    latest_video["id"],
                    preferred_languages=["es", "en"],
                    ytt_api=None,
                    max_chars=openai_cfg.get("max_chars"),
                    retry_delay=transcript_delay,
                    cookies_path=cfg.get("cookies_file"),
                )

                # Si NO se pudo obtener la transcripción, enviamos error a Telegram
                if transcript_text is None:
                    print(f"[ERROR] ❌ No se pudo procesar el video (sin transcripción)")

                    error_message = (
                        f"⚠️ <b>ERROR AL PROCESAR VIDEO</b>\n\n"
                        f"📺 <b>{latest_video['channel']}</b>\n"
                        f"🎬 {latest_video['title']}\n"
                        f"🔗 <a href=\"{latest_video['link']}\">Ver vídeo</a>\n"
                        f"📅 {latest_video.get('published','')}\n\n"
                        f"━━━━━━━━━━━━━━━━━━\n\n"
                        f"❌ <b>No se pudo obtener la transcripción</b>\n\n"
                        f"<b>Motivo:</b>\n"
                        f"• {error_reason}\n\n"
                        f"💡 <b>Solución:</b> El script reintentará en 15 minutos.\n"
                        f"Si el problema persiste, verifica manualmente el video."
                    )

                    send_telegram(telegram_cfg, error_message)

                    # NO marcamos como procesado para que lo reintente después
                    print(f"[INFO] Video NO marcado como procesado, se reintentará después\n")
                    continue

                # Si SÍ obtuvimos la transcripción, generamos resumen
                print(f"[INFO] Generando resumen con transcripción completa...")
                summary = build_summary(client, openai_cfg, latest_video, transcript_text)

                # Formatear mensaje para Telegram con HTML básico
                message = (
                    f"📺 <b>{latest_video['channel']}</b>\n"
                    f"🎬 {latest_video['title']}\n"
                    f"🔗 <a href=\"{latest_video['link']}\">Ver vídeo</a>\n"
                    f"📅 {latest_video.get('published','')}\n\n"
                    f"━━━━━━━━━━━━━━━━━━\n\n"
                    f"{summary}\n"
                )

                send_telegram(telegram_cfg, message)

                # Marcamos el vídeo como procesado SOLO si todo fue exitoso
                # Actualizamos el diccionario y guardamos
                processed_videos[channel_name] = latest_video["id"]
                save_processed_videos(cfg["state_file"], processed_videos)
                print(f"[INFO] ✅ Video procesado y guardado correctamente para el canal '{channel_name}'\n")

        except Exception as e:
            print(f"[ERROR] Error general en el bucle principal: {e}")
            import traceback
            traceback.print_exc()

        wait = cfg["poll_interval_seconds"]
        print(f"[INFO] ⏰ Esperando {wait} segundos ({wait//60} minutos) antes de la próxima comprobación...\n")
        time.sleep(wait)


if __name__ == "__main__":
    run_forever()
