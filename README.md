# YouTube to Telegram - Resúmenes Ejecutivos

Bot que monitorea canales de YouTube y envía **resúmenes ejecutivos** de nuevos vídeos directamente a Telegram.

## 🎯 Características

- ✅ Monitorea canales de YouTube mediante RSS feeds
- ✅ Detecta automáticamente nuevos vídeos
- ✅ Extrae transcripciones completas
- ✅ Genera resúmenes ejecutivos **sin paja** usando OpenAI
- ✅ Envía notificaciones a Telegram
- ✅ Evita duplicados (guarda estado de vídeos procesados)

## 📋 Requisitos Previos

### 1. Crear un Bot de Telegram

1. Abre Telegram y busca **@BotFather**
2. Envía `/newbot` y sigue las instrucciones
3. Guarda el **token** que te proporciona (ej: `1234567890:ABCdefGHI...`)

### 2. Obtener tu Chat ID

1. Busca **@userinfobot** en Telegram
2. Envía `/start`
3. Copia tu **ID** (número como `123456789`)

### 3. API Key de OpenAI

1. Ve a https://platform.openai.com/api-keys
2. Crea una nueva API key
3. Guarda la clave (ej: `sk-proj-...`)

## 🚀 Instalación

### 1. Clonar repositorio

```bash
git clone <este-repo>
cd Youtube_To_Telegram
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 3. Configurar variables de entorno

Copia el archivo de ejemplo:

```bash
cp .env.example .env
```

Edita `.env` con tus credenciales:

```bash
OPENAI_API_KEY=sk-tu-api-key-aqui
TELEGRAM_BOT_TOKEN=1234567890:tu-bot-token
TELEGRAM_CHAT_ID=tu-chat-id
```

**Alternativa:** Puedes editar directamente las claves en `YOUTUBE.py` en la sección `CONFIG`.

### 4. Configurar canales de YouTube

Edita `YOUTUBE.py` y añade los canales que quieres monitorear:

```python
"feeds": [
    {
        "name": "Trading Dominion",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCmJL2llHf2tEcDAjaz-LFgQ",
    },
    {
        "name": "Otro Canal",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=CHANNEL_ID_AQUI",
    },
],
```

#### ¿Cómo obtener el Channel ID?

1. Ve al canal de YouTube
2. Copia la URL del canal (ej: `https://www.youtube.com/@nombrecanal`)
3. Si la URL tiene `@nombrecanal`, busca el ID real:
   - Ve a cualquier vídeo del canal
   - Click derecho → "Ver código fuente de la página"
   - Busca `"channelId"` o `"externalId"`
4. Construye la URL del feed: `https://www.youtube.com/feeds/videos.xml?channel_id=UC...`

## ▶️ Uso

### Ejecutar el bot

```bash
python YOUTUBE.py
```

El bot se ejecutará indefinidamente:
- Revisa los canales cada **15 minutos** (configurable)
- Detecta vídeos nuevos
- Extrae transcripción
- Genera resumen ejecutivo
- Envía a Telegram
- Guarda el estado en `processed_videos.json`

### Ejecutar en segundo plano (Linux/Mac)

```bash
nohup python YOUTUBE.py > youtube_bot.log 2>&1 &
```

### Ejecutar como servicio (systemd)

Crea `/etc/systemd/system/youtube-telegram.service`:

```ini
[Unit]
Description=YouTube to Telegram Bot
After=network.target

[Service]
Type=simple
User=tu-usuario
WorkingDirectory=/ruta/a/Youtube_To_Telegram
Environment="OPENAI_API_KEY=tu-key"
Environment="TELEGRAM_BOT_TOKEN=tu-token"
Environment="TELEGRAM_CHAT_ID=tu-chat-id"
ExecStart=/usr/bin/python3 /ruta/a/Youtube_To_Telegram/YOUTUBE.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Activar:

```bash
sudo systemctl daemon-reload
sudo systemctl enable youtube-telegram
sudo systemctl start youtube-telegram
sudo systemctl status youtube-telegram
```

## ⚙️ Configuración Avanzada

### Ajustar intervalo de comprobación

En `YOUTUBE.py`:

```python
"poll_interval_seconds": 900,  # 15 minutos (900 segundos)
```

### Cambiar modelo de OpenAI

```python
"model": "gpt-4o-mini",  # Más barato
# "model": "gpt-4o",     # Más potente pero más caro
```

### Ajustar límite de texto para OpenAI

```python
"max_chars": 8000,  # Máximo de caracteres de transcripción a enviar
```

## 📊 Formato del Resumen

El bot genera resúmenes con esta estructura:

- 🎯 **Idea Central**: Tesis principal del vídeo
- 💡 **Puntos Clave**: 3-7 conclusiones concretas
- 📊 **Datos de Valor**: Cifras, estadísticas
- ⚠️ **Advertencias**: Sesgos o limitaciones
- 🔑 **Acción Recomendada**: Qué hacer con la información

**Sin paja, sin relleno, solo valor.**

## 🔧 Solución de Problemas

### No recibo mensajes en Telegram

1. Verifica que el bot token y chat ID sean correctos
2. Asegúrate de haber iniciado una conversación con el bot (envía `/start`)
3. Revisa los logs para ver errores

### Error "No transcription available"

- Algunos vídeos no tienen subtítulos/transcripciones
- El bot usará la descripción del vídeo como alternativa

### Error de OpenAI API

- Verifica que tu API key sea válida
- Comprueba que tengas saldo en tu cuenta de OpenAI
- Revisa límites de rate limit

## 📝 Notas

- Los vídeos procesados se guardan en `processed_videos.json`
- Si borras este archivo, el bot procesará todos los vídeos de nuevo
- El bot solo procesa vídeos **nuevos** desde su inicio

## 🔒 Seguridad

- **NO** subas el archivo `.env` a GitHub
- Usa variables de entorno en producción
- Mantén tus tokens y API keys en secreto

## 📄 Licencia

Uso personal y educativo.
