#!/usr/bin/env python3
"""
LeetCode File Organizer

Автоматически организует .cpp файлы из LeetCodeProblems:
- Создает папки с номерами задач
- Перемещает .cpp файлы в соответствующие папки
- Получает условия задач с LeetCode и algo.monster
"""

import re
import shutil
import time
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from typing import Optional


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


def parse_algo_monster_content(html_content: str) -> Optional[dict]:
    soup = BeautifulSoup(html_content, 'html.parser')
    content_area = soup.find('article')
    if not content_area: return None

    result = {"description": "", "examples": [], "constraints": [], "images": []}

    # 1. Спец-теги и форматирование (как в LeetCode)
    for sup in content_area.find_all('sup'):
        sup.replace_with(f"^{sup.get_text().strip()}")
    for sub in content_area.find_all('sub'):
        sub.replace_with(f"_{sub.get_text().strip()}")
    for code in content_area.find_all('code'):
        code.replace_with(f" `{code.get_text().strip()}` ")
    for strong in content_area.find_all(['strong', 'b']):
        strong.replace_with(f" **{strong.get_text().strip()}** ")

    # 2. Парсинг контента
    description_parts = []
    found_stop = False
    
    for elem in content_area.find_all(['p', 'ul', 'ol', 'pre', 'h2', 'h3']):
        txt_lower = elem.get_text().lower()
        if any(x in txt_lower for x in ['example', 'solution', 'approach', 'constraints']):
            found_stop = True
            
        if not found_stop:
            if elem.name == 'p':
                t = elem.get_text(separator='', strip=True)
                t = re.sub(r'[ \t]+', ' ', t)
                if t: description_parts.append(t)
            elif elem.name in ['ul', 'ol']:
                items = [f"- {li.get_text(separator='', strip=True)}" for li in elem.find_all('li')]
                description_parts.append("\n".join(items))

        # Примеры
        if found_stop and elem.name == 'pre':
            raw = elem.get_text().strip()
            if "Input:" in raw or "Output:" in raw:
                ex = {}
                in_m = re.search(r'Input:\s*(.*?)(?=Output:|$)', raw, re.DOTALL)
                out_m = re.search(r'Output:\s*(.*?)(?=Explanation:|$)', raw, re.DOTALL)
                if in_m: ex["input"] = in_m.group(1).strip()
                if out_m: ex["output"] = out_m.group(1).strip()
                if ex not in result["examples"]: result["examples"].append(ex)

    # Чистим степени и склеиваем
    desc = "\n\n".join(description_parts)
    desc = re.sub(r'(\d)\s*\^\s*(\d+)', r'\1^\2', desc)
    result["description"] = desc
    return result

def get_algo_monster_problem(problem_number: int, slug: Optional[str] = None) -> Optional[dict]:
    """
    Загружает Premium задачу с AlgoMonster Lite.
    """
    # Сначала пробуем по номеру, потом по слагу
    urls = [f"https://algo.monster/liteproblems/{problem_number}"]
    if slug:
        urls.insert(0, f"https://algo.monster/liteproblems/{slug}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    for url in urls:
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = parse_algo_monster_content(response.text)
                if data and (data["description"] or data["examples"]):
                    return data
        except Exception:
            continue
    return None


def parse_leetcode_html_content(html_content: str) -> dict:
    soup = BeautifulSoup(html_content, 'html.parser')
    result = {"description": "", "examples": [], "constraints": [], "images": []}

    # --- 1. ПРЕДОБРАБОТКА ТЕГОВ ---
    # Степени и индексы (строго без пробелов)
    for sup in soup.find_all('sup'):
        sup.replace_with(f"^{sup.get_text().strip()}")
    for sub in soup.find_all('sub'):
        sub.replace_with(f"_{sub.get_text().strip()}")

    # Форматирование (добавляем ОДИН пробел по краям для предотвращения склейки)
    for code in soup.find_all('code'):
        code.replace_with(f" `{code.get_text().strip()}` ")
    for strong in soup.find_all(['strong', 'b']):
        strong.replace_with(f" **{strong.get_text().strip()}** ")
    for em in soup.find_all(['em', 'i']):
        em.replace_with(f" *{em.get_text().strip()}* ")

    # Картинки
    for img in soup.find_all('img'):
        src = img.get('src', '')
        if src:
            if src.startswith('/'): src = f"https://leetcode.com{src}"
            elif not src.startswith('http'): src = f"https://leetcode.com/{src}"
            img.replace_with(f"\n\n![Image]({src})\n\n")

    # --- 2. ПРИМЕРЫ (Извлекаем ДО чистки описания) ---
    for pre in soup.find_all('pre'):
        # Для примеров берем текст как есть, чтобы не было лишних звезд
        raw_text = pre.get_text().strip()
        if 'Input:' in raw_text or 'Output:' in raw_text:
            example = {}
            # Используем регулярные выражения для чистого извлечения
            input_m = re.search(r'Input:\s*(.*?)(?=Output:|$)', raw_text, re.DOTALL)
            output_m = re.search(r'Output:\s*(.*?)(?=Explanation:|$)', raw_text, re.DOTALL)
            expl_m = re.search(r'Explanation:\s*(.*)', raw_text, re.DOTALL)
            
            if input_m: example["input"] = input_m.group(1).strip()
            if output_m: example["output"] = output_m.group(1).strip()
            if expl_m: example["explanation"] = expl_m.group(1).strip()
            
            if example: result["examples"].append(example)
            
            # Удаляем заголовок "Example X" перед пре-блоком
            p_sib = pre.find_previous_sibling()
            if p_sib and 'Example' in p_sib.get_text(): p_sib.decompose()
            pre.decompose()

    # --- 3. ОГРАНИЧЕНИЯ ---
    for elem in soup.find_all(['p', 'strong', 'h3', 'h4', 'div']):
        if 'Constraint' in elem.get_text():
            ul = elem.find_next('ul')
            if ul:
                for li in ul.find_all('li'):
                    txt = li.get_text(separator='', strip=True)
                    # Чистим степени в ограничениях: "10 ^ 9" -> "10^9"
                    txt = re.sub(r'(\d)\s*\^\s*(\d+)', r'\1^\2', txt)
                    result["constraints"].append(txt)
                ul.decompose()
            elem.decompose()
            break

    # --- 4. СБОРКА ОПИСАНИЯ ---
    desc_parts = []
    # Берем только элементы верхнего уровня, чтобы избежать дублей
    for child in soup.find_all(['p', 'div', 'ul', 'ol', 'blockquote'], recursive=False):
        # Используем separator='', так как пробелы уже расставлены в шаге 1
        text = child.get_text(separator='', strip=True)
        if not text: continue
        
        if child.name in ['ul', 'ol']:
            items = [f"- {li.get_text(separator='', strip=True)}" for li in child.find_all('li')]
            text = "\n".join(items)
        
        # Финальная чистка: убираем лишние пробелы, но оставляем один между словами
        text = re.sub(r'[ \t]+', ' ', text)
        # Склеиваем степени: "10 ^ 9" -> "10^9"
        text = re.sub(r'(\d)\s*\^\s*(\d+)', r'\1^\2', text)
        desc_parts.append(text)

    result["description"] = "\n\n".join(desc_parts).strip()
    return result


def format_markdown_content(problem_number: int, slug: Optional[str], 
                            parsed_content: dict, is_locked: bool = False) -> str:
    """
    Форматирует структурированные данные в красивый markdown.
    """
    title = f"Problem {problem_number}"
    if slug:
        title_parts = slug.replace('-', ' ').title().split()
        title += f" - {' '.join(title_parts)}"
    
    content = f"# {title}\n\n"
    
    if slug:
        leetcode_url = f"https://leetcode.com/problems/{slug}/description/"
        content += f"[🔗 LeetCode Problem]({leetcode_url})\n\n"
    
    if is_locked:
        content += "> **Premium Problem (Locked)**\n\n"
    
    # Описание
    content += "## 📝 Описание\n\n"
    if parsed_content.get("description"):
        content += parsed_content["description"]
        # Добавляем изображения, которые не связаны с примерами
        if parsed_content.get("images"):
            content += "\n\n"
            for img_url in parsed_content["images"]:
                content += f"![Image]({img_url})\n\n"
    else:
        content += "*Не удалось получить описание задачи автоматически.*"
    content += "\n\n"
    
    # Примеры (только если есть данные)
    examples = parsed_content.get("examples", [])
    if examples:
        content += "## 💡 Примеры\n\n"
        for i, example in enumerate(examples, 1):
            content += f"### Пример {i}\n\n"
            
            # Изображения для этого примера (если есть)
            if example.get("images"):
                for img_url in example["images"]:
                    content += f"![Image]({img_url})\n\n"
            
            if example.get("input"):
                content += "**Входные данные:**\n"
                content += f"```\n{example['input']}\n```\n\n"
            
            if example.get("output"):
                content += "**Выходные данные:**\n"
                content += f"```\n{example['output']}\n```\n\n"
            
            if example.get("explanation"):
                content += "**Объяснение:**\n"
                content += f"{example['explanation']}\n\n"
            
            content += "---\n\n"
    
    # Ограничения (только если есть данные)
    constraints = parsed_content.get("constraints", [])
    if constraints:
        content += "## ⚠️ Ограничения\n\n"
        for constraint in constraints:
            content += f"- {constraint}\n"
        content += "\n"
    
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
                         parsed_content: Optional[dict], slug: Optional[str] = None,
                         is_locked: bool = False) -> bool:
    """
    Создает .md файл с условием задачи.
    
    Args:
        problem_dir: Директория задачи
        problem_number: Номер задачи
        parsed_content: Словарь с распарсенными данными (None для Locked задач без описания)
        slug: Slug задачи (опционально)
        is_locked: Является ли задача Premium
        
    Returns:
        True если успешно, False при ошибке
    """
    md_file = problem_dir / f"{problem_number}.md"
    if md_file.exists(): return False
    
    try:
        if parsed_content:
            # Если данные есть (со словаря LeetCode или AlgoMonster)
            content = format_markdown_content(problem_number, slug, parsed_content, is_locked)
        else:
            # Если данных совсем нет — создаем шаблон-заглушку
            content = create_locked_problem_template(problem_number, slug)
            
        md_file.write_text(content, encoding='utf-8')
        return True
    except Exception as e:
        print(f" Ошибка: {e}")
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
    description_data = None  # Словарь с распарсенными данными
    
    if is_locked:
        # Для Locked задач пробуем получить с algo.monster
        print(f"  Получение условия с algo.monster...")
        description_data = get_algo_monster_problem(problem_number, slug)
        
        if description_data:
            print(f"  Условие получено с algo.monster")
        else:
            print(f"  Не удалось получить данные с algo.monster, будет создан шаблон")
    else:
        # Для обычных задач получаем с LeetCode
        if slug:
            print(f"  Получение условия с LeetCode...")
            html_content = get_leetcode_problem_description(slug)
            if html_content:
                description_data = parse_leetcode_html_content(html_content)
                print(f"  Условие получено с LeetCode")
            else:
                print(f"  Не удалось получить условие с LeetCode")
        else:
            print(f"  Пропуск получения условия: slug не найден")
    
    # Создаем .md файл
    create_markdown_file(problem_dir, problem_number, description_data, slug, is_locked)
    
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
