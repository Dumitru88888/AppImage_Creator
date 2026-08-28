# AppImage Builder — Fluent Design Edition

<img width="1040" height="720" alt="Screenshot_20260828_161643" src="https://github.com/user-attachments/assets/233fe187-6e6a-413f-9973-5b4276a80ad7" />

<img width="1040" height="720" alt="Screenshot_20260828_161643" src="https://github.com/user-attachments/assets/de0df00f-febf-4604-9ac7-1c8200196148" />

<img width="1040" height="720" alt="Screenshot_20260828_161936" src="https://github.com/user-attachments/assets/6ed3f453-4b19-4574-9603-b4f3c90268d3" />

<img width="1040" height="720" alt="Screenshot_20260828_162002" src="https://github.com/user-attachments/assets/65885ee2-bf70-4331-938e-57c7b50b9b05" />






Графическое приложение для сборки переносимых AppImage-пакетов на Linux в стиле Microsoft Fluent Design (PySide 6 + qfluentwidgets).

## Возможности

- **Сборка AppImage** — из любого исполняемого файла, с автоматическим созданием AppDir, AppRun и `.desktop`-файла
- **Автоматическое создание `.desktop`** — одной кнопкой из заполненных метаданных
- **Валидатор `.desktop`-файлов** — проверка обязательных полей и стандартных категорий
- **Менеджер зависимостей** — подключение дополнительных библиотек (.so) к сборке
- **Менеджер скриптов** — включение shell-скриптов в AppImage
- **Сохранение / загрузка конфигураций** в JSON, быстрое сохранение на рабочий стол
- **Автоустановка linuxdeploy** прямо из интерфейса
- **Сборка в фоновом потоке** с журналом и возможностью отмены
- **Тёмная и светлая темы** — приложение следует теме оформления системы
- **Два языка интерфейса** — русский и английский

## Установка

```bash
pip install PySide6 PySide6-Fluent-Widgets
```

## Запуск

```bash
python3 AppImage_Builder_Fluent.py
```

Или двойным щелчком по ярлыку / с помощью скрипта-лаунчера:

```bash
./launch_appimage_builder.sh
```

## Структура проекта

| Файл | Назначение |
|------|-----------|
| `AppImage_Builder_Fluent.py` | Всё приложение в одном файле |
| `launch_appimage_builder.sh` | Запуск без окна терминала (фоновый режим) |
| `install_appimage_tools.sh` | Установка linuxdeploy в систему |

## Системные требования

- Python 3.8+
- Linux (сборка AppImage использует linuxdeploy и работает только в Linux)
- Рекомендуемый значок: PNG 256x256
