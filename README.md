# 🚀 VideoUpload Pro

VideoUpload Pro - это веб-приложение для загрузки видео файлов в Dropbox с автоматической записью в Google Sheets.

## 📋 Возможности

- ✅ Загрузка видео файлов в Dropbox
- ✅ Автоматическая запись в Google Sheets
- ✅ Современный веб-интерфейс
- ✅ Поддержка больших файлов (до 2GB)
- ✅ История загрузок
- ✅ Прогресс загрузки в реальном времени

## 🛠️ Настройка

### 1. Переменные окружения

Создайте следующие переменные окружения:

```bash
# Dropbox Access Token
DROPBOX_ACCESS_TOKEN=your_dropbox_token_here

# Google Service Account JSON (весь JSON как строка)
GOOGLE_CREDENTIALS_JSON={"type":"service_account","project_id":"your-project",...}

# ID Google Sheets (опционально)
GOOGLE_SHEETS_ID=your_sheet_id_here
```

### 2. Получение Dropbox токена

1. Перейдите на https://www.dropbox.com/developers/apps
2. Создайте новое приложение
3. Получите Access Token
4. Установите переменную `DROPBOX_ACCESS_TOKEN`

### 3. Настройка Google Sheets

1. Перейдите в Google Cloud Console
2. Создайте Service Account
3. Скачайте JSON файл с ключами
4. Установите переменную `GOOGLE_CREDENTIALS_JSON` с содержимым JSON

### 4. Локальный запуск

```bash
pip install -r requirements.txt
python app.py
```

### 5. Развертывание на Render

1. Подключите GitHub репозиторий
2. Установите переменные окружения в настройках Render
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `gunicorn app:app --config gunicorn.conf.py`

## 📁 Структура проекта

```
video_uniquebot_final/
├── app.py              # Основной сервер Flask
├── index.html          # Фронтенд интерфейс
├── requirements.txt    # Python зависимости
├── gunicorn.conf.py    # Конфигурация сервера
├── Procfile           # Команда запуска для Render
├── .gitignore         # Игнорируемые файлы
└── README.md          # Документация
```

## 🔧 Технологический стек

- **Backend**: Python, Flask, Google Sheets API, Dropbox API
- **Frontend**: HTML, CSS, JavaScript
- **Развертывание**: Render, Gunicorn
- **Хранение**: Dropbox (файлы), Google Sheets (метаданные)

## 📊 Как это работает

1. Пользователь выбирает видео файлы через веб-интерфейс
2. Файлы загружаются на сервер
3. Создается папка в Dropbox с именем `{artikul}_{date}`
4. Файлы переименовываются и загружаются в Dropbox
5. Данные записываются в Google Sheets
6. Пользователь получает ссылки на папку и таблицу

## 🎯 Поддерживаемые форматы

- MP4
- AVI
- MOV
- WebM
- MKV
- WMV

## 🚀 Запуск в production

Приложение готово для запуска на Render.com:

1. Форкните репозиторий
2. Подключите к Render
3. Установите переменные окружения
4. Деплой автоматически

## 🔒 Безопасность

- Все секреты хранятся в переменных окружения
- Валидация типов файлов
- Ограничение размера файлов
- Безопасная загрузка через временные директории

## 📞 Поддержка

Если у вас возникли проблемы:
1. Проверьте переменные окружения
2. Убедитесь, что токены действительны
3. Проверьте логи сервера

---

**Создано для эффективной работы с видео контентом! 🎬** 