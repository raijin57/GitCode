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
import time
import requests
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


def get_problem_slug(problem_number: int) -> Optional[str]:
    """
    Получает slug (название) задачи по номеру через GraphQL API LeetCode.
    
    Args:
        problem_number: Номер задачи
        
    Returns:
        Slug задачи (например, "two-sum") или None при ошибке
    """
    graphql_url = "https://leetcode.com/graphql/"
    
    # GraphQL запрос для получения информации о задаче по номеру
    query = """
    query problemsetQuestionList($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {
      problemsetQuestionList: questionList(
        categorySlug: $categorySlug
        limit: $limit
        skip: $skip
        filters: $filters
      ) {
        total: totalNum
        questions: data {
          acRate
          difficulty
          freqBar
          frontendQuestionId: questionFrontendId
          isFavor
          paidOnly: isPaidOnly
          status
          title
          titleSlug
          topicTags {
            name
            id
            slug
          }
          hasSolution
          hasVideoSolution
        }
      }
    }
    """
    
    # Запрашиваем все задачи и ищем по номеру
    variables = {
        "categorySlug": "",
        "skip": 0,
        "limit": 50,  # Начнем с небольшого лимита
        "filters": {}
    }
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        # Пробуем найти задачу, перебирая страницы
        skip = 0
        limit = 50
        
        while True:
            variables["skip"] = skip
            variables["limit"] = limit
            
            response = requests.post(
                graphql_url,
                json={"query": query, "variables": variables},
                headers=headers,
                timeout=10
            )
            
            if response.status_code != 200:
                print(f"Ошибка GraphQL запроса: {response.status_code}")
                return None
            
            data = response.json()
            
            if "errors" in data:
                print(f"Ошибка GraphQL: {data['errors']}")
                return None
            
            questions = data.get("data", {}).get("problemsetQuestionList", {}).get("questions", [])
            
            if not questions:
                break
            
            # Ищем задачу с нужным номером
            for question in questions:
                frontend_id = question.get("frontendQuestionId")
                if frontend_id and int(frontend_id) == problem_number:
                    return question.get("titleSlug")
            
            # Если не нашли, проверяем есть ли еще страницы
            total = data.get("data", {}).get("problemsetQuestionList", {}).get("total", 0)
            if skip + limit >= total:
                break
            
            skip += limit
            time.sleep(1)  # Задержка для избежания rate limiting
        
        print(f"Задача с номером {problem_number} не найдена")
        return None
        
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе к GraphQL API: {e}")
        return None
    except Exception as e:
        print(f"Неожиданная ошибка: {e}")
        return None


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
