#!/usr/bin/env python3
"""
LeetCode File Organizer

Автоматически организует .cpp файлы из LeetCodeProblems:
- Создает папки с номерами задач
- Перемещает .cpp файлы в соответствующие папки
- Получает условия задач с LeetCode и algo.monster
"""

import os
import re
import shutil
from pathlib import Path
from typing import Optional, Tuple


# Конфигурация
LEETCODE_PROBLEMS_PATH = "/home/arsen/CLionProjects/LeetCodeProblems"


def extract_problem_number(filename: str) -> Optional[int]:
    """
    Извлекает номер задачи из имени файла.
    
    Поддерживает форматы:
    - 123.cpp -> 123
    - 161Locked.cpp -> 161
    - 269Locked.cpp -> 269
    
    Args:
        filename: Имя файла (например, "123.cpp" или "161Locked.cpp")
        
    Returns:
        Номер задачи или None, если не удалось извлечь
    """
    # Извлекаем число из начала имени файла
    match = re.match(r'^(\d+)', filename)
    if match:
        return int(match.group(1))
    return None


def is_locked_problem(filename: str) -> bool:
    """
    Проверяет, является ли задача Premium (Locked).
    
    Args:
        filename: Имя файла
        
    Returns:
        True если в имени файла есть "Locked", иначе False
    """
    return "Locked" in filename.lower()


def scan_cpp_files(directory: str) -> list[Path]:
    """
    Сканирует директорию и находит все .cpp файлы в корне.
    
    Args:
        directory: Путь к директории для сканирования
        
    Returns:
        Список путей к .cpp файлам
    """
    directory_path = Path(directory)
    if not directory_path.exists():
        print(f"Ошибка: директория {directory} не существует")
        return []
    
    cpp_files = []
    for file_path in directory_path.iterdir():
        if file_path.is_file() and file_path.suffix == '.cpp':
            cpp_files.append(file_path)
    
    return cpp_files


if __name__ == "__main__":
    print("LeetCode File Organizer")
    print("=" * 50)
    
    # Тест функций извлечения
    test_files = ["123.cpp", "161Locked.cpp", "269Locked.cpp", "206.cpp"]
    for test_file in test_files:
        number = extract_problem_number(test_file)
        locked = is_locked_problem(test_file)
        print(f"{test_file}: номер={number}, locked={locked}")
    
    # Сканирование файлов
    print(f"\nСканирование директории: {LEETCODE_PROBLEMS_PATH}")
    cpp_files = scan_cpp_files(LEETCODE_PROBLEMS_PATH)
    print(f"Найдено .cpp файлов: {len(cpp_files)}")
