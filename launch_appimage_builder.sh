#!/bin/bash
# launch_appimage_builder.sh
# --------------------------
# Запускает AppImage Builder без окна терминала.
# Любой вывод программы уходит в лог, а не в консоль,
# поэтому при запуске из файлового менеджера терминал не открывается.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$DIR/appimage_builder.log"

nohup python3 "$DIR/AppImage_Builder_Fluent.py" >>"$LOG_FILE" 2>&1 &
disown
