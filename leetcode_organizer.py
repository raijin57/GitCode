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
    """
    Специфический парсер для структуры algo.monster/liteproblems.
    Пытается привести данные к тому же формату, что и LeetCode.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # В liteproblems основной контент обычно в теге <article> или основном контейнере
    content_area = soup.find('article') or soup.find('main')
    if not content_area:
        return None

    result = {
        "description": "",
        "examples": [],
        "constraints": [],
        "images": []
    }

    # Ищем описание (все до первого заголовка Example)
    description_parts = []
    found_example = False
    seen_texts = set()  # Для удаления дубликатов
    
    # Собираем все параграфы и списки
    for elem in content_area.find_all(['p', 'ul', 'ol', 'pre', 'h2', 'h3']):
        text = elem.get_text().strip()
        
        if 'Example' in text and (elem.name in ['h2', 'h3', 'p']):
            found_example = True
            continue
            
        if not found_example:
            if elem.name == 'p':
                # Убираем дубликаты
                if text and text not in seen_texts and len(text) > 10:
                    description_parts.append(text)
                    seen_texts.add(text)
            elif elem.name in ['ul', 'ol']:
                items_text = "\n".join([f"- {li.get_text().strip()}" for li in elem.find_all('li')])
                # Убираем дубликаты списков
                if items_text and items_text not in seen_texts:
                    description_parts.append(items_text)
                    seen_texts.add(items_text)
        
        # Парсим примеры, если они в блоках <pre>
        if found_example and elem.name == 'pre':
            # Пытаемся разделить Input/Output если они внутри одного pre
            raw_pre = elem.get_text().strip()
            example = {"input": "", "output": "", "explanation": ""}
            
            if "Input:" in raw_pre:
                parts = raw_pre.split("Output:")
                example["input"] = parts[0].replace("Input:", "").strip()
                if len(parts) > 1:
                    if "Explanation:" in parts[1]:
                        sub_parts = parts[1].split("Explanation:")
                        example["output"] = sub_parts[0].strip()
                        example["explanation"] = sub_parts[1].strip()
                    else:
                        example["output"] = parts[1].strip()
            
            if example["input"] or example["output"]:
                result["examples"].append(example)

        # Ограничения (обычно в конце)
        if 'Constraints' in text:
            ul = elem.find_next('ul')
            if ul:
                result["constraints"] = [li.get_text().strip() for li in ul.find_all('li')]

    result["description"] = "\n\n".join(description_parts)
    return result

def get_algo_monster_problem(problem_number: int, slug: Optional[str] = None) -> Optional[dict]:
    """
    Получает данные Premium задачи с algo.monster/liteproblems.
    Возвращает словарь (как parse_leetcode_html_content), а не просто текст.
    """
    urls_to_try = [
        f"https://algo.monster/liteproblems/{problem_number}",
        f"https://algo.monster/problems/leetcode-{problem_number}",
    ]
    if slug:
        urls_to_try.insert(0, f"https://algo.monster/liteproblems/{slug}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    for url in urls_to_try:
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                print(f"  Успешно открыт URL: {url}")
                parsed_data = parse_algo_monster_content(response.text)
                if parsed_data and (parsed_data["description"] or parsed_data["examples"]):
                    return parsed_data
        except Exception as e:
            continue
            
    return None


def parse_leetcode_html_content(html_content: str) -> dict:
    """
    Парсит HTML контент задачи LeetCode.
    Версия 'Nuclear': сохраняет всё (фото, таблицы), удаляя только примеры и ограничения.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    result = {
        "description": "",
        "examples": [],
        "constraints": [],
        "images": []
    }
    
    # --- ЭТАП 1: Подготовка контента (превращаем теги в текст) ---

    # 1. Картинки -> Markdown
    # Сохраняем ссылки на изображения, но не заменяем их сразу
    # Заменим их позже, после извлечения примеров
    all_images = []
    for img in soup.find_all('img'):
        src = img.get('src', '')
        if src:
            if src.startswith('/'):
                src = f"https://leetcode.com{src}"
            elif not src.startswith('http'):
                src = f"https://leetcode.com/{src}"
            all_images.append((img, src))
            result["images"].append(src)

    # 2. Форматирование -> Markdown
    # Код
    for code in soup.find_all('code'):
        code.replace_with(f" `{code.get_text().strip()}` ")
    
    # Жирный текст
    for strong in soup.find_all(['strong', 'b']):
        strong.replace_with(f" **{strong.get_text().strip()}** ")
        
    # Курсив
    for em in soup.find_all(['em', 'i']):
        em.replace_with(f" *{em.get_text().strip()}* ")
        
    # Списки (превращаем li в текст с дефисом)
    for li in soup.find_all('li'):
        # Если li еще не обработан (например, не удален в ограничениях)
        li.insert_before("- ")

    # Степени и индексы
    for sup in soup.find_all('sup'):
        sup.replace_with(f"^{sup.get_text().strip()}")
    for sub in soup.find_all('sub'):
        sub.replace_with(f"_{sub.get_text().strip()}")

    # --- ЭТАП 2: Извлечение и УДАЛЕНИЕ специальных блоков ---

    # 1. Примеры (обычно в <pre>)
    # Сначала извлекаем изображения, которые могут быть связаны с примерами
    pre_tags = soup.find_all('pre')
    for pre in pre_tags:
        text = pre.get_text(separator='\n').strip()
        if 'Input:' in text or 'Output:' in text:
            example = {}
            input_idx = text.find('Input:')
            output_idx = text.find('Output:')
            expl_idx = text.find('Explanation:')
            
            if input_idx != -1:
                end = output_idx if output_idx != -1 else len(text)
                example["input"] = text[input_idx + 6:end].strip()
            
            if output_idx != -1:
                end = expl_idx if expl_idx != -1 else len(text)
                example["output"] = text[output_idx + 7:end].strip()
                
            if expl_idx != -1:
                example["explanation"] = text[expl_idx + 12:].strip()
            
            # Очищаем артефакты форматирования из примеров
            for key in ["input", "output", "explanation"]:
                if key in example:
                    # Убираем артефакты типа "** " в начале и конце
                    example[key] = re.sub(r'^\s*\*\*\s+', '', example[key])
                    example[key] = re.sub(r'\s+\*\*\s*$', '', example[key])
                    example[key] = re.sub(r'^\s*\*\s+', '', example[key])
                    example[key] = re.sub(r'\s+\*\s*$', '', example[key])
                    # Убираем множественные пробелы
                    example[key] = re.sub(r'\s+', ' ', example[key]).strip()
            
            # Проверяем, есть ли изображение рядом с этим примером
            # Ищем изображения в том же контексте, что и пример
            example_images = []
            
            # Ищем изображения перед pre (в предыдущих siblings или в родителе)
            # Сначала проверяем предыдущие siblings
            prev_sibling = pre.find_previous_sibling()
            while prev_sibling:
                # Если нашли img, добавляем его
                if prev_sibling.name == 'img':
                    src = prev_sibling.get('src', '')
                    if src:
                        if src.startswith('/'):
                            src = f"https://leetcode.com{src}"
                        elif not src.startswith('http'):
                            src = f"https://leetcode.com/{src}"
                        example_images.append(src)
                        if src in result["images"]:
                            result["images"].remove(src)
                        prev_sibling.decompose()
                        break
                # Если нашли другой pre или заголовок Example, останавливаемся
                if prev_sibling.name in ['pre', 'h2', 'h3'] or 'Example' in prev_sibling.get_text():
                    break
                prev_sibling = prev_sibling.find_previous_sibling()
            
            # Также проверяем родительский элемент на наличие img
            parent = pre.find_parent()
            if parent:
                # Ищем img в родителе, которые находятся между этим pre и предыдущим
                all_imgs = parent.find_all('img')
                for img in all_imgs:
                    # Проверяем, находится ли img между предыдущим pre и текущим
                    prev_pre = pre.find_previous('pre')
                    if (prev_pre is None or img.find_previous('pre') == prev_pre) and img.find_next('pre') == pre:
                        src = img.get('src', '')
                        if src:
                            if src.startswith('/'):
                                src = f"https://leetcode.com{src}"
                            elif not src.startswith('http'):
                                src = f"https://leetcode.com/{src}"
                            if src not in example_images:
                                example_images.append(src)
                            if src in result["images"]:
                                result["images"].remove(src)
                            img.decompose()
            
            if example_images:
                example["images"] = example_images
                # Удаляем эти изображения из общего списка и из soup
                for img_src in example_images:
                    if img_src in result["images"]:
                        result["images"].remove(img_src)
                    # Находим и удаляем соответствующий img тег из soup
                    for img_tag, saved_src in all_images:
                        if saved_src == img_src and img_tag in soup:
                            img_tag.decompose()
            
            if example:
                result["examples"].append(example)
                
            # Удаляем сам блок примера из дерева
            # Также пытаемся удалить заголовок "Example 1:", если он есть перед pre
            previous = pre.find_previous_sibling()
            if previous and 'Example' in previous.get_text():
                previous.decompose()
            pre.decompose()
    
    # Теперь заменяем оставшиеся изображения (которые не связаны с примерами) на markdown
    for img_tag, src in all_images:
        if img_tag in soup:  # Если изображение еще не удалено
            img_tag.replace_with(f"\n\n![Image]({src})\n\n")

    # 2. Ограничения
    # Ищем блок ограничений и удаляем его
    constraints_header = None
    for elem in soup.find_all(['p', 'strong', 'h3', 'div']):
        if 'Constraint' in elem.get_text():
            constraints_header = elem
            break
            
    if constraints_header:
        ul_constraints = constraints_header.find_next('ul')
        if ul_constraints:
            for li in ul_constraints.find_all('li'):
                cons_text = li.get_text(separator=' ', strip=True)
                # Чистим артефакты ("- " который мы добавили выше)
                cons_text = cons_text.replace("- ", "", 1).strip()
                # Фиксы форматирования
                cons_text = re.sub(r'(\d)\s+\^', r'\1^', cons_text)
                cons_text = re.sub(r'(\w)\s+\[\s+(\w)\s+\]', r'\1[\2]', cons_text)
                result["constraints"].append(cons_text)
            ul_constraints.decompose()
        
        # Удаляем сам заголовок Constraints
        constraints_header.decompose()

    # --- ЭТАП 3: Всё, что осталось — это описание ---
    
    # Теперь soup содержит только описание и картинки, так как
    # примеры и ограничения мы удалили (.decompose())
    
    # Используем separator=' ' чтобы слова не разбивались на отдельные строки
    raw_desc = soup.get_text(separator=' ', strip=True)
    
    # Финальная чистка текста
    # Нормализуем пробелы
    raw_desc = re.sub(r'\s+', ' ', raw_desc)
    # Разбиваем на параграфы по двойным переносам строк (если они были в оригинале)
    # Но сначала нужно сохранить структуру параграфов
    
    # Лучший подход: извлекаем текст из каждого параграфа отдельно
    description_parts = []
    for p in soup.find_all(['p', 'div']):
        p_text = p.get_text(separator=' ', strip=True)
        if p_text and len(p_text) > 3:
            # Проверяем, не является ли это изображением (уже обработанным)
            if not p_text.startswith('!['):
                # Нормализуем пробелы
                p_text = re.sub(r'\s+', ' ', p_text)
                description_parts.append(p_text)
    
    # Если не нашли параграфы, используем весь текст
    if not description_parts:
        raw_desc = soup.get_text(separator=' ', strip=True)
        raw_desc = re.sub(r'\s+', ' ', raw_desc)
        description_parts = [raw_desc] if raw_desc else []
    
    # Собираем обратно, разделяя параграфы
    result["description"] = "\n\n".join(description_parts)
    
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
    
    # Примеры
    content += "## 💡 Примеры\n\n"
    if parsed_content.get("examples"):
        for i, example in enumerate(parsed_content["examples"], 1):
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
    else:
        # Пустой шаблон, если примеры не спарсились
        content += "```\n"
        content += "Входные данные:\n"
        content += "Выходные данные:\n"
        content += "```\n\n"
    
    # Ограничения
    content += "## ⚠️ Ограничения\n\n"
    if parsed_content.get("constraints"):
        for constraint in parsed_content["constraints"]:
            content += f"- {constraint}\n"
    else:
        content += "- \n"
    
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
