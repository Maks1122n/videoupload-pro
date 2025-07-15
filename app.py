from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import logging
import tempfile
import dropbox
from dropbox.exceptions import AuthError, ApiError
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import time
import traceback
import shutil
import gc
import json

# Настройка приложения
app = Flask(__name__, static_folder='static')
CORS(app)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# КОНФИГУРАЦИЯ - ИСПОЛЬЗУЕМ ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ И FALLBACK
SPREADSHEET_ID = os.environ.get('GOOGLE_SHEETS_ID', '1uo3JONGwST9BZWKiLhqmn3UcGKx8k9oXqGBNvlkV3RY')
SHEET_NAME = 'Банк исходников'

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

# Настройки файлов
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024
ALLOWED_VIDEO_TYPES = {
    'video/mp4', 'video/avi', 'video/mov', 'video/quicktime', 
    'video/webm', 'video/mkv', 'video/wmv'
}

def create_google_services():
    """Создание сервисов Google API с FALLBACK на встроенные данные"""
    try:
        logger.info("🔍 Проверяю переменные окружения...")
        
        # СНАЧАЛА ПРОБУЕМ ПЕРЕМЕННУЮ ОКРУЖЕНИЯ
        credentials_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
        
        if credentials_json:
            logger.info("📋 Переменная GOOGLE_CREDENTIALS_JSON найдена, парсю JSON...")
            try:
                credentials_info = json.loads(credentials_json)
                creds = Credentials.from_service_account_info(credentials_info, scopes=SCOPES)
                sheets_service = build('sheets', 'v4', credentials=creds)
                logger.info("✅ Google API авторизован через переменную окружения!")
                return sheets_service
            except Exception as e:
                logger.warning(f"⚠️ Ошибка с переменной окружения: {e}")
        
        # FALLBACK НА ВСТРОЕННЫЕ ДАННЫЕ
        logger.info("🔄 Переменная не найдена, использую встроенные данные...")
        logger.error("❌ Установите переменную окружения GOOGLE_CREDENTIALS_JSON")
        return None
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в create_google_services: {e}")
        logger.error(f"❌ Стек ошибки: {traceback.format_exc()}")
        return None

def create_dropbox_client():
    """Создание клиента Dropbox с FALLBACK на встроенный токен"""
    try:
        # СНАЧАЛА ПРОБУЕМ ПЕРЕМЕННУЮ ОКРУЖЕНИЯ
        token = os.environ.get('DROPBOX_ACCESS_TOKEN')
        
        if not token:
            # FALLBACK НА ВСТРОЕННЫЙ ТОКЕН
            logger.info("🔄 Переменная DROPBOX_ACCESS_TOKEN не найдена")
            logger.error("❌ Установите переменную окружения DROPBOX_ACCESS_TOKEN")
            return None
        
        logger.info("📋 Подключаюсь к Dropbox...")
        dbx = dropbox.Dropbox(token)
        account_info = dbx.users_get_current_account()
        logger.info(f"✅ Dropbox подключен успешно. Аккаунт: {account_info.email}")
        return dbx
        
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к Dropbox: {e}")
        logger.error(f"❌ Стек ошибки: {traceback.format_exc()}")
        return None

def create_dropbox_folder_and_get_link(dbx, folder_name):
    """Создание папки в Dropbox"""
    try:
        folder_path = f"/{folder_name}"
        logger.info(f"📂 Создаю папку: {folder_name}")
        
        try:
            dbx.files_create_folder_v2(folder_path)
            logger.info(f"✅ Папка создана: {folder_name}")
        except ApiError as e:
            if e.error.is_path() and e.error.get_path().is_conflict():
                logger.info(f"📁 Папка уже существует: {folder_name}")
            else:
                raise e
        
        try:
            shared_link = dbx.sharing_create_shared_link_with_settings(
                folder_path,
                settings=dropbox.sharing.SharedLinkSettings(
                    requested_visibility=dropbox.sharing.RequestedVisibility.public
                )
            )
            folder_url = shared_link.url
            logger.info(f"🔗 Создана ссылка на папку: {folder_name}")
            return folder_url
        except ApiError as e:
            if e.error.is_shared_link_already_exists():
                links = dbx.sharing_list_shared_links(path=folder_path)
                if links.links:
                    folder_url = links.links[0].url
                    logger.info(f"🔗 Получена существующая ссылка: {folder_name}")
                    return folder_url
            folder_encoded = folder_name.replace('_', '%20')
            return f"https://www.dropbox.com/home/{folder_encoded}"
            
    except Exception as e:
        logger.error(f"❌ Ошибка работы с папкой: {e}")
        return "https://www.dropbox.com/home"

def upload_to_dropbox_simple(dbx, folder_name, file_path, filename):
    """Загрузка файла в Dropbox с подробным логированием"""
    try:
        dropbox_path = f"/{folder_name}/{filename}"
        file_size = os.path.getsize(file_path)
        logger.info(f"📤 Загружаю файл: {filename} ({format_file_size(file_size)})")
        
        start_time = time.time()
        
        with open(file_path, 'rb') as f:
            file_data = f.read()
        
        if len(file_data) <= 150 * 1024 * 1024:  # До 150MB
            logger.info(f"🔄 Использую простой метод загрузки для {filename}")
            dbx.files_upload(file_data, dropbox_path, mode=dropbox.files.WriteMode.overwrite)
            logger.info(f"✅ Файл загружен простым методом: {filename}")
        else:
            logger.info(f"🔄 Использую chunked загрузку для большого файла {filename}")
            chunk_size = 4 * 1024 * 1024  # 4MB
            upload_session_start_result = dbx.files_upload_session_start(file_data[:chunk_size])
            cursor = dropbox.files.UploadSessionCursor(
                session_id=upload_session_start_result.session_id,
                offset=chunk_size
            )
            
            while cursor.offset < len(file_data):
                if (cursor.offset + chunk_size) >= len(file_data):
                    commit = dropbox.files.CommitInfo(path=dropbox_path, mode=dropbox.files.WriteMode.overwrite)
                    dbx.files_upload_session_finish(
                        file_data[cursor.offset:],
                        cursor,
                        commit
                    )
                    break
                else:
                    dbx.files_upload_session_append_v2(
                        file_data[cursor.offset:cursor.offset + chunk_size],
                        cursor
                    )
                    cursor.offset += chunk_size
                    
                    progress = (cursor.offset / len(file_data)) * 100
                    logger.info(f"📈 Прогресс загрузки {filename}: {progress:.1f}%")
            
            logger.info(f"✅ Файл загружен chunked методом: {filename}")
        
        upload_time = time.time() - start_time
        logger.info(f"⏱️ Время загрузки {filename}: {upload_time:.1f} секунд")
        
        # Создаем публичную ссылку
        try:
            shared_link = dbx.sharing_create_shared_link_with_settings(dropbox_path)
            public_url = shared_link.url.replace('?dl=0', '?dl=1')
            logger.info(f"🔗 Создана ссылка на файл: {filename}")
        except ApiError as e:
            if e.error.is_shared_link_already_exists():
                links = dbx.sharing_list_shared_links(path=dropbox_path)
                if links.links:
                    public_url = links.links[0].url.replace('?dl=0', '?dl=1')
                else:
                    public_url = f"https://dropbox.com/s/unknown/{filename}"
            else:
                public_url = f"https://dropbox.com/s/unknown/{filename}"
        
        logger.info(f"🎉 Файл успешно загружен: {filename}")
        return public_url, dropbox_path
        
    except Exception as e:
        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА загрузки {filename}: {e}")
        logger.error(f"❌ Стек: {traceback.format_exc()}")
        raise

def add_row_to_sheet(sheets_service, spreadsheet_id, sheet_name, data):
    """Добавить строку в Google Sheets"""
    try:
        row = [
            data['artikul'],
            data['filename'],
            data['date'],
            data['description'],
            data['folder_link']
        ]
        body = {'values': [row]}
        
        logger.info(f"📊 Добавляю строку в Google Sheets для артикула: {data['artikul']}")
        sheets_service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A:E",
            valueInputOption='USER_ENTERED',
            body=body
        ).execute()
        
        logger.info(f"✅ Строка добавлена в таблицу: {data['artikul']}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка добавления в таблицу: {e}")
        raise

def format_file_size(size_bytes):
    """Форматирование размера файла"""
    if size_bytes == 0:
        return "0 B"
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.1f} {size_names[i]}"

@app.route('/')
def index():
    """Главная страница"""
    try:
        logger.info("🌐 Запрос главной страницы")
        
        # Проверяем сервисы
        dropbox_client = create_dropbox_client()
        sheets_service = create_google_services()
        
        if not dropbox_client:
            logger.error("❌ Dropbox недоступен")
            return '<h1>❌ Ошибка Dropbox</h1><p>Проверьте токен</p>'
        
        if not sheets_service:
            logger.error("❌ Google Sheets недоступен") 
            return '<h1>❌ Ошибка Google Sheets</h1><p>Проверьте credentials</p>'
        
        logger.info("✅ Все сервисы работают, отдаю index.html")
        return send_from_directory('.', 'index.html')
        
    except Exception as e:
        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА главной страницы: {e}")
        return f'<h1>ОШИБКА</h1><p>{str(e)}</p>'

@app.route('/upload', methods=['POST'])
def upload_videos():
    """КРИТИЧЕСКИЙ ENDPOINT ЗАГРУЗКИ"""
    upload_start_time = time.time()
    logger.info("🚨🚨🚨 ПОЛУЧЕН ЗАПРОС НА ЗАГРУЗКУ! 🚨🚨🚨")
    logger.info("🕐 ВРЕМЯ НАЧАЛА ЗАГРУЗКИ: %s", datetime.now().strftime("%H:%M:%S"))
    
    try:
        # Проверяем сервисы
        dropbox_client = create_dropbox_client()
        sheets_service = create_google_services()
        
        if not dropbox_client:
            logger.error("❌ DROPBOX НЕДОСТУПЕН")
            return jsonify({'error': 'Dropbox недоступен'}), 500
        
        # Получаем данные
        artikul = request.form.get('artikul')
        date = request.form.get('date')
        description = request.form.get('description')
        
        logger.info(f"📋 ДАННЫЕ ФОРМЫ:")
        logger.info(f"   Артикул: {artikul}")
        logger.info(f"   Дата: {date}")
        logger.info(f"   Описание: {description}")
        
        if not all([artikul, date, description]):
            logger.error("❌ НЕ ВСЕ ПОЛЯ ЗАПОЛНЕНЫ")
            return jsonify({'error': 'Все поля обязательны'}), 400
        
        # Получаем файлы
        files = request.files.getlist('videos')
        logger.info(f"📁 ПОЛУЧЕНО ФАЙЛОВ: {len(files)}")
        
        if not files or all(file.filename == '' for file in files):
            logger.error("❌ НЕТ ФАЙЛОВ ДЛЯ ЗАГРУЗКИ")
            return jsonify({'error': 'Нет файлов'}), 400
        
        # Валидация файлов
        valid_files = []
        total_size = 0
        for file in files:
            if file.filename == '':
                continue
            
            file.seek(0, 2)
            file_size = file.tell()
            file.seek(0)
            total_size += file_size
            
            logger.info(f"📄 ФАЙЛ: {file.filename} ({format_file_size(file_size)})")
            
            if file_size > MAX_FILE_SIZE:
                logger.error(f"❌ ФАЙЛ СЛИШКОМ БОЛЬШОЙ: {file.filename}")
                return jsonify({'error': f'Файл {file.filename} слишком большой'}), 400
            
            valid_files.append(file)
        
        logger.info(f"📊 ОБЩИЙ РАЗМЕР ФАЙЛОВ: {format_file_size(total_size)}")
        
        # Создаем папку
        dropbox_folder = f"{artikul}_{date}"
        logger.info(f"📂 СОЗДАЮ ПАПКУ: {dropbox_folder}")
        
        folder_url = create_dropbox_folder_and_get_link(dropbox_client, dropbox_folder)
        logger.info(f"🔗 ССЫЛКА НА ПАПКУ: {folder_url}")
        
        uploaded_files = []
        
        # Обрабатываем файлы
        with tempfile.TemporaryDirectory() as temp_dir:
            logger.info(f"📁 ВРЕМЕННАЯ ДИРЕКТОРИЯ: {temp_dir}")
            
            for i, file in enumerate(valid_files, 1):
                file_start_time = time.time()
                logger.info(f"🔄 ОБРАБАТЫВАЮ ФАЙЛ {i}/{len(valid_files)}: {file.filename}")
                
                # Генерируем имя
                file_extension = os.path.splitext(file.filename)[1].lower()
                numbered_filename = f"{i:02d}_{artikul}_{date}{file_extension}"
                
                # Сохраняем временно
                temp_file_path = os.path.join(temp_dir, numbered_filename)
                file.save(temp_file_path)
                file_size = os.path.getsize(temp_file_path)
                
                logger.info(f"💾 ФАЙЛ СОХРАНЕН: {numbered_filename} ({format_file_size(file_size)})")
                
                # Загружаем в Dropbox
                logger.info(f"📤 ЗАГРУЖАЮ В DROPBOX: {numbered_filename}")
                dropbox_url, dropbox_path = upload_to_dropbox_simple(
                    dropbox_client, dropbox_folder, temp_file_path, numbered_filename
                )
                
                file_end_time = time.time()
                file_duration = file_end_time - file_start_time
                
                uploaded_files.append({
                    'filename': numbered_filename,
                    'original_name': file.filename,
                    'size': format_file_size(file_size),
                    'dropbox_url': dropbox_url,
                    'dropbox_path': dropbox_path,
                    'storage': 'Dropbox',
                    'upload_time': f"{file_duration:.1f}s"
                })
                
                logger.info(f"✅ ФАЙЛ {numbered_filename} ЗАГРУЖЕН ЗА {file_duration:.1f} СЕКУНД!")
        
        # Добавляем в Google Sheets
        sheet_success = False
        if sheets_service:
            try:
                logger.info("📊 ДОБАВЛЯЮ В GOOGLE SHEETS")
                
                if len(uploaded_files) == 1:
                    files_description = uploaded_files[0]['filename']
                else:
                    files_description = f"{len(uploaded_files)} файлов"
                
                sheet_data = {
                    'artikul': artikul,
                    'filename': files_description,
                    'date': date,
                    'description': description,
                    'folder_link': folder_url
                }
                
                add_row_to_sheet(sheets_service, SPREADSHEET_ID, SHEET_NAME, sheet_data)
                sheet_success = True
                logger.info("✅ ЗАПИСЬ ДОБАВЛЕНА В GOOGLE SHEETS")
                
            except Exception as e:
                logger.warning(f"⚠️ НЕ УДАЛОСЬ ДОБАВИТЬ В ТАБЛИЦУ: {e}")
        
        # Формируем ответ
        upload_end_time = time.time()
        total_duration = upload_end_time - upload_start_time
        
        response_data = {
            'success': True,
            'message': 'Файлы успешно загружены!',
            'artikul': artikul,
            'date': date,
            'description': description,
            'folder_link': folder_url,
            'dropbox_folder': dropbox_folder,
            'dropbox_success': True,
            'sheet_success': sheet_success,
            'sheet_link': f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}" if sheet_success else None,
            'uploaded_files': uploaded_files,
            'upload_time': datetime.now().isoformat(),
            'total_duration': f"{total_duration:.1f}s",
            'total_size': format_file_size(total_size)
        }
        
        logger.info("🏁 ОБЩЕЕ ВРЕМЯ ЗАГРУЗКИ: %.1f секунд (%.1f минут)", total_duration, total_duration/60)
        logger.info("🎉🎉🎉 ВСЕ ОПЕРАЦИИ ЗАВЕРШЕНЫ УСПЕШНО! 🎉🎉🎉")
        logger.info(f"📋 ЗАГРУЖЕНО {len(uploaded_files)} ФАЙЛОВ ДЛЯ АРТИКУЛА {artikul}")
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"💥💥💥 КРИТИЧЕСКАЯ ОШИБКА: {e}")
        logger.error(f"💥 СТЕК: {traceback.format_exc()}")
        return jsonify({'error': f'Ошибка сервера: {str(e)}'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Проверка здоровья сервиса"""
    logger.info("💚 Проверка здоровья сервиса")
    return jsonify({
        'status': 'OK',
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE
    
    logger.info("🚀🚀🚀 ЗАПУСК VIDEOUPLOAD PRO 🚀🚀🚀")
    logger.info(f"📏 Максимальный размер файла: {format_file_size(MAX_FILE_SIZE)}")
    
    # Проверяем сервисы при запуске
    dropbox_client = create_dropbox_client()
    sheets_service = create_google_services()
    
    logger.info(f"📦 Dropbox: {'✅ Работает' if dropbox_client else '❌ Ошибка'}")
    logger.info(f"📊 Google Sheets: {'✅ Работает' if sheets_service else '❌ Ошибка'}")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
