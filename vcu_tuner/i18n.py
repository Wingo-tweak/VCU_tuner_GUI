"""Centralized user-interface strings."""

from __future__ import annotations

import re

TEXT = {
    "en": {
        "title": "Ninebot G3 VCU A0–A4 tuner", "heading": "Ninebot G3 VCU calibration tuner",
        "subtitle": "1CGC / vehicle variant 0 only. The source file is never overwritten.", "language": "Language",
        "firmware": "Firmware", "open": "Open raw .bin or OTA .zip…", "drop": "or drop a file into this window",
        "no_file": "No file selected", "recognition": "Recognition", "open_firmware": "Open a firmware file",
        "write_blocked": "Writing is disabled", "unsupported_title": "Unsupported firmware", "rejected": "File rejected",
        "checking": "Validating firmware…", "loaded": "Firmware loaded; edits currently exist only in this form",
        "loaded_readonly": "Firmware loaded in read-only mode",
        "exact": "Known SHA-256; structure also verified",
        "structural": "Modified derivative: unknown SHA-256, verified layout and opcodes",
        "readonly": "Known SHA-256; code constants are shown read-only",
        "pair_box": "A0/A1 calibration · decoded initialized RAM", "profile_mode": "Profile / mode", "storage": "Storage",
        "walk": "Walk", "eco": "Eco", "sport": "Sport", "drive": "Drive",
        "sport_working": "Sport working slot (overwritten by reg6E profile)", "sport_preset": "Sport / reg6E={value}",
        "read_only": "read-only",
        "pair_note": "A0/A1 are shown in effective raw units: the MCU receives these integer scales.\nIn 1.5.8+, the Sport working slot is selected again from three reg6E presets and is therefore read-only here.",
        "readonly_pair_note": "This early firmware has no editable A0/A1 calibration table. For 1CGC / variant 0, the confirmed code-constant pair is shared by all listed modes.",
        "scalar_box": "A2–A4 defaults and speed fields · Thumb/raw storage", "field": "Field", "value": "Value",
        "scope_location": "Scope / location", "a2": "A2 default", "a3_1": "A3 default, selector 1",
        "a3_2": "A3 default, selector 2", "a4": "A4 default", "drive_speed": "Drive speed guard/fallback",
        "sport_fallback": "Sport speed fallback/default", "scope_a2": "global for all variants",
        "scope_a3": "conditional producer branch; runtime override may replace it", "scope_a4": "variant group 0/3/4",
        "scope_drive": "vehicle variant 0 only", "scope_sport": "variant 0; used only when reg48 high byte is below 5",
        "scalar_note": "Fields use the 0..255 range. A2 is also checked against the existing ADD.W encoding ({count} of 256 values fit).\nA2/A3/A4 are confirmed producer constants; this does not imply identical effects in every runtime branch.",
        "readonly_scalar_note": "Values are read directly from confirmed code constants and the variant-0 speed table. They are displayed for comparison; this profile cannot export changes.",
        "safety": "Safety boundaries",
        "safety_note": "• A0/A1 and speed-table edits target vehicle variant 0. A2 is global; A4 targets variants 0/3/4.\n• The tool never edits in place. It performs decode → encode → readback and writes a JSON audit.\n• Some float combinations compress poorly and may not fit the IAR source area; export is then rejected.\n• A value fitting its data type is not necessarily safe for the scooter. Existing guards and physical limits still apply.\n• Sport fallback changes reg48 only when its current high byte is below 5; it is not a replacement for code-level 45 km/h guards.",
        "readonly_safety_note": "This exact firmware version is supported as a viewer only. Every input and export action is disabled; the source file cannot be modified by this session.",
        "ota_template": "OTA template:", "loaded_ota_template": "loaded OTA package: {name}",
        "bundled_template": "bundled {name} · SHA-256 {digest}", "custom_template": "custom: {name}",
        "choose_template": "Choose another template…", "reset_template": "Use default template",
        "template_help": "If your flasher rejects the bundled package, choose a template accepted by that flasher.",
        "export_raw": "Export raw binary…", "export_ota": "Export OTA ZIP…", "reset_values": "Reset values",
        "save_raw": "Save raw firmware", "save_ota": "Save OTA ZIP", "select_template": "Choose an OTA ZIP template",
        "exporting": "Repacking and verifying readback…", "export_rejected": "Export rejected",
        "export_failed": "Export failed", "export_complete": "Export complete",
        "created": "Created:\n{artifact}\n\nAudit:\n{audit}\n\nThe source file was not modified.",
        "ready": "Ready", "done": "Done: {name}", "integers": "All fields must contain decimal integers.",
    },
    "ru": {
        "title": "Ninebot G3 VCU — редактор A0–A4", "heading": "Редактор калибровок Ninebot G3 VCU",
        "subtitle": "Только 1CGC / vehicle variant 0. Исходный файл никогда не перезаписывается.", "language": "Язык",
        "firmware": "Прошивка", "open": "Открыть raw .bin или OTA .zip…", "drop": "или перетащите файл в это окно",
        "no_file": "Файл не выбран", "recognition": "Распознавание", "open_firmware": "Откройте файл прошивки",
        "write_blocked": "Запись запрещена", "unsupported_title": "Прошивка не поддерживается", "rejected": "Файл отклонён",
        "checking": "Проверка прошивки…", "loaded": "Прошивка прочитана; изменения пока существуют только в форме",
        "loaded_readonly": "Прошивка прочитана в режиме только для чтения",
        "exact": "Подтверждённый SHA-256; структура также проверена",
        "structural": "Изменённая производная: SHA-256 неизвестен, layout и opcode подтверждены",
        "readonly": "Подтверждённый SHA-256; code constants показаны только для чтения",
        "pair_box": "Калибровка A0/A1 · распакованная initialized RAM", "profile_mode": "Профиль / режим", "storage": "Хранение",
        "walk": "Walk", "eco": "Eco", "sport": "Sport", "drive": "Drive",
        "sport_working": "Рабочая пара Sport (перезаписывается профилем reg6E)", "sport_preset": "Sport / reg6E={value}",
        "read_only": "только чтение",
        "pair_note": "A0/A1 показаны в effective raw units: MCU получает эти целочисленные масштабы.\nВ 1.5.8+ рабочая пара Sport заново выбирается из трёх профилей reg6E и поэтому здесь не редактируется.",
        "readonly_pair_note": "В этой ранней прошивке нет редактируемой таблицы A0/A1. Для 1CGC / variant 0 одна подтверждённая пара code constants общая для всех показанных режимов.",
        "scalar_box": "Значения A2–A4 и скорости · Thumb/raw storage", "field": "Поле", "value": "Значение",
        "scope_location": "Область действия / место", "a2": "A2 по умолчанию", "a3_1": "A3 по умолчанию, selector 1",
        "a3_2": "A3 по умолчанию, selector 2", "a4": "A4 по умолчанию", "drive_speed": "Drive speed guard/fallback",
        "sport_fallback": "Sport speed fallback/default", "scope_a2": "глобально для всех variants",
        "scope_a3": "условная ветка producer; runtime override может заменить", "scope_a4": "группа variants 0/3/4",
        "scope_drive": "только vehicle variant 0", "scope_sport": "variant 0; применяется только при high byte reg48 меньше 5",
        "scalar_note": "Диапазон полей — 0..255. A2 также проверяется по существующей кодировке ADD.W ({count} из 256 значений помещаются).\nA2/A3/A4 — подтверждённые producer constants, но это не означает одинаковый эффект во всех runtime-ветках.",
        "readonly_scalar_note": "Значения считаны из подтверждённых code constants и speed table для variant 0. Они показаны для сравнения; этот профиль не экспортирует изменения.",
        "safety": "Границы безопасности",
        "safety_note": "• A0/A1 и speed table меняются для vehicle variant 0. A2 глобален; A4 относится к variants 0/3/4.\n• Инструмент не меняет файл на месте: выполняются decode → encode → readback и запись JSON audit.\n• Некоторые сочетания float хуже сжимаются и могут не поместиться в IAR source area — экспорт тогда отклоняется.\n• Допустимый тип данных не гарантирует безопасное значение. Штатные guards и физические пределы сохраняются.\n• Sport fallback меняет reg48 лишь когда его high byte меньше 5; это не замена code-level ограничений 45 км/ч.",
        "readonly_safety_note": "Эта точная версия поддерживается только как viewer. Все поля и действия экспорта заблокированы; исходный файл не может быть изменён в этом сеансе.",
        "ota_template": "Шаблон OTA:", "loaded_ota_template": "загруженный OTA пакет: {name}",
        "bundled_template": "встроенный {name} · SHA-256 {digest}", "custom_template": "выбранный: {name}",
        "choose_template": "Выбрать другой template…", "reset_template": "Вернуть template по умолчанию",
        "template_help": "Если Flasher отклоняет встроенный пакет, выберите template, который этот Flasher принимает.",
        "export_raw": "Экспорт raw binary…", "export_ota": "Экспорт OTA ZIP…", "reset_values": "Вернуть значения",
        "save_raw": "Сохранить raw firmware", "save_ota": "Сохранить OTA ZIP", "select_template": "Выберите OTA ZIP template",
        "exporting": "Перепаковка и readback-проверка…", "export_rejected": "Экспорт отклонён",
        "export_failed": "Не удалось экспортировать", "export_complete": "Экспорт завершён",
        "created": "Создано:\n{artifact}\n\nAudit:\n{audit}\n\nИсходный файл не изменён.",
        "ready": "Готово", "done": "Готово: {name}", "integers": "Все поля должны содержать целые десятичные числа.",
    },
}


def tr(language: str, key: str, **values) -> str:
    return TEXT.get(language, TEXT["en"])[key].format(**values)


def localize_error(message: str, language: str) -> str:
    """Translate common backend errors while preserving technical values."""
    if language != "ru":
        return message
    exact = {
        "unknown SHA-256; structural profile was not found. Writing is disabled":
            "Неизвестный SHA-256; структурный профиль не найден. Запись запрещена.",
        "the source file or an existing output file will not be overwritten":
            "Исходный или уже существующий выходной файл не будет перезаписан.",
        "bundled OTA template file is missing": "Файл встроенного OTA template отсутствует.",
        "bundled OTA template SHA-256 mismatch": "SHA-256 встроенного OTA template не совпадает.",
        "OTA template must contain FIRM.bin and info.json": "OTA template должен содержать FIRM.bin и info.json.",
        "repacked IAR stream does not fit in the raw image. Try slightly changing one or more A0/A1 values and export again; different float bit patterns compress differently":
            "Перепакованный IAR stream не помещается в raw image. Попробуйте немного изменить одно или несколько значений A0/A1 и повторить экспорт: разные float-представления сжимаются по-разному.",
        "repacked IAR stream overlaps the next source without a verified zero-fill consumer. Try slightly changing one or more A0/A1 values and export again; different float bit patterns compress differently":
            "Перепакованный IAR stream пересекает следующий source без подтверждённого zero-fill consumer. Попробуйте немного изменить одно или несколько значений A0/A1 и повторить экспорт: разные float-представления сжимаются по-разному.",
        "A0 must be 0..65535 and A1 must be 0..255": "A0 должен быть 0..65535, A1 — 0..255.",
    }
    if message in exact:
        return exact[message]
    match = re.fullmatch(r"VCU (.+) was recognized, but this early code-constant version is read-only", message)
    if match:
        return f"VCU {match.group(1)} распознана, но ранняя code-constant версия доступна только для чтения."
    match = re.fullmatch(r"expected one IAR initialized-data descriptor, found (\d+)", message)
    if match:
        return f"Ожидался один IAR initialized-data descriptor, найдено {match.group(1)}."
    if message.startswith("known SHA-256, but structural checks failed:"):
        return "SHA-256 известен, но проверки структуры не пройдены:" + message.split(":", 1)[1]
    if message.startswith("unknown SHA-256; structural profile is ambiguous:"):
        return "Неизвестный SHA-256; структурный профиль неоднозначен:" + message.split(":", 1)[1]
    if message.startswith("field ") and message.endswith(" is not writable"):
        return "Поле " + message[6:-16] + " недоступно для записи."
    return message
