#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AppImage Builder — Fluent Design Edition (PySide 6).

Единый файл: конструктор AppImage + валидатор .desktop + менеджер зависимостей.
Интерфейс на PySide 6 в стиле Microsoft Fluent Design (qfluentwidgets):
  * боковая навигация, карточки, акцентные кнопки, всплывающие уведомления;
  * русский и английский языки (переключатель в разделе «Настройки»);
  * светлая и тёмная темы.

Установка зависимостей:
    pip install PySide6 PySide6-Fluent-Widgets

Запуск:
    python app_image_creator_fluent.py

Примечание: сама сборка AppImage (linuxdeploy) работает только в Linux;
на Windows доступны редактор .desktop, валидатор и менеджер зависимостей.
"""

import contextlib
import io
import json
import os
import platform
import random
import shutil
import string
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

try:
    with contextlib.redirect_stdout(io.StringIO()):  # скрываем рекламный баннер qfluentwidgets
        from PySide6.QtCore import QRect, QSize, QPoint, Qt, Signal
        from PySide6.QtWidgets import QApplication, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLayout, QLabel, QVBoxLayout, QWidget
        from qfluentwidgets import (
        BodyLabel,
        CaptionLabel,
        CardWidget,
        ComboBox,
        EditableComboBox,
        FluentIcon as FIF,
        FluentWindow,
        InfoBar,
        InfoBarPosition,
        LineEdit,
        ListWidget,
        NavigationItemPosition,
        PlainTextEdit,
        PrimaryPushButton,
        PushButton,
        StrongBodyLabel,
        SubtitleLabel,
        SwitchButton,
        Theme,
        TitleLabel,
        setTheme,
        setThemeColor,
    )
    with contextlib.redirect_stdout(io.StringIO()):
        from qfluentwidgets.components.navigation import NavigationTreeWidget
except ImportError as _e:  # дружелюбная подсказка при запуске двойным щелчком
    _MSG = (
        "Не найдены зависимости графического интерфейса.\n\n"
        "Установите их командой:\n"
        "    pip install PySide6 PySide6-Fluent-Widgets\n\n"
        f"Подробности: {_e}"
    )
    if __name__ == "__main__":
        print(_MSG)
        try:
            input("\nНажмите Enter для выхода...")
        except EOFError:
            pass
        sys.exit(1)
    raise

# ============================================================================
# Константы
# ============================================================================

APP_NAME = "AppImage Builder"
DEFAULT_APP_VERSION = "1.0"

LINUXDEPLOY_URLS = {
    'arm64': 'https://github.com/linuxdeploy/linuxdeploy/releases/download/1-alpha-20250213-2/linuxdeploy-aarch64.AppImage',
    'amd64': 'https://github.com/linuxdeploy/linuxdeploy/releases/download/1-alpha-20250213-2/linuxdeploy-x86_64.AppImage',
}

VALID_CATEGORIES = [
    'AudioVideo', 'Audio', 'Video', 'Graphics', 'Office',
    'Development', 'Education', 'Game', 'Network', 'Settings',
    'System', 'Utility',
]

REQUIRED_DESKTOP_FIELDS = ['Name', 'Exec', 'Type', 'Categories']

DEFAULT_COMMENT_RU = "Приложение, созданное в AppImage Builder"
DEFAULT_COMMENT_EN = "App created with AppImage Builder"

ICON_SIZE = '256x256'
ICON_DIR = f'usr/share/icons/hicolor/{ICON_SIZE}/apps'
BIN_DIR = 'usr/bin'
APPLICATIONS_DIR = 'usr/share/applications'
LIB_DIR = 'usr/lib'

BUILDS_DIR_NAME = "Сборки AppImage"
SCRIPTS_DIR_NAME = "Скрипты"

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
APP_LOGO_CANDIDATES = ["logo.png", "Program Logo.png"]
APP_LOGO_PATH = next(
    (ASSETS_DIR / name for name in APP_LOGO_CANDIDATES if (ASSETS_DIR / name).exists()),
    ASSETS_DIR / "logo.png",
)


def get_app_icon():
    from PySide6.QtGui import QIcon
    icon = QIcon(str(APP_LOGO_PATH)) if APP_LOGO_PATH.exists() else QIcon()
    return icon


def get_desktop_dir() -> Path:
    try:
        result = subprocess.run(
            ["xdg-user-dir", "DESKTOP"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            path = Path(result.stdout.strip())
            if path.is_dir():
                return path
    except (OSError, subprocess.SubprocessError):
        pass
    return Path.home() / "Desktop"


def get_builds_dir() -> Path:
    builds_dir = get_desktop_dir() / BUILDS_DIR_NAME
    builds_dir.mkdir(parents=True, exist_ok=True)
    return builds_dir


def get_scripts_dir() -> Path:
    scripts_dir = get_desktop_dir() / SCRIPTS_DIR_NAME
    scripts_dir.mkdir(parents=True, exist_ok=True)
    return scripts_dir

COLOR_LOG_BG = '#0f172a'
COLOR_LOG_FG = '#e2e8f0'
COLOR_OK = '#16a34a'
COLOR_WARN = '#d97706'
COLOR_ERR = '#dc2626'
THEME_COLOR = '#0078d4'

# ============================================================================
# Локализация (RU / EN)
# ============================================================================

STRINGS = {
    'ru': {
        'title': f"{APP_NAME} — конструктор AppImage",
        'subtitle': "Сборка переносимых Linux-приложений",
        'tab_build': "Сборка",
        'tab_validator': "Валидатор",
        'tab_deps': "Зависимости",
        'tab_scripts': "Скрипты",
        'tab_settings': "Настройки",
        # Страница сборки
        'files_card': "Файлы",
        'meta_card': "Метаданные",
        'executable': "Исполняемый файл:",
        'icon': "Значок (.png):",
        'app_name': "Название:",
        'version': "Версия:",
        'category': "Категория:",
        'comment': "Описание:",
        'browse': "Обзор…",
        'select_exe_title': "Выберите исполняемый файл",
        'select_icon_title': "Выберите значок",
        'png_files': "Файлы PNG (*.png)",
        'all_files': "Все файлы (*)",
        'save_config': "Сохранить конфигурацию",
        'load_config': "Загрузить конфигурацию",
        'generate': "Собрать AppImage",
        'cancel': "Отменить",
        'clear': "Очистить",
        'linuxdeploy_ok': "linuxdeploy: установлен",
        'linuxdeploy_missing': "linuxdeploy: не найден",
        'install_linuxdeploy': "Установить linuxdeploy",
        'ld_already': "linuxdeploy уже установлен.",
        'ld_install_prompt_t': "Установка linuxdeploy",
        'ld_install_prompt_m': "linuxdeploy не установлен. Скачать и установить его сейчас?",
        'ld_install_fail': "Не удалось установить linuxdeploy. Подробности в журнале.",
        'build_log': "Журнал сборки",
        'err_fill_fields': "Заполните все обязательные поля.",
        'err_exe_not_found': "Исполняемый файл не найден: {}",
        'err_icon_not_found': "Файл значка не найден: {}",
        'err_title': "Ошибка",
        'err_save_cfg': "Не удалось сохранить конфигурацию: {}",
        'err_load_json': "Некорректный JSON-файл: {}",
        'err_read_file': "Не удалось прочитать файл: {}",
        'err_build_failed': "Сборка не удалась: {}",
        'unexpected_error': "Непредвиденная ошибка: {}",
        'cfg_saved': "Конфигурация сохранена: {}",
        'cfg_loaded': "Конфигурация загружена: {}",
        'save_cfg_title': "Сохранить конфигурацию",
        'load_cfg_title': "Загрузить конфигурацию",
        'json_files': "Файлы JSON (*.json)",
        'success_title': "Готово",
        'success_build': "AppImage успешно собран!",
        'info_title': "Информация",
        'build_cancelled': "Сборка отменена.",
        'cancelling': "Отмена сборки…",
        'log_creating_appdir': "Создание AppDir: {}",
        'log_desktop_created': "Файл .desktop создан: {}",
        'log_apprun_created': "AppRun создан: {}",
        'log_dep_added': "Добавлена зависимость: {}",
        'log_ld_missing': "linuxdeploy не найден. Установите его для создания AppImage.",
        'log_running_ld': "Запуск linuxdeploy для поиска зависимостей…",
        'log_executing': "Выполняется: {}",
        'log_build_error': "Ошибка при создании AppImage.",
        'log_categories_issue': "Похоже, проблема в категориях файла .desktop.",
        'log_check_validator': "Проверьте вкладку «Валидатор».",
        'log_build_ok': "AppImage успешно собран!",
        'log_script_added': "Добавлен скрипт: {}",
        'log_script_missing': "Внимание: скрипт не найден, пропущен: {}",
        'log_appimage_copied': "AppImage скопирован: {}",
        'log_copy_failed': "Не удалось скопировать AppImage в {}: {}",
        # Валидатор
        'validator_card': "Файл .desktop",
        'desktop_content': "Содержимое файла .desktop:",
        'validate_btn': "Проверить файл",
        'validation_failed': "Валидация НЕ пройдена: {}",
        'validation_warn': "Валидация пройдена с предупреждениями: {}",
        'validation_passed': "Валидация пройдена",
        'missing_field': "Отсутствует обязательное поле: {}",
        'bad_category': "Категория «{}» не является стандартной. Используйте одну из стандартных категорий.",
        'no_sample_comment': "Пример приложения",
        # Зависимости
        'deps_card': "Библиотеки",
        'add_dependency': "Добавить зависимость:",
        'add': "Добавить",
        'sort': "Сортировать",
        'dep_list': "Список зависимостей:",
        'select_deps_title': "Выберите файлы зависимостей",
        'remove_selected': "Удалить выбранные",
        'clear_all': "Очистить всё",
        # Скрипты
        'scripts_card': "Скрипты (.sh)",
        'script_name': "Имя скрипта:",
        'script_content': "Содержимое скрипта:",
        'save_script': "Сохранить скрипт",
        'add_existing_script': "Добавить существующий",
        'scripts_list': "Скрипты для включения в сборку AppImage:",
        'select_scripts_title': "Выберите shell-скрипты",
        'err_script_name': "Введите имя скрипта.",
        'err_save_script': "Не удалось сохранить скрипт: {}",
        'script_saved': "Скрипт сохранён: {}",
        # Настройки
        'settings_card': "Оформление и язык",
        'theme': "Тёмная тема",
        'language': "Язык интерфейса",
        'settings_hint': "Изменения применяются сразу.",
        'quick_save': "Быстро сохранить на рабочий стол",
        'create_desktop_btn': "Создать файл .desktop автоматически",
        'err_desktop_name': "Введите название приложения.",
        'desktop_saved': "Файл .desktop сохранён: {}",
        'tip_executable': "Путь к исполняемому файлу приложения, которое будет упаковано в AppImage.\nМожно указать вручную или через кнопку «Обзор».",
        'tip_icon': "Путь к значку приложения в формате PNG (рекомендуется 256x256).\nЗначок будет использоваться в AppDir и ярлыке приложения.",
        'tip_name': "Имя приложения (обязательное поле).\nИспользуется в имени AppImage, .desktop-файле и значке.",
        'tip_version': "Версия приложения, например 1.0.0.\nЕсли оставить пустым, будет использована версия по умолчанию.",
        'tip_category': "Категории приложения из свободного меню (обязательное поле).\nМожно указать несколько через точку с запятой, например: Graphics;Utility.\nВлияет на валидацию .desktop-файла.",
        'tip_comment': "Краткое описание приложения для .desktop-файла.\nОтображается в подсказке ярлыка и в меню приложений.",
        'tip_save_cfg': "Сохранить конфигурацию в JSON-файл\nс выбором места и имени файла вручную.",
        'tip_quick_save': "Сохранить конфигурацию в JSON-файл на рабочий стол одним нажатием.\nИмя файла генерируется автоматически: случайное имя + текущие дата и время.",
        'tip_create_desktop': "Автоматически создать .desktop-файл на рабочем столе,\nзаполнив его данными из полей «Название», «Категория», «Описание» и «Версия».\nСодержимое также появится на вкладке «Валидатор».",
        'tip_load_cfg': "Загрузить конфигурацию из ранее сохранённого JSON-файла.",
        'tip_generate': "Запустить сборку AppImage из указанных файлов и метаданных.",
        'tip_cancel': "Прервать текущую сборку AppImage.",
        'tip_deps_entry': "Путь к файлу зависимости (например, .so-библиотеке),\nкоторую нужно включить в AppImage. Можно выбрать несколько файлов кнопкой «Добавить».",
        'tip_deps_list': "Список зависимостей, которые будут скопированы в AppImage.\nВыделите элемент, чтобы удалить его кнопкой «Удалить выбранные».",
        'tip_script_name': "Имя скрипта, например setup.sh.\nЕсли расширение .sh не указано, оно будет добавлено автоматически.",
        'tip_script_content': "Содержимое скрипта на bash.\nСкрипт будет сохранён с правами на выполнение и включён в AppImage.",
        'tip_scripts_list': "Скрипты, которые попадут в AppImage при сборке.\nВыделите элемент, чтобы удалить его кнопкой «Удалить выбранные».",
        'tip_desktop_text': "Содержимое .desktop-файла для проверки.\nВставьте или отредактируйте содержимое и нажмите «Проверить файл».",
    },
    'en': {
        'title': APP_NAME,
        'subtitle': "Build portable Linux applications",
        'tab_build': "Build",
        'tab_validator': "Validator",
        'tab_deps': "Dependencies",
        'tab_scripts': "Scripts",
        'tab_settings': "Settings",
        'files_card': "Files",
        'meta_card': "Metadata",
        'executable': "Executable:",
        'icon': "Icon (.png):",
        'app_name': "App Name:",
        'version': "Version:",
        'category': "Category:",
        'comment': "Comment:",
        'browse': "Browse…",
        'select_exe_title': "Select executable",
        'select_icon_title': "Select icon",
        'png_files': "PNG files (*.png)",
        'all_files': "All files (*)",
        'save_config': "Save Config",
        'load_config': "Load Config",
        'generate': "Generate AppImage",
        'cancel': "Cancel",
        'clear': "Clear",
        'linuxdeploy_ok': "linuxdeploy: available",
        'linuxdeploy_missing': "linuxdeploy: not found",
        'install_linuxdeploy': "Install linuxdeploy",
        'ld_already': "linuxdeploy is already installed.",
        'ld_install_prompt_t': "Install linuxdeploy",
        'ld_install_prompt_m': "linuxdeploy is not installed. Download and install it now?",
        'ld_install_fail': "linuxdeploy installation failed. Check the log for details.",
        'build_log': "Build log",
        'err_fill_fields': "Please complete all required fields.",
        'err_exe_not_found': "Executable file not found: {}",
        'err_icon_not_found': "Icon file not found: {}",
        'err_title': "Error",
        'err_save_cfg': "Failed to save configuration: {}",
        'err_load_json': "Invalid JSON file: {}",
        'err_read_file': "Failed to read file: {}",
        'err_build_failed': "Build failed: {}",
        'unexpected_error': "Unexpected error: {}",
        'cfg_saved': "Configuration saved to {}",
        'cfg_loaded': "Configuration loaded from {}",
        'save_cfg_title': "Save Configuration",
        'load_cfg_title': "Load Configuration",
        'json_files': "JSON files (*.json)",
        'success_title': "Success",
        'success_build': "AppImage generated successfully!",
        'info_title': "Info",
        'build_cancelled': "Build cancelled.",
        'cancelling': "Cancelling build...",
        'log_creating_appdir': "Creating AppDir in {}",
        'log_desktop_created': "Desktop file created at {}",
        'log_apprun_created': "AppRun created at {}",
        'log_dep_added': "Added dependency: {}",
        'log_ld_missing': "linuxdeploy not found. Please install it to create AppImages.",
        'log_running_ld': "Running linuxdeploy to detect dependencies...",
        'log_executing': "Executing: {}",
        'log_build_error': "Error during AppImage creation.",
        'log_categories_issue': "It seems there's an issue with the desktop file categories.",
        'log_check_validator': "Please check the Validator page for details.",
        'log_build_ok': "AppImage generated successfully!",
        'log_script_added': "Added script: {}",
        'log_script_missing': "Warning: script not found, skipped: {}",
        'log_appimage_copied': "AppImage copied to {}",
        'log_copy_failed': "Failed to copy AppImage to {}: {}",
        'validator_card': "Desktop Entry File",
        'desktop_content': "Desktop file content:",
        'validate_btn': "Validate File",
        'validation_failed': "Validation FAILED: {}",
        'validation_warn': "Validation PASSED with warnings: {}",
        'validation_passed': "Validation PASSED",
        'missing_field': "Missing required field: {}",
        'bad_category': "Category '{}' is not a standard category. Consider using one of the standard categories.",
        'no_sample_comment': "A sample application",
        'deps_card': "Libraries",
        'add_dependency': "Add dependency:",
        'add': "Add",
        'sort': "Sort",
        'dep_list': "Dependency list:",
        'select_deps_title': "Select dependency files",
        'remove_selected': "Remove Selected",
        'clear_all': "Clear All",
        'scripts_card': "Scripts (.sh)",
        'script_name': "Script name:",
        'script_content': "Script content:",
        'save_script': "Save Script",
        'add_existing_script': "Add Existing",
        'scripts_list': "Scripts to include in the AppImage build:",
        'select_scripts_title': "Select shell scripts",
        'err_script_name': "Please enter a script name.",
        'err_save_script': "Failed to save script: {}",
        'script_saved': "Script saved to {}",
        'settings_card': "Appearance & language",
        'theme': "Dark theme",
        'language': "Interface language",
        'settings_hint': "Changes are applied immediately.",
        'quick_save': "Quick Save to Desktop",
        'create_desktop_btn': "Create .desktop File Automatically",
        'err_desktop_name': "Please enter the application name.",
        'desktop_saved': ".desktop file saved to {}",
        'tip_executable': "Path to the executable to be packaged into the AppImage.\nEnter it manually or use the Browse button.",
        'tip_icon': "Path to the application icon in PNG format (256x256 recommended).\nThe icon is used in the AppDir and the application shortcut.",
        'tip_name': "Application name (required).\nUsed for the AppImage file name, .desktop file and icon.",
        'tip_version': "Application version, e.g. 1.0.0.\nIf left empty, the default version is used.",
        'tip_category': "Application categories from the free desktop menu (required).\nMultiple categories can be separated by semicolons, e.g.: Graphics;Utility.\nAffects .desktop validation.",
        'tip_comment': "Short application description for the .desktop file.\nShown in the shortcut tooltip and in the applications menu.",
        'tip_save_cfg': "Save the configuration to a JSON file\nchoosing the location and file name manually.",
        'tip_quick_save': "Save the configuration to a JSON file on the desktop in one click.\nThe file name is generated automatically: random name + current date and time.",
        'tip_create_desktop': "Automatically create a .desktop file on the desktop,\nfilling it with the data from the Name, Category, Comment and Version fields.\nThe content is also shown on the Validator tab.",
        'tip_load_cfg': "Load a configuration from a previously saved JSON file.",
        'tip_generate': "Start building the AppImage from the specified files and metadata.",
        'tip_cancel': "Abort the current AppImage build.",
        'tip_deps_entry': "Path to a dependency file (e.g. a .so library)\nto include in the AppImage. Multiple files can be selected with the Add button.",
        'tip_deps_list': "Dependencies that will be copied into the AppImage.\nSelect an item to remove it with the Remove Selected button.",
        'tip_script_name': "Script name, e.g. setup.sh.\nThe .sh extension is added automatically if missing.",
        'tip_script_content': "Bash script content.\nThe script is saved as executable and included in the AppImage.",
        'tip_scripts_list': "Scripts that will be included in the AppImage build.\nSelect an item to remove it with the Remove Selected button.",
        'tip_desktop_text': "Desktop file content to validate.\nPaste or edit the content and press Validate File.",
    },
}

_current_lang = 'ru'


def tr(key: str, *args) -> str:
    s = STRINGS[_current_lang].get(key) or STRINGS['en'].get(key, key)
    return s.format(*args) if args else s


def set_language(lang: str) -> None:
    global _current_lang
    _current_lang = lang


def get_language() -> str:
    return _current_lang


# ============================================================================
# Типы данных и серверная логика (без GUI)
# ============================================================================

@dataclass
class BuildConfig:
    name: str
    version: str
    category: str
    comment: str
    executable_path: Path
    icon_path: Optional[Path] = None
    extra_deps: List[Path] = field(default_factory=list)


@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        if self.errors:
            return tr('validation_failed', "; ".join(self.errors))
        if self.warnings:
            return tr('validation_warn', "; ".join(self.warnings))
        return tr('validation_passed')

    @property
    def color(self) -> str:
        if self.errors:
            return COLOR_ERR
        if self.warnings:
            return COLOR_WARN
        return COLOR_OK


class DesktopFileHandler:
    def generate(self, config: BuildConfig) -> str:
        categories = config.category.strip().rstrip(';')
        return (
            f"[Desktop Entry]\n"
            f"Name={config.name}\n"
            f"Comment={config.comment}\n"
            f"Exec={config.name}\n"
            f"Icon={config.name}\n"
            f"Type=Application\n"
            f"Categories={categories};\n"
            f"Terminal=false\n"
            f"StartupNotify=true\n"
        )

    def validate(self, content: str) -> ValidationResult:
        errors: List[str] = []
        warnings: List[str] = []
        present_fields: List[str] = []

        for line in content.split('\n'):
            line = line.strip()
            if '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip()

            if key in REQUIRED_DESKTOP_FIELDS:
                present_fields.append(key)

            if key == 'Categories':
                for category_value in [c.strip() for c in value.split(';') if c.strip()]:
                    if category_value not in VALID_CATEGORIES:
                        warnings.append(tr('bad_category', category_value))

        for f in REQUIRED_DESKTOP_FIELDS:
            if f not in present_fields:
                errors.append(tr('missing_field', f))

        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)

    def get_sample(self) -> str:
        return (
            "[Desktop Entry]\n"
            "Name=My Application\n"
            "Comment=\n"
            "Exec=myapp\n"
            "Icon=myapp\n"
            "Type=Application\n"
            "Categories=Utility;\n"
            "Terminal=false\n"
            "StartupNotify=true\n"
        )


class AppDirBuilder:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.appdir_path: Optional[Path] = None

    def create(self, config: BuildConfig) -> Path:
        self.appdir_path = self.base_dir / f"{config.name}.AppDir"
        if self.appdir_path.exists():
            shutil.rmtree(self.appdir_path)
        for sub in (BIN_DIR, ICON_DIR, APPLICATIONS_DIR, LIB_DIR):
            (self.appdir_path / sub).mkdir(parents=True, exist_ok=True)
        return self.appdir_path

    def cleanup(self) -> None:
        if self.appdir_path and self.appdir_path.exists():
            shutil.rmtree(self.appdir_path)
            self.appdir_path = None

    def add_executable(self, src: Path) -> Path:
        dest = self.appdir_path / BIN_DIR / src.name
        shutil.copy2(src, dest)
        return dest

    def add_script(self, src: Path) -> Path:
        dest = self.appdir_path / BIN_DIR / src.name
        shutil.copy2(src, dest)
        dest.chmod(0o755)
        return dest

    def add_icon(self, src: Path, name: str) -> Path:
        dest = self.appdir_path / ICON_DIR / f"{name}.png"
        shutil.copy2(src, dest)
        return dest

    def create_desktop_file(self, config: BuildConfig, content: str) -> Path:
        desktop_path = self.appdir_path / APPLICATIONS_DIR / f"{config.name}.desktop"
        desktop_path.write_text(content, encoding='utf-8')
        return desktop_path

    def create_apprun_script(self, executable_name: str) -> Path:
        apprun_content = (
            "#!/bin/bash\n"
            'HERE="$(dirname "$(readlink -f "${0}")")"\n'
            'export LD_LIBRARY_PATH="$HERE/usr/lib:$LD_LIBRARY_PATH"\n'
            f'exec "$HERE/usr/bin/{executable_name}" "$@"\n'
        )
        apprun_path = self.appdir_path / "AppRun"
        apprun_path.write_text(apprun_content, encoding='utf-8')
        apprun_path.chmod(0o755)
        return apprun_path


class LinuxDeployManager:
    def is_available(self) -> bool:
        return shutil.which("linuxdeploy") is not None

    def get_version(self) -> Optional[str]:
        if not self.is_available():
            return None
        try:
            result = subprocess.run(
                ["linuxdeploy", "--version"], capture_output=True, text=True, timeout=5,
            )
            return result.stdout.strip() or result.stderr.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

    def get_url(self, arch: str = None) -> Optional[str]:
        if arch is None:
            arch = platform.machine().lower()
        arch_map = {'aarch64': 'arm64', 'arm64': 'arm64', 'x86_64': 'amd64', 'amd64': 'amd64'}
        return LINUXDEPLOY_URLS.get(arch_map.get(arch))

    def install(self, log_callback: Callable[[str], None] = None) -> bool:
        url = self.get_url()
        if not url:
            if log_callback:
                log_callback("Unsupported CPU architecture for automatic install.")
            return False
        if not shutil.which("pkexec"):
            if log_callback:
                log_callback("pkexec not found. Install policykit or run install_appimage_tools.sh manually.")
            return False
        if log_callback:
            log_callback("Installing linuxdeploy...")

        install_cmd = [
            "pkexec", "bash", "-c",
            "set -e; TMP_DIR=$(mktemp -d); cd \"$TMP_DIR\"; "
            f"wget -c \"{url}\" -O linuxdeploy.AppImage; "
            "chmod +x linuxdeploy.AppImage; "
            "mv linuxdeploy.AppImage /usr/local/bin/linuxdeploy; "
            "cd ~; rm -rf \"$TMP_DIR\""
        ]
        try:
            process = subprocess.Popen(
                install_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            for line in iter(process.stdout.readline, ''):
                if line and log_callback:
                    log_callback(line.strip())
            process.stdout.close()
            process.wait()
            if process.returncode != 0:
                if log_callback:
                    log_callback("linuxdeploy installation failed.")
                return False
            if log_callback:
                log_callback("linuxdeploy installed successfully.")
            return True
        except Exception as e:
            if log_callback:
                log_callback(f"Installation error: {e}")
            return False

    def ensure_available(self, log_callback: Callable[[str], None] = None) -> bool:
        if self.is_available():
            return True
        return self.install(log_callback)


# ============================================================================
# Страница «Сборка»
# ============================================================================

class BuildPage(QWidget):
    log_signal = Signal(str)
    desktop_signal = Signal(str)
    build_state_signal = Signal(bool)
    build_result_signal = Signal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('build-page')

        self.linuxdeploy = LinuxDeployManager()
        self.desktop_handler = DesktopFileHandler()
        self._build_process = None
        self._builder = None
        self._build_thread = None

        self.log_signal.connect(self._append_log)
        self.build_state_signal.connect(self._set_build_state)
        self.build_result_signal.connect(self._on_build_result)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        self.title_row = QHBoxLayout()
        self.title_row.setSpacing(12)
        self.logo_label = QLabel()
        if APP_LOGO_PATH.exists():
            from PySide6.QtGui import QPixmap
            self.logo_label.setPixmap(
                QPixmap(str(APP_LOGO_PATH)).scaled(
                    44, 44, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        self.title_label = SubtitleLabel(tr('tab_build'))
        self.title_row.addWidget(self.logo_label)
        self.title_row.addWidget(self.title_label)
        self.title_row.addStretch(1)
        root.addLayout(self.title_row)

        # --- Карточка «Файлы» ---
        self.files_card = CardWidget(self)
        files = QGridLayout(self.files_card)
        files.setContentsMargins(20, 16, 20, 16)
        files.setHorizontalSpacing(10)
        files.setVerticalSpacing(10)

        self.exe_label = BodyLabel(tr('executable'))
        self.exe_entry = LineEdit()
        self.exe_entry.setClearButtonEnabled(True)
        self.exe_browse = PushButton(FIF.FOLDER, tr('browse'))
        self.exe_browse.clicked.connect(self.select_executable)

        self.icon_label = BodyLabel(tr('icon'))
        self.icon_entry = LineEdit()
        self.icon_entry.setClearButtonEnabled(True)
        self.icon_browse = PushButton(FIF.FOLDER, tr('browse'))
        self.icon_browse.clicked.connect(self.select_icon)

        files.addWidget(self.exe_label, 0, 0)
        files.addWidget(self.exe_entry, 0, 1)
        files.addWidget(self.exe_browse, 0, 2)
        files.addWidget(self.icon_label, 1, 0)
        files.addWidget(self.icon_entry, 1, 1)
        files.addWidget(self.icon_browse, 1, 2)
        files.setColumnStretch(1, 1)
        root.addWidget(self.files_card)

        # --- Карточка «Метаданные» ---
        self.meta_card = CardWidget(self)
        meta = QGridLayout(self.meta_card)
        meta.setContentsMargins(20, 16, 20, 16)
        meta.setHorizontalSpacing(10)
        meta.setVerticalSpacing(10)

        self.name_label = BodyLabel(tr('app_name'))
        self.name_entry = LineEdit()
        self.name_entry.setClearButtonEnabled(True)
        self.version_label = BodyLabel(tr('version'))
        self.version_entry = LineEdit()
        self.version_entry.setClearButtonEnabled(True)

        self.category_label = BodyLabel(tr('category'))
        self.category_combo = EditableComboBox()
        self.category_combo.addItems(VALID_CATEGORIES)
        self.category_combo.setCurrentText("Game")
        self.comment_label = BodyLabel(tr('comment'))
        self.comment_entry = LineEdit()
        self.comment_entry.setClearButtonEnabled(True)
        self.comment_entry.setText(tr_default_comment())

        meta.addWidget(self.name_label, 0, 0)
        meta.addWidget(self.name_entry, 0, 1)
        meta.addWidget(self.version_label, 0, 2)
        meta.addWidget(self.version_entry, 0, 3)
        meta.addWidget(self.category_label, 1, 0)
        meta.addWidget(self.category_combo, 1, 1)
        meta.addWidget(self.comment_label, 1, 2)
        meta.addWidget(self.comment_entry, 1, 3)
        meta.setColumnStretch(1, 2)
        meta.setColumnStretch(3, 3)
        root.addWidget(self.meta_card)

        # --- Действия ---
        self.save_cfg_button = PushButton(FIF.SAVE, tr('save_config'))
        self.save_cfg_button.clicked.connect(self._save_config)
        self.quick_save_button = PushButton(FIF.SAVE_AS, tr('quick_save'))
        self.quick_save_button.clicked.connect(self._quick_save_config)
        self.load_cfg_button = PushButton(FIF.DOCUMENT, tr('load_config'))
        self.load_cfg_button.clicked.connect(self._load_config)
        self.create_desktop_button = PushButton(FIF.TILES, tr('create_desktop_btn'))
        self.create_desktop_button.clicked.connect(self._create_desktop_automatically)
        self.generate_button = PrimaryPushButton(FIF.PLAY, tr('generate'))
        self.generate_button.clicked.connect(self.build_appimage)
        self.cancel_button = PushButton(tr('cancel'))
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel_build)

        root.addWidget(_flow_row(
            self.save_cfg_button, self.quick_save_button, self.load_cfg_button,
            self.create_desktop_button, self.generate_button, self.cancel_button,
        ))

        # --- Статус linuxdeploy ---
        ld_row = QHBoxLayout()
        self.linuxdeploy_status_label = BodyLabel("")
        self.install_linuxdeploy_button = PushButton(FIF.SYNC, tr('install_linuxdeploy'))
        self.install_linuxdeploy_button.clicked.connect(self._prompt_install_linuxdeploy)
        ld_row.addWidget(self.linuxdeploy_status_label)
        ld_row.addStretch(1)
        ld_row.addWidget(self.install_linuxdeploy_button)
        root.addLayout(ld_row)

        # --- Журнал ---
        log_header = QHBoxLayout()
        self.log_label = StrongBodyLabel(tr('build_log'))
        self.clear_log_button = PushButton(tr('clear'))
        self.clear_log_button.clicked.connect(self._clear_log)
        log_header.addWidget(self.log_label)
        log_header.addStretch(1)
        log_header.addWidget(self.clear_log_button)
        root.addLayout(log_header)

        self.log_text = PlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(get_mono_font())
        self.log_text.setStyleSheet(
            f"PlainTextEdit {{ background-color: {COLOR_LOG_BG}; color: {COLOR_LOG_FG}; }}"
        )
        root.addWidget(self.log_text, 1)

        self._apply_tooltips()
        self._update_linuxdeploy_status()

    # --- Подсказки ---
    def _apply_tooltips(self):
        self.exe_entry.setToolTip(tr('tip_executable'))
        self.icon_entry.setToolTip(tr('tip_icon'))
        self.name_entry.setToolTip(tr('tip_name'))
        self.version_entry.setToolTip(tr('tip_version'))
        self.category_combo.setToolTip(tr('tip_category'))
        self.comment_entry.setToolTip(tr('tip_comment'))
        self.save_cfg_button.setToolTip(tr('tip_save_cfg'))
        self.quick_save_button.setToolTip(tr('tip_quick_save'))
        self.load_cfg_button.setToolTip(tr('tip_load_cfg'))
        self.create_desktop_button.setToolTip(tr('tip_create_desktop'))
        self.generate_button.setToolTip(tr('tip_generate'))
        self.cancel_button.setToolTip(tr('tip_cancel'))

    # --- Язык ---
    def apply_language(self):
        self.title_label.setText(tr('tab_build'))
        self.exe_label.setText(tr('executable'))
        self.icon_label.setText(tr('icon'))
        self.name_label.setText(tr('app_name'))
        self.version_label.setText(tr('version'))
        self.category_label.setText(tr('category'))
        self.comment_label.setText(tr('comment'))
        self.exe_browse.setText(tr('browse'))
        self.icon_browse.setText(tr('browse'))
        self.save_cfg_button.setText(tr('save_config'))
        self.load_cfg_button.setText(tr('load_config'))
        self.generate_button.setText(tr('generate'))
        self.cancel_button.setText(tr('cancel'))
        self.install_linuxdeploy_button.setText(tr('install_linuxdeploy'))
        self.log_label.setText(tr('build_log'))
        self.clear_log_button.setText(tr('clear'))
        self.quick_save_button.setText(tr('quick_save'))
        self.create_desktop_button.setText(tr('create_desktop_btn'))
        self._apply_tooltips()
        self._update_linuxdeploy_status()

    # --- Файлы ---
    def select_executable(self):
        path, _ = QFileDialog.getOpenFileName(self, tr('select_exe_title'), "", tr('all_files'))
        if path:
            self.exe_entry.setText(path)
            if not self.name_entry.text():
                self.name_entry.setText(os.path.splitext(os.path.basename(path))[0])

    def select_icon(self):
        path, _ = QFileDialog.getOpenFileName(self, tr('select_icon_title'), "", tr('png_files'))
        if path:
            self.icon_entry.setText(path)

    # --- Журнал ---
    def _append_log(self, message: str):
        self.log_text.appendPlainText(message)

    def _clear_log(self):
        self.log_text.clear()

    # --- linuxdeploy ---
    def _update_linuxdeploy_status(self):
        if self.linuxdeploy.is_available():
            self.linuxdeploy_status_label.setText(tr('linuxdeploy_ok'))
            self.linuxdeploy_status_label.setStyleSheet(f"color: {COLOR_OK};")
            self.install_linuxdeploy_button.setEnabled(False)
        else:
            self.linuxdeploy_status_label.setText(tr('linuxdeploy_missing'))
            self.linuxdeploy_status_label.setStyleSheet(f"color: {COLOR_ERR};")
            self.install_linuxdeploy_button.setEnabled(True)

    def _prompt_install_linuxdeploy(self):
        window = self.window()
        if self.linuxdeploy.is_available():
            InfoBar.success(tr('info_title'), tr('ld_already'), duration=2500, parent=window)
            self._update_linuxdeploy_status()
            return
        InfoBar.warning(
            tr('ld_install_prompt_t'), tr('ld_install_prompt_m'),
            orient=Qt.Horizontal, isClosable=True, position=InfoBarPosition.TOP,
            duration=-1, parent=window,
        )
        success = self.linuxdeploy.install(log_callback=lambda m: self.log_signal.emit(m))
        if not success:
            InfoBar.error(tr('err_title'), tr('ld_install_fail'), duration=4000, parent=window)
        self._update_linuxdeploy_status()

    # --- Конфигурация ---
    def _save_config(self):
        path, _ = QFileDialog.getSaveFileName(
            self, tr('save_cfg_title'), str(get_desktop_dir()), tr('json_files'),
        )
        if not path:
            return
        self._save_config_to_file(path)

    def _quick_save_config(self):
        random_part = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = get_desktop_dir() / f"config_{random_part}_{timestamp}.json"
        self._save_config_to_file(str(path))

    def _save_config_to_file(self, path: str):
        scripts_page = getattr(self.window(), 'scripts_page', None)
        scripts = [str(s) for s in scripts_page.get_scripts()] if scripts_page else []
        config = {
            'name': self.name_entry.text(),
            'version': self.version_entry.text(),
            'category': self.category_combo.currentText(),
            'comment': self.comment_entry.text(),
            'executable_path': self.exe_entry.text(),
            'icon_path': self.icon_entry.text(),
            'scripts': scripts,
        }
        try:
            if not path.endswith('.json'):
                path += '.json'
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            self._append_log(tr('cfg_saved', path))
            InfoBar.success(tr('success_title'), tr('cfg_saved', path), duration=3000, parent=self.window())
        except (OSError, IOError) as e:
            InfoBar.error(tr('err_title'), tr('err_save_cfg', e), duration=4000, parent=self.window())

    def _load_config(self):
        path, _ = QFileDialog.getOpenFileName(self, tr('load_cfg_title'), "", tr('json_files'))
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except (json.JSONDecodeError, ValueError) as e:
            InfoBar.error(tr('err_title'), tr('err_load_json', e), duration=4000, parent=self.window())
            return
        except (OSError, IOError) as e:
            InfoBar.error(tr('err_title'), tr('err_read_file', e), duration=4000, parent=self.window())
            return

        self.name_entry.setText(str(config.get('name', '')))
        self.version_entry.setText(str(config.get('version', '')))
        self.category_combo.setCurrentText(str(config.get('category', '')))
        self.comment_entry.setText(str(config.get('comment', '')))
        self.exe_entry.setText(str(config.get('executable_path', '')))
        self.icon_entry.setText(str(config.get('icon_path', '')))
        scripts_page = getattr(self.window(), 'scripts_page', None)
        if scripts_page:
            scripts_page.set_scripts(config.get('scripts', []))
        self._append_log(tr('cfg_loaded', path))

    # --- Сборка ---
    def _create_desktop_automatically(self):
        name = self.name_entry.text().strip()
        if not name:
            InfoBar.error(tr('err_title'), tr('err_desktop_name'), duration=3000, parent=self.window())
            return
        config = BuildConfig(
            name=name,
            version=self.version_entry.text().strip() or DEFAULT_APP_VERSION,
            category=self.category_combo.currentText().strip(),
            comment=self.comment_entry.text().strip(),
            executable_path=Path(self.exe_entry.text().strip()),
            icon_path=Path(self.icon_entry.text().strip()) if self.icon_entry.text().strip() else None,
        )
        content = self.desktop_handler.generate(config)
        self.desktop_signal.emit(content)

        path = get_desktop_dir() / f"{name}.desktop"
        try:
            path.write_text(content, encoding='utf-8')
            path.chmod(0o755)
        except OSError as e:
            InfoBar.error(tr('err_title'), tr('err_save_cfg', e), duration=4000, parent=self.window())
            return

        self._append_log(tr('log_desktop_created', path))
        self._append_log(content)
        InfoBar.success(tr('success_title'), tr('desktop_saved', path), duration=4000, parent=self.window())

    def _set_build_state(self, building: bool):
        self.generate_button.setEnabled(not building)
        self.cancel_button.setEnabled(building)

    def _cancel_build(self):
        if self._build_process and self._build_process.poll() is None:
            self.log_signal.emit(tr('cancelling'))
            self._build_process.terminate()
            try:
                self._build_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._build_process.kill()
        if self._builder:
            self._builder.cleanup()
            self._builder = None
        self._build_process = None
        self.build_state_signal.emit(False)
        self.log_signal.emit(tr('build_cancelled'))

    def _on_build_result(self, success: bool, message: str):
        window = self.window()
        if success:
            InfoBar.success(tr('success_title'), message, duration=4000, parent=window)
        else:
            InfoBar.error(tr('err_title'), message, duration=5000, parent=window)

    def build_appimage(self):
        if self._build_thread and self._build_thread.is_alive():
            return
        exe = self.exe_entry.text().strip()
        icon = self.icon_entry.text().strip()
        name = self.name_entry.text().strip()
        category = self.category_combo.currentText().strip()

        if not all([exe, icon, name, category]):
            InfoBar.error(tr('err_title'), tr('err_fill_fields'), duration=3000, parent=self.window())
            return
        if not os.path.exists(exe):
            InfoBar.error(tr('err_title'), tr('err_exe_not_found', exe), duration=4000, parent=self.window())
            return
        if not os.path.exists(icon):
            InfoBar.error(tr('err_title'), tr('err_icon_not_found', icon), duration=4000, parent=self.window())
            return

        self.log_text.clear()
        self._deps_cache = self.window().deps_page.get_dependencies()
        self._scripts_cache = [
            str(s) for s in self.window().scripts_page.get_scripts()
        ] if hasattr(self.window(), 'scripts_page') else []
        self.build_state_signal.emit(True)
        self._build_thread = threading.Thread(target=self._run_build, daemon=True)
        self._build_thread.start()

    def _run_build(self):
        try:
            self._execute_build()
        except Exception as e:
            self.log_signal.emit(tr('unexpected_error', e))
            self.build_result_signal.emit(False, tr('err_build_failed', e))
        finally:
            self._build_process = None
            self._build_thread = None
            self.build_state_signal.emit(False)

    def _execute_build(self):
        exe = self.exe_entry.text().strip()
        icon = self.icon_entry.text().strip()
        name = self.name_entry.text().strip()
        version = self.version_entry.text().strip() or DEFAULT_APP_VERSION
        category = self.category_combo.currentText().strip()
        comment = self.comment_entry.text().strip()
        dependencies = list(getattr(self, '_deps_cache', []))

        config = BuildConfig(
            name=name, version=version, category=category, comment=comment,
            executable_path=Path(exe), icon_path=Path(icon),
        )

        desktop_content = self.desktop_handler.generate(config)
        self.desktop_signal.emit(desktop_content)

        validation = self.desktop_handler.validate(desktop_content)
        if not validation.is_valid:
            self.log_signal.emit(validation.summary)
            return

        self._builder = AppDirBuilder(base_dir=Path.cwd())
        self._appdir_path = self._builder.create(config)
        self.log_signal.emit(tr('log_creating_appdir', self._appdir_path))

        self._builder.add_executable(config.executable_path)
        self._builder.add_icon(config.icon_path, name)
        desktop_path = self._builder.create_desktop_file(config, desktop_content)
        self.log_signal.emit(tr('log_desktop_created', desktop_path))

        apprun_path = self._builder.create_apprun_script(config.executable_path.name)
        self.log_signal.emit(tr('log_apprun_created', apprun_path))

        for script in list(getattr(self, '_scripts_cache', [])):
            script_path = Path(script)
            if script_path.exists():
                self._builder.add_script(script_path)
                self.log_signal.emit(tr('log_script_added', script_path.name))
            else:
                self.log_signal.emit(tr('log_script_missing', script))

        for dep in dependencies:
            dep_path = Path(dep)
            if dep_path.exists():
                dest = self._builder.appdir_path / "usr" / "lib" / dep_path.name
                shutil.copy2(dep_path, dest)
                self.log_signal.emit(tr('log_dep_added', dep_path.name))

        if not self.linuxdeploy.ensure_available(log_callback=lambda m: self.log_signal.emit(m)):
            self.log_signal.emit(tr('log_ld_missing'))
            self._builder.cleanup()
            self._builder = None
            self.build_result_signal.emit(False, tr('log_ld_missing'))
            return

        self.log_signal.emit(tr('log_running_ld'))
        cmd = [
            "linuxdeploy",
            "--appdir", str(self._appdir_path),
            "--output", "appimage",
            "--executable", str(self._appdir_path / "usr/bin" / config.executable_path.name),
            "--icon-file", str(self._appdir_path / ICON_DIR / f"{name}.png"),
        ]
        for dep in dependencies:
            dep_path = Path(dep)
            if dep_path.exists():
                cmd.extend(["--library", str(dep_path)])

        self.log_signal.emit(tr('log_executing', ' '.join(cmd)))
        self._build_process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        output = ""
        for line in iter(self._build_process.stdout.readline, ''):
            if line:
                output += line
                self.log_signal.emit(line.rstrip('\n'))
        self._build_process.stdout.close()
        self._build_process.wait()

        if self._build_process.returncode != 0:
            self.log_signal.emit(tr('log_build_error'))
            if "contains an unregistered value" in output:
                self.log_signal.emit(tr('log_categories_issue'))
                self.log_signal.emit(tr('log_check_validator'))
            self._builder.cleanup()
            self._builder = None
            self.build_result_signal.emit(False, tr('log_build_error'))
            return

        self.log_signal.emit(tr('log_build_ok'))

        output_dir = self._appdir_path.parent
        appimages = sorted(output_dir.glob(f"*{name}*.AppImage"))
        if not appimages:
            appimages = sorted(output_dir.glob("*.AppImage"))
        if appimages:
            try:
                builds_dir = get_builds_dir()
                for appimage in appimages:
                    dest = builds_dir / appimage.name
                    shutil.copy2(appimage, dest)
                    self.log_signal.emit(tr('log_appimage_copied', dest))
            except OSError as e:
                self.log_signal.emit(tr('log_copy_failed', builds_dir, e))

        self.build_result_signal.emit(True, tr('success_build'))
        self._builder = None


# ============================================================================
# Страница «Валидатор»
# ============================================================================

class ValidatorPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('validator-page')
        self.handler = DesktopFileHandler()

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        self.title_label = SubtitleLabel(tr('tab_validator'))
        root.addWidget(self.title_label)

        self.content_label = BodyLabel(tr('desktop_content'))
        root.addWidget(self.content_label)

        self.desktop_text = PlainTextEdit()
        self.desktop_text.setFont(get_mono_font())
        self.desktop_text.insertPlainText(self.handler.get_sample())
        self.desktop_text.setToolTip(tr('tip_desktop_text'))
        root.addWidget(self.desktop_text, 1)

        self.validate_button = PrimaryPushButton(FIF.INFO, tr('validate_btn'))
        self.validate_button.clicked.connect(self._on_validate)
        self.validation_result = StrongBodyLabel("")
        btn_row = _flow_row(self.validate_button, self.validation_result)
        root.addWidget(btn_row)

    def apply_language(self):
        self.title_label.setText(tr('tab_validator'))
        self.content_label.setText(tr('desktop_content'))
        self.validate_button.setText(tr('validate_btn'))
        self.desktop_text.setToolTip(tr('tip_desktop_text'))

    def get_content(self) -> str:
        return self.desktop_text.toPlainText()

    def set_content(self, content: str) -> None:
        self.desktop_text.setPlainText(content)

    def validate(self) -> ValidationResult:
        result = self.handler.validate(self.get_content())
        self.validation_result.setText(result.summary)
        self.validation_result.setStyleSheet(f"color: {result.color};")
        return result

    def _on_validate(self) -> None:
        result = self.validate()
        if result.is_valid and not result.warnings:
            InfoBar.success(tr('info_title'), tr('validation_passed'), duration=2500, parent=self.window())
        elif result.is_valid:
            InfoBar.warning(tr('info_title'), tr('validation_passed'), duration=2500, parent=self.window())
        else:
            InfoBar.error(tr('err_title'), tr('validation_failed', '; '.join(result.errors)),
                          duration=4000, parent=self.window())


# ============================================================================
# Страница «Зависимости»
# ============================================================================

class DependenciesPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('deps-page')

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        self.title_label = SubtitleLabel(tr('tab_deps'))
        root.addWidget(self.title_label)

        self.add_label = BodyLabel(tr('add_dependency'))
        self.deps_entry = LineEdit()
        self.deps_entry.setPlaceholderText("/path/to/libfoo.so")
        self.deps_entry.setClearButtonEnabled(True)
        self.add_button = PushButton(FIF.FOLDER, tr('add'))
        self.add_button.clicked.connect(self.select_dependencies)
        self.sort_button = PushButton(FIF.SYNC, tr('sort'))
        self.sort_button.clicked.connect(self.sort_dependencies)

        entry_row = QHBoxLayout()
        entry_row.addWidget(self.add_label)
        entry_row.addWidget(self.deps_entry, 1)
        entry_row.addWidget(self.add_button)
        entry_row.addWidget(self.sort_button)
        root.addLayout(entry_row)

        self.list_label = StrongBodyLabel(tr('dep_list'))
        root.addWidget(self.list_label)

        self.deps_listbox = ListWidget()
        root.addWidget(self.deps_listbox, 1)

        self.remove_button = PushButton(FIF.DELETE, tr('remove_selected'))
        self.remove_button.clicked.connect(self.remove_selected_dependency)
        self.clear_button = PushButton(tr('clear_all'))
        self.clear_button.clicked.connect(self.clear_dependencies)
        root.addWidget(_flow_row(self.remove_button, self.clear_button))

        self.deps_entry.setToolTip(tr('tip_deps_entry'))
        self.deps_listbox.setToolTip(tr('tip_deps_list'))

    def apply_language(self):
        self.title_label.setText(tr('tab_deps'))
        self.add_label.setText(tr('add_dependency'))
        self.deps_entry.setPlaceholderText("/path/to/libfoo.so")
        self.add_button.setText(tr('add'))
        self.sort_button.setText(tr('sort'))
        self.list_label.setText(tr('dep_list'))
        self.remove_button.setText(tr('remove_selected'))
        self.clear_button.setText(tr('clear_all'))
        self.deps_entry.setToolTip(tr('tip_deps_entry'))
        self.deps_listbox.setToolTip(tr('tip_deps_list'))

    def select_dependencies(self):
        files, _ = QFileDialog.getOpenFileNames(self, tr('select_deps_title'))
        existing = set(self.get_dependencies())
        for f in files:
            if f and f not in existing:
                self.deps_listbox.addItem(f)
                existing.add(f)

    def remove_selected_dependency(self):
        for item in self.deps_listbox.selectedItems():
            self.deps_listbox.takeItem(self.deps_listbox.row(item))

    def clear_dependencies(self):
        self.deps_listbox.clear()

    def sort_dependencies(self):
        deps = sorted(self.get_dependencies())
        self.clear_dependencies()
        self.deps_listbox.addItems(deps)

    def get_dependencies(self):
        return [self.deps_listbox.item(i).text() for i in range(self.deps_listbox.count())]

    def set_dependencies(self, deps):
        self.clear_dependencies()
        self.deps_listbox.addItems(deps)


# ============================================================================
# Страница «Скрипты»
# ============================================================================

class ScriptsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('scripts-page')
        self._script_paths = []

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        self.title_label = SubtitleLabel(tr('tab_scripts'))
        root.addWidget(self.title_label)

        card = CardWidget(self)
        inner = QVBoxLayout(card)
        inner.setContentsMargins(20, 16, 20, 16)
        inner.setSpacing(10)

        self.name_label = BodyLabel(tr('script_name'))
        self.name_entry = LineEdit()
        self.name_entry.setPlaceholderText("install_helper.sh")
        self.name_entry.setClearButtonEnabled(True)

        name_row = QHBoxLayout()
        name_row.addWidget(self.name_label)
        name_row.addWidget(self.name_entry, 1)
        inner.addLayout(name_row)

        self.content_label = BodyLabel(tr('script_content'))
        inner.addWidget(self.content_label)

        self.script_text = PlainTextEdit()
        self.script_text.setFont(get_mono_font())
        self.script_text.setPlainText("#!/bin/bash\n")
        inner.addWidget(self.script_text, 1)

        self.save_button = PrimaryPushButton(FIF.SAVE, tr('save_script'))
        self.save_button.clicked.connect(self.save_script)
        self.add_button = PushButton(FIF.FOLDER, tr('add_existing_script'))
        self.add_button.clicked.connect(self.add_existing_script)
        self.remove_button = PushButton(FIF.DELETE, tr('remove_selected'))
        self.remove_button.clicked.connect(self.remove_selected)
        inner.addWidget(_flow_row(self.save_button, self.add_button, self.remove_button))
        root.addWidget(card, 1)

        self.list_label = StrongBodyLabel(tr('scripts_list'))
        root.addWidget(self.list_label)

        self.scripts_listbox = ListWidget()
        root.addWidget(self.scripts_listbox, 1)

        self.name_entry.setToolTip(tr('tip_script_name'))
        self.script_text.setToolTip(tr('tip_script_content'))
        self.scripts_listbox.setToolTip(tr('tip_scripts_list'))

    def apply_language(self):
        self.title_label.setText(tr('tab_scripts'))
        self.name_label.setText(tr('script_name'))
        self.content_label.setText(tr('script_content'))
        self.save_button.setText(tr('save_script'))
        self.add_button.setText(tr('add_existing_script'))
        self.remove_button.setText(tr('remove_selected'))
        self.list_label.setText(tr('scripts_list'))
        self.name_entry.setToolTip(tr('tip_script_name'))
        self.script_text.setToolTip(tr('tip_script_content'))
        self.scripts_listbox.setToolTip(tr('tip_scripts_list'))

    def save_script(self):
        name = self.name_entry.text().strip()
        if not name:
            InfoBar.error(tr('err_title'), tr('err_script_name'), duration=3000, parent=self.window())
            return
        if not name.endswith(".sh"):
            name += ".sh"

        path = get_scripts_dir() / name
        content = self.script_text.toPlainText().rstrip("\n") + "\n"
        try:
            path.write_text(content, encoding="utf-8")
            path.chmod(0o755)
        except OSError as e:
            InfoBar.error(tr('err_title'), tr('err_save_script', e), duration=4000, parent=self.window())
            return

        self._add_script_path(str(path))
        InfoBar.success(tr('info_title'), tr('script_saved', path), duration=3000, parent=self.window())

    def add_existing_script(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, tr('select_scripts_title'), str(get_scripts_dir()),
            "Shell scripts (*.sh);;All files (*)",
        )
        for f in files:
            if f:
                self._add_script_path(f)

    def _add_script_path(self, path: str):
        if path not in self._script_paths:
            self._script_paths.append(path)
            self.scripts_listbox.addItem(path)

    def remove_selected(self):
        for item in self.scripts_listbox.selectedItems():
            self._script_paths.remove(item.text())
            self.scripts_listbox.takeItem(self.scripts_listbox.row(item))

    def get_scripts(self):
        return list(self._script_paths)

    def set_scripts(self, scripts):
        self._script_paths = []
        self.scripts_listbox.clear()
        for s in scripts:
            self._add_script_path(str(Path(str(s)).expanduser().resolve()))


# ============================================================================
# Страница «Настройки»
# ============================================================================

class SettingsPage(QWidget):
    def __init__(self, window: 'MainWindow', parent=None):
        super().__init__(parent)
        self.setObjectName('settings-page')
        self._window = window

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        self.title_label = SubtitleLabel(tr('tab_settings'))
        root.addWidget(self.title_label)

        card = CardWidget(self)
        grid = QGridLayout(card)
        grid.setContentsMargins(20, 16, 20, 16)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(14)

        self.theme_label = BodyLabel(tr('theme'))
        self.theme_switch = SwitchButton()
        self.theme_switch.checkedChanged.connect(self._on_theme_changed)
        self.theme_switch.setChecked(is_system_dark_theme())

        self.lang_label = BodyLabel(tr('language'))
        self.lang_combo = ComboBox()
        self.lang_combo.addItems(['RU', 'EN'])
        self.lang_combo.setCurrentText(get_language().upper())
        self.lang_combo.currentTextChanged.connect(self._on_language_changed)

        grid.addWidget(self.theme_label, 0, 0)
        grid.addWidget(self.theme_switch, 0, 1)
        grid.addWidget(self.lang_label, 1, 0)
        grid.addWidget(self.lang_combo, 1, 1)
        grid.setColumnStretch(0, 1)
        root.addWidget(card)

        self.hint_label = CaptionLabel(tr('settings_hint'))
        root.addWidget(self.hint_label)
        root.addStretch(1)

    def apply_language(self):
        self.title_label.setText(tr('tab_settings'))
        self.theme_label.setText(tr('theme'))
        self.theme_switch.setText(tr('theme'))
        self.lang_label.setText(tr('language'))
        self.hint_label.setText(tr('settings_hint'))

    def _on_theme_changed(self, checked: bool):
        setTheme(Theme.DARK if checked else Theme.LIGHT)

    def _on_language_changed(self, text: str):
        self._window.switch_language(text.lower())


# ============================================================================
# Главное окно
# ============================================================================

class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(tr('title'))
        self.resize(1040, 720)
        self.setMinimumSize(880, 620)

        self.build_page = BuildPage()
        self.validator_page = ValidatorPage()
        self.deps_page = DependenciesPage()
        self.scripts_page = ScriptsPage()
        self.settings_page = SettingsPage(self)

        self.build_page.desktop_signal.connect(self.validator_page.set_content)

        self.addSubInterface(self.build_page, FIF.PLAY, tr('tab_build'))
        self.addSubInterface(self.validator_page, FIF.SEARCH, tr('tab_validator'))
        self.addSubInterface(self.deps_page, FIF.FOLDER, tr('tab_deps'))
        self.addSubInterface(self.scripts_page, FIF.CODE, tr('tab_scripts'))
        self.addSubInterface(self.settings_page, FIF.SETTING, tr('tab_settings'),
                             NavigationItemPosition.BOTTOM)

    def switch_language(self, lang: str):
        old_texts = {
            'tab_build': tr('tab_build'),
            'tab_validator': tr('tab_validator'),
            'tab_deps': tr('tab_deps'),
            'tab_scripts': tr('tab_scripts'),
            'tab_settings': tr('tab_settings'),
        }
        set_language(lang)
        self.setWindowTitle(tr('title'))
        for page in (self.build_page, self.validator_page, self.deps_page,
                     self.scripts_page, self.settings_page):
            page.apply_language()
        for item in self.findChildren(NavigationTreeWidget):
            for key, old in old_texts.items():
                if item.text() == old:
                    item.setText(tr(key))
                    break


def tr_default_comment() -> str:
    return DEFAULT_COMMENT_RU if get_language() == 'ru' else DEFAULT_COMMENT_EN


def get_mono_font():
    from PySide6.QtGui import QFont
    return QFont('Consolas', 10)


def is_system_dark_theme() -> bool:
    """Определяет, используется ли в системе тёмная тема оформления."""
    from PySide6.QtGui import QPalette
    try:
        result = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0 and "dark" in result.stdout.lower():
            return True
    except (OSError, subprocess.SubprocessError):
        pass

    kde_globals = Path.home() / ".config" / "kdeglobals"
    try:
        if kde_globals.exists():
            for line in kde_globals.read_text(encoding='utf-8', errors='ignore').splitlines():
                if line.strip().lower().startswith('colorscheme'):
                    if 'dark' in line.lower():
                        return True
                    break
    except OSError:
        pass

    # Запасной вариант: яркость фонового цвета системной палитры Qt
    try:
        color = QApplication.palette().color(QPalette.ColorRole.Window)
        return color.lightness() < 128
    except Exception:
        return False


class FlowLayout(QLayout):
    """Раскладка, в которой виджеты переносятся на новую строку,
    если не помещаются по ширине. Гарантирует, что текст кнопок
    не обрезается при узком окне."""

    def __init__(self, parent=None, margin=0, spacing=10):
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self._spacing = spacing
        self._items = []

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect, test_only):
        margins = self.contentsMargins()
        effective = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x, y = effective.x(), effective.y()
        line_height = 0
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + self._spacing
            if next_x - self._spacing > effective.right() + 1 and line_height > 0:
                x = effective.x()
                y += line_height + self._spacing
                next_x = x + hint.width() + self._spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + margins.bottom()


def _flow_row(*widgets) -> QWidget:
    """Контейнер с перетекающей раскладкой для строки кнопок."""
    container = QWidget()
    layout = FlowLayout(container, spacing=10)
    for w in widgets:
        layout.addWidget(w)
    return container


def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(get_app_icon())
    setThemeColor(THEME_COLOR)
    setTheme(Theme.DARK if is_system_dark_theme() else Theme.LIGHT)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
