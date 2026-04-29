# RafInviteBotV2 (Telegram бот + Mini Web App)

## Что это
- Бот на Python (`bot.py`)
- Mini Web App (статический сайт в `web/`) для Telegram
- RSVP: «Կգամ / Չեմ գա (с причиной) / Կպատասխանեմ հետո»
- Админу прилетают уведомления о каждом ответе
- Напоминания: ежедневно неответившим + еженедельно всем (юморные)

## Подготовка `.env`
Создай `.env` рядом с `bot.py` по примеру `.env.example`:

```env
BOT_TOKEN=...
WEBAPP_URL=https://<user>.github.io/<repo>/
ADMIN_CHAT_ID=123456789
EVENT_TITLE=...
EVENT_DATETIME_TEXT=...
EVENT_PLACE_NAME=...
EVENT_ADDRESS=...
EVENT_MAP_URL=...
TIMEZONE=Asia/Yerevan
```

### Как получить `ADMIN_CHAT_ID`
Самый простой способ — написать своему боту `/start`, затем в обработчике ты увидишь `message.chat.id` в логах (мы можем добавить команду `/whoami` при желании).

## Аудио (голос ребёнка)
Положи mp3-файл сюда:
- `web/audio/raf-voice.mp3`

Mini Web App включит звук после нажатия кнопки «Ձայնը միացնե՞մ».

## Установка и запуск (Windows / PowerShell)

```powershell
cd D:\birthday-tg-bot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python bot.py
```

## Локальный просмотр Web App

```powershell
cd D:\birthday-tg-bot\web
python -m http.server 8000
```

## Деплой Web App на GitHub Pages
1) Создай репозиторий на GitHub и залей туда проект.\n+2) В GitHub открой **Settings → Pages**.\n+3) Source: **Deploy from a branch**.\n+4) Branch: `main` (или `master`).\n+5) Folder: **`/web`**.\n+6) Сохрани — через минуту появится URL вида `https://<user>.github.io/<repo>/`.\n+7) Пропиши этот URL в `.env` как `WEBAPP_URL` и перезапусти бота.\n+
## Настройка даты на сайте
Открой `web/script.js` и поменяй:\n+- `EVENT_ISO_LOCAL`\n+- `EVENT_LABEL`
