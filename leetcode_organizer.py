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
LEETCODE_PROBLEMS_PATH = "/home/arsen/CLionProjects/test"


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
    return "locked" in filename.lower()


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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://leetcode.com/problemset/",
        "Origin": "https://leetcode.com"
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
    Получает условие задачи с LeetCode через GraphQL API.
    
    Args:
        slug: Slug задачи (например, "two-sum")
        
    Returns:
        Текст условия задачи или None при ошибке
    """
    graphql_url = "https://leetcode.com/graphql/"
    
    # GraphQL запрос для получения полного описания задачи
    query = """
    query questionContent($titleSlug: String!) {
      question(titleSlug: $titleSlug) {
        content
        mysqlSchemas
        dataSchemas
      }
    }
    """
    
    variables = {
        "titleSlug": slug
    }
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": f"https://leetcode.com/problems/{slug}/",
        "Origin": "https://leetcode.com"
    }
    
    try:
        response = requests.post(
            graphql_url,
            json={"query": query, "variables": variables},
            headers=headers,
            timeout=10
        )
        
        if response.status_code != 200:
            print(f"Ошибка при запросе к GraphQL API: {response.status_code}")
            return None
        
        data = response.json()
        
        if "errors" in data:
            print(f"Ошибка GraphQL: {data['errors']}")
            return None
        
        question_data = data.get("data", {}).get("question")
        if not question_data:
            print(f"Не найдены данные задачи для slug: {slug}")
            return None
        
        content = question_data.get("content")
        if not content:
            print(f"Не найдено описание для slug: {slug}")
            return None
        
        # Возвращаем HTML контент для дальнейшего парсинга
        return content
            
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе к GraphQL API: {e}")
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


def parse_leetcode_html_content(html_content: str) -> dict:
    """
    Парсит HTML контент задачи LeetCode и извлекает структурированную информацию.
    
    Args:
        html_content: HTML контент задачи
        
    Returns:
        Словарь с ключами: description, examples, constraints, images
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    result = {
        "description": "",
        "examples": [],
        "constraints": [],
        "images": []
    }
    
    # Извлекаем изображения
    for img in soup.find_all('img'):
        src = img.get('src', '')
        if src:
            # Преобразуем относительные URL в абсолютные
            if src.startswith('/'):
                src = f"https://leetcode.com{src}"
            elif not src.startswith('http'):
                src = f"https://leetcode.com/{src}"
            result["images"].append(src)
    
    # Находим все элементы для правильного извлечения
    all_elements = soup.find_all(['p', 'ul', 'ol', 'pre', 'strong'])
    
    # Ищем начало примеров и ограничений
    example_start = None
    constraints_start = None
    
    for elem in all_elements:
        text = elem.get_text(strip=True)
        if re.match(r'Example\s+\d+', text, re.I) and example_start is None:
            example_start = elem
        if 'Constraint' in text and constraints_start is None:
            constraints_start = elem
    
    # Вспомогательная функция для извлечения текста с сохранением форматирования
    def extract_text_with_formatting(elem):
        """Извлекает текст с сохранением пробелов и математических обозначений"""
        if elem is None:
            return ""
        
        # Обрабатываем sup теги (степени) - заменяем на ^
        for sup in elem.find_all('sup'):
            sup_text = sup.get_text(strip=True)
            sup.replace_with(f"^{sup_text}")
        
        # Обрабатываем sub теги
        for sub in elem.find_all('sub'):
            sub_text = sub.get_text(strip=True)
            sub.replace_with(f"_{sub_text}")
        
        # Извлекаем текст с пробелами между элементами
        text = elem.get_text(separator=' ', strip=True)
        # Нормализуем множественные пробелы
        text = re.sub(r'\s+', ' ', text)
        return text
    
    # Извлекаем описание (все до примеров)
    description_parts = []
    for elem in soup.find_all(['p', 'ul', 'ol']):
        # Проверяем, не является ли это частью примеров или ограничений
        elem_text = extract_text_with_formatting(elem)
        if 'Example' in elem_text or (example_start and elem == example_start):
            break
        if 'Constraint' in elem_text or (constraints_start and elem == constraints_start):
            break
        
        if elem.name == 'p':
            text = extract_text_with_formatting(elem)
            if text and len(text) > 3:
                description_parts.append(text)
        elif elem.name in ['ul', 'ol']:
            items = []
            for li in elem.find_all('li'):
                item_text = extract_text_with_formatting(li)
                if item_text:
                    items.append(item_text)
            if items:
                description_parts.append("\n".join([f"- {item}" for item in items]))
    
    result["description"] = "\n\n".join(description_parts)
    
    # Извлекаем примеры - более надежный способ
    example_pattern = re.compile(r'Example\s+(\d+)', re.I)
    
    # Ищем все параграфы с примерами
    all_ps = soup.find_all('p')
    i = 0
    while i < len(all_ps):
        p = all_ps[i]
        text = extract_text_with_formatting(p)
        
        # Нашли начало примера
        if example_pattern.search(text):
            example = {}
            example_num = example_pattern.search(text).group(1)
            
            # Ищем Input, Output, Explanation в следующих элементах
            j = i + 1
            while j < len(all_ps) and j < i + 15:
                next_p = all_ps[j]
                next_text = extract_text_with_formatting(next_p)
                
                # Проверяем, не начался ли новый пример или ограничения
                if example_pattern.search(next_text) or 'Constraint' in next_text:
                    break
                
                # Input
                if 'Input' in next_text and 'input' not in example:
                    # Ищем следующий <pre> или код в том же параграфе
                    pre = next_p.find_next('pre')
                    if pre:
                        example["input"] = pre.get_text(strip=True)
                    else:
                        # Может быть в самом параграфе после "Input:"
                        input_match = re.search(r'Input:\s*(.+)', next_text, re.I)
                        if input_match:
                            example["input"] = input_match.group(1).strip()
                
                # Output
                elif 'Output' in next_text and 'output' not in example:
                    pre = next_p.find_next('pre')
                    if pre:
                        example["output"] = pre.get_text(strip=True)
                    else:
                        output_match = re.search(r'Output:\s*(.+)', next_text, re.I)
                        if output_match:
                            example["output"] = output_match.group(1).strip()
                
                # Explanation
                elif 'Explanation' in next_text and 'explanation' not in example:
                    expl_parts = []
                    k = j + 1
                    while k < len(all_ps) and k < j + 5:
                        expl_p = all_ps[k]
                        expl_text = extract_text_with_formatting(expl_p)
                        if 'Example' in expl_text or 'Constraint' in expl_text or 'Input' in expl_text or 'Output' in expl_text:
                            break
                        if expl_text:
                            expl_parts.append(expl_text)
                        k += 1
                    if expl_parts:
                        example["explanation"] = " ".join(expl_parts)
                    else:
                        # Может быть в самом параграфе
                        expl_match = re.search(r'Explanation:\s*(.+)', next_text, re.I)
                        if expl_match:
                            example["explanation"] = expl_match.group(1).strip()
                
                j += 1
            
            if example:
                result["examples"].append(example)
            i = j - 1
        
        i += 1
    
    # Извлекаем ограничения с сохранением форматирования
    for p in all_ps:
        text = extract_text_with_formatting(p)
        if 'Constraint' in text:
            # Ищем следующий <ul>
            ul = p.find_next('ul')
            if ul:
                for li in ul.find_all('li'):
                    constraint_text = extract_text_with_formatting(li)
                    if constraint_text:
                        result["constraints"].append(constraint_text)
                break
    
    # Если не нашли через параграфы, ищем через strong
    if not result["constraints"]:
        for strong in soup.find_all('strong'):
            if 'Constraint' in extract_text_with_formatting(strong):
                ul = strong.find_next('ul')
                if ul:
                    for li in ul.find_all('li'):
                        constraint_text = extract_text_with_formatting(li)
                        if constraint_text:
                            result["constraints"].append(constraint_text)
                    break
    
    return result


def format_markdown_content(problem_number: int, slug: Optional[str], 
                            parsed_content: dict, is_locked: bool = False) -> str:
    """
    Форматирует структурированные данные в красивый markdown.
    
    Args:
        problem_number: Номер задачи
        slug: Slug задачи
        parsed_content: Словарь с parsed данными
        is_locked: Является ли задача Premium
        
    Returns:
        Отформатированный markdown текст
    """
    title = f"Problem {problem_number}"
    if slug:
        # Преобразуем slug в читаемое название
        title_parts = slug.replace('-', ' ').title().split()
        title += f" - {' '.join(title_parts)}"
    
    content = f"# {title}\n\n"
    
    # Ссылка на LeetCode
    if slug:
        leetcode_url = f"https://leetcode.com/problems/{slug}/description/"
        content += f"[🔗 LeetCode Problem]({leetcode_url})\n\n"
    
    if is_locked:
        content += "> **Premium Problem (Locked)**\n\n"
        content += "Эта задача доступна только с LeetCode Premium подпиской.\n\n"
    
    # Описание
    if parsed_content.get("description"):
        content += "## 📝 Описание\n\n"
        description = parsed_content["description"]
        
        # Улучшаем форматирование описания
        # Разделяем на параграфы и форматируем
        lines = description.split('\n')
        formatted_lines = []
        in_list = False
        
        for line in lines:
            line = line.strip()
            if not line:
                if in_list:
                    formatted_lines.append("")
                    in_list = False
                continue
            
            # Если строка начинается с "- ", это список
            if line.startswith('- '):
                if not in_list:
                    formatted_lines.append("")
                formatted_lines.append(line)
                in_list = True
            elif line.startswith('```'):
                if in_list:
                    formatted_lines.append("")
                    in_list = False
                formatted_lines.append(line)
            else:
                # Обычный текст - добавляем как параграф
                if in_list:
                    formatted_lines.append("")
                    in_list = False
                formatted_lines.append(line)
        
        # Объединяем параграфы
        formatted_text = '\n'.join(formatted_lines)
        # Убираем множественные пустые строки
        formatted_text = re.sub(r'\n{3,}', '\n\n', formatted_text)
        
        content += formatted_text
        content += "\n\n"
    else:
        content += "## 📝 Описание\n\n"
        content += "*Не удалось получить описание задачи автоматически.*\n\n"
    
    # Изображения
    if parsed_content.get("images"):
        content += "## 🖼️ Изображения\n\n"
        for img_url in parsed_content["images"]:
            content += f"![Image]({img_url})\n\n"
    
    # Примеры
    if parsed_content.get("examples"):
        content += "## 💡 Примеры\n\n"
        for i, example in enumerate(parsed_content["examples"], 1):
            content += f"### Пример {i}\n\n"
            
            if example.get("input"):
                content += "**Входные данные:**\n\n"
                content += "```\n"
                content += example["input"]
                content += "\n```\n\n"
            
            if example.get("output"):
                content += "**Выходные данные:**\n\n"
                content += "```\n"
                content += example["output"]
                content += "\n```\n\n"
            
            if example.get("explanation"):
                content += "**Объяснение:**\n\n"
                content += f"{example['explanation']}\n\n"
            
            content += "---\n\n"
    else:
        content += "## 💡 Примеры\n\n"
        content += "```\n"
        content += "Входные данные:\n"
        content += "Выходные данные:\n"
        content += "```\n\n"
    
    # Ограничения
    if parsed_content.get("constraints"):
        content += "## ⚠️ Ограничения\n\n"
        for constraint in parsed_content["constraints"]:
            content += f"- {constraint}\n"
        content += "\n"
    else:
        content += "## ⚠️ Ограничения\n\n"
        content += "- \n\n"
    
    return content


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
        description: HTML контент условия задачи (None для Locked задач без описания)
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
            # Парсим HTML контент
            if description:
                parsed_content = parse_leetcode_html_content(description)
            else:
                parsed_content = {
                    "description": "",
                    "examples": [],
                    "constraints": [],
                    "images": []
                }
            
            # Форматируем в markdown
            content = format_markdown_content(problem_number, slug, parsed_content, is_locked)
        
        md_file.write_text(content, encoding='utf-8')
        print(f"  Создан: {md_file}")
        return True
        
    except Exception as e:
        print(f"  Ошибка при создании .md файла: {e}")
        import traceback
        traceback.print_exc()
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
