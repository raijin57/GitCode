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
from bs4 import BeautifulSoup
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


def get_leetcode_problem_description(slug: str) -> Optional[str]:
    """
    Получает условие задачи с LeetCode через веб-скрапинг.
    
    Args:
        slug: Slug задачи (например, "two-sum")
        
    Returns:
        Текст условия задачи или None при ошибке
    """
    url = f"https://leetcode.com/problems/{slug}/description/"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            print(f"Ошибка при запросе к LeetCode: {response.status_code}")
            return None
        
        soup = BeautifulSoup(response.content, 'lxml')
        
        # Ищем описание задачи
        # LeetCode использует различные селекторы, попробуем несколько вариантов
        description = None
        
        # Вариант 1: ищем в div с классом description
        desc_div = soup.find('div', class_='description')
        if desc_div:
            description = desc_div.get_text(strip=True)
        
        # Вариант 2: ищем в meta тегах или других местах
        if not description:
            # Попробуем найти через data-атрибуты или другие селекторы
            content_div = soup.find('div', {'data-track-load': 'description_content'})
            if content_div:
                description = content_div.get_text(strip=True)
        
        # Вариант 3: попробуем найти через GraphQL данные в скриптах
        if not description:
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'questionContent' in script.string:
                    # Парсим JSON данные из скрипта
                    import json
                    try:
                        # Ищем JSON данные в скрипте
                        content_match = re.search(r'questionContent["\']?\s*:\s*["\']([^"\']+)', script.string)
                        if content_match:
                            description = content_match.group(1)
                            break
                    except:
                        pass
        
        if description:
            # Очищаем HTML теги если они есть
            if '<' in description:
                desc_soup = BeautifulSoup(description, 'html.parser')
                description = desc_soup.get_text(separator='\n', strip=True)
            
            return description
        else:
            print(f"Не удалось найти описание задачи для slug: {slug}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе к LeetCode: {e}")
        return None
    except Exception as e:
        print(f"Неожиданная ошибка при парсинге: {e}")
        return None


def get_algo_monster_problem(problem_number: int, slug: Optional[str] = None) -> Optional[str]:
    """
    Получает условие Premium задачи с algo.monster.
    
    Args:
        problem_number: Номер задачи
        slug: Slug задачи (опционально, для более точного поиска)
        
    Returns:
        Текст условия задачи или None при ошибке
    """
    # Пробуем разные варианты URL на algo.monster
    urls_to_try = []
    
    if slug:
        urls_to_try.append(f"https://algo.monster/problems/{slug}")
        urls_to_try.append(f"https://algo.monster/lc/{slug}")
    
    urls_to_try.append(f"https://algo.monster/problems/{problem_number}")
    urls_to_try.append(f"https://algo.monster/lc/{problem_number}")
    urls_to_try.append(f"https://algo.monster/problems/leetcode-{problem_number}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }
    
    for url in urls_to_try:
        try:
            response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'lxml')
                
                # Ищем описание задачи на algo.monster
                # Структура может отличаться, пробуем разные селекторы
                description = None
                
                # Вариант 1: ищем в основных контентных блоках
                content_divs = soup.find_all(['div', 'article', 'section'], class_=re.compile(r'content|description|problem|question', re.I))
                for div in content_divs:
                    text = div.get_text(strip=True)
                    if len(text) > 100:  # Достаточно длинный текст, вероятно описание
                        description = text
                        break
                
                # Вариант 2: ищем в main контенте
                if not description:
                    main = soup.find('main')
                    if main:
                        description = main.get_text(separator='\n', strip=True)
                
                # Вариант 3: ищем в article
                if not description:
                    article = soup.find('article')
                    if article:
                        description = article.get_text(separator='\n', strip=True)
                
                if description and len(description) > 50:
                    return description
                    
        except requests.exceptions.RequestException:
            continue  # Пробуем следующий URL
        except Exception as e:
            print(f"Ошибка при парсинге algo.monster ({url}): {e}")
            continue
    
    print(f"Не удалось получить условие задачи {problem_number} с algo.monster")
    return None


def create_locked_problem_template(problem_number: int, slug: Optional[str] = None) -> str:
    """
    Создает шаблон .md файла для Premium (Locked) задач.
    
    Args:
        problem_number: Номер задачи
        slug: Slug задачи (опционально)
        
    Returns:
        Содержимое .md файла
    """
    title = f"Problem {problem_number}"
    if slug:
        title += f" - {slug.replace('-', ' ').title()}"
    
    algo_monster_urls = []
    if slug:
        algo_monster_urls.append(f"https://algo.monster/problems/{slug}")
        algo_monster_urls.append(f"https://algo.monster/lc/{slug}")
    algo_monster_urls.append(f"https://algo.monster/problems/{problem_number}")
    algo_monster_urls.append(f"https://algo.monster/lc/{problem_number}")
    
    template = f"""# {title}

## Premium Problem (Locked)

Эта задача доступна только с LeetCode Premium подпиской.

### Ссылки на сторонние ресурсы:

"""
    
    for url in algo_monster_urls:
        template += f"- [algo.monster]({url})\n"
    
    template += f"""
### Условие задачи:

*Заполните условие задачи вручную, используя один из ресурсов выше.*

### Примеры:

```
Входные данные:
Выходные данные:
```

### Ограничения:

- 

### Решение:

```cpp
// Ваш код находится в {problem_number}.cpp
```
"""
    
    return template


def create_problem_directory(base_path: str, problem_number: int) -> Path:
    """
    Создает папку для задачи с номером.
    
    Args:
        base_path: Базовый путь к директории с задачами
        problem_number: Номер задачи
        
    Returns:
        Путь к созданной папке
    """
    problem_dir = Path(base_path) / str(problem_number)
    problem_dir.mkdir(exist_ok=True)
    return problem_dir


def move_cpp_file(cpp_file_path: Path, target_dir: Path) -> bool:
    """
    Перемещает .cpp файл в целевую директорию.
    
    Args:
        cpp_file_path: Путь к исходному .cpp файлу
        target_dir: Целевая директория
        
    Returns:
        True если успешно, False при ошибке
    """
    try:
        target_file = target_dir / cpp_file_path.name
        if target_file.exists():
            print(f"  Предупреждение: файл {target_file} уже существует, пропускаем перемещение")
            return False
        
        shutil.move(str(cpp_file_path), str(target_file))
        print(f"  Перемещен: {cpp_file_path.name} -> {target_dir / cpp_file_path.name}")
        return True
    except Exception as e:
        print(f"  Ошибка при перемещении файла {cpp_file_path}: {e}")
        return False


def create_markdown_file(problem_dir: Path, problem_number: int, 
                         description: Optional[str], slug: Optional[str] = None,
                         is_locked: bool = False) -> bool:
    """
    Создает .md файл с условием задачи.
    
    Args:
        problem_dir: Директория задачи
        problem_number: Номер задачи
        description: Текст условия задачи (None для Locked задач без описания)
        slug: Slug задачи (опционально)
        is_locked: Является ли задача Premium
        
    Returns:
        True если успешно, False при ошибке
    """
    md_file = problem_dir / f"{problem_number}.md"
    
    # Если файл уже существует, пропускаем
    if md_file.exists():
        print(f"  Предупреждение: файл {md_file} уже существует, пропускаем создание")
        return False
    
    try:
        if is_locked and not description:
            # Создаем шаблон для Locked задачи
            content = create_locked_problem_template(problem_number, slug)
        else:
            # Создаем .md файл с условием
            title = f"Problem {problem_number}"
            if slug:
                title += f" - {slug.replace('-', ' ').title()}"
            
            leetcode_url = f"https://leetcode.com/problems/{slug}/description/" if slug else ""
            
            content = f"""# {title}

"""
            
            if leetcode_url:
                content += f"[LeetCode Problem]({leetcode_url})\n\n"
            
            if is_locked:
                content += "## Premium Problem (Locked)\n\n"
            
            if description:
                content += f"""## Описание

{description}

"""
            else:
                content += """## Описание

*Не удалось получить описание задачи автоматически.*

"""
            
            content += """## Примеры

```
Входные данные:
Выходные данные:
```

## Ограничения

- 

## Решение

```cpp
// Ваш код находится в {problem_number}.cpp
```
"""
        
        md_file.write_text(content, encoding='utf-8')
        print(f"  Создан: {md_file}")
        return True
        
    except Exception as e:
        print(f"  Ошибка при создании .md файла: {e}")
        return False


def organize_file(cpp_file_path: Path, base_path: str) -> bool:
    """
    Обрабатывает один .cpp файл: создает папку, перемещает файл и получает условие.
    
    Args:
        cpp_file_path: Путь к .cpp файлу
        base_path: Базовый путь к директории с задачами
        
    Returns:
        True если успешно обработано, False при ошибке
    """
    filename = cpp_file_path.name
    problem_number = extract_problem_number(filename)
    
    if problem_number is None:
        print(f"Пропуск {filename}: не удалось извлечь номер задачи")
        return False
    
    is_locked = is_locked_problem(filename)
    
    print(f"\nОбработка: {filename} (задача #{problem_number}, {'Locked' if is_locked else 'обычная'})")
    
    # Создаем папку для задачи
    problem_dir = create_problem_directory(base_path, problem_number)
    
    # Перемещаем .cpp файл
    if not move_cpp_file(cpp_file_path, problem_dir):
        # Если файл уже был перемещен, продолжаем
        pass
    
    # Получаем slug задачи
    slug = None
    if is_locked or True:  # Всегда получаем slug для ссылок
        print(f"  Получение slug для задачи #{problem_number}...")
        slug = get_problem_slug(problem_number)
        if slug:
            print(f"  Найден slug: {slug}")
        else:
            print(f"  Не удалось получить slug для задачи #{problem_number}")
    
    # Получаем условие задачи
    description = None
    
    if is_locked:
        # Для Locked задач пробуем получить с algo.monster
        print(f"  Получение условия с algo.monster...")
        description = get_algo_monster_problem(problem_number, slug)
        if description:
            print(f"  Условие получено с algo.monster")
        else:
            print(f"  Не удалось получить условие с algo.monster, будет создан шаблон")
    else:
        # Для обычных задач получаем с LeetCode
        if slug:
            print(f"  Получение условия с LeetCode...")
            description = get_leetcode_problem_description(slug)
            if description:
                print(f"  Условие получено с LeetCode")
            else:
                print(f"  Не удалось получить условие с LeetCode")
        else:
            print(f"  Пропуск получения условия: slug не найден")
    
    # Создаем .md файл
    create_markdown_file(problem_dir, problem_number, description, slug, is_locked)
    
    return True


def main():
    """
    Основная функция: сканирует .cpp файлы и обрабатывает их.
    """
    print("LeetCode File Organizer")
    print("=" * 50)
    print(f"Директория: {LEETCODE_PROBLEMS_PATH}")
    print()
    
    # Сканируем .cpp файлы
    cpp_files = scan_cpp_files(LEETCODE_PROBLEMS_PATH)
    
    if not cpp_files:
        print("Не найдено .cpp файлов для обработки")
        return
    
    print(f"Найдено .cpp файлов: {len(cpp_files)}")
    print(f"Начинаем обработку...\n")
    
    # Обрабатываем каждый файл
    processed = 0
    failed = 0
    
    for cpp_file in cpp_files:
        try:
            if organize_file(cpp_file, LEETCODE_PROBLEMS_PATH):
                processed += 1
            else:
                failed += 1
            # Задержка между запросами для избежания rate limiting
            time.sleep(2)
        except Exception as e:
            print(f"Ошибка при обработке {cpp_file}: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"Обработка завершена!")
    print(f"Успешно обработано: {processed}")
    print(f"Ошибок: {failed}")


if __name__ == "__main__":
    main()
