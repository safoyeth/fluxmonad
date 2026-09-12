# FluxMonad

[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Typing](https://img.shields.io/badge/typing-strict-green.svg)](https://mypy.readthedocs.io/)
[![Tests](https://img.shields.io/badge/tests-106%20passed-brightgreen.svg)](tests/)

**[English](README.md)** | **[Русский](README_RU.md)**

> Высокопроизводительная библиотека ленивой потоковой обработки данных для Python, объединяющая формальные законы монад, декларативные конструкторы запросов и оптимизатор планов выполнения на базе AST.

---

## 🚀 Ключевые возможности

- **⚡ Потоковая обработка с константной памятью ($O(1)$ RAM)**: Обработка миллионов записей или бесконечных потоков с минимальным потреблением оперативной памяти.
- **🧠 Оптимизатор на базе правил (Rule-Based Optimizer, RBO)**: Поддержка **проталкивания предикатов (Predicate Pushdown)** и **слияния узлов (Node Fusion)**, перемещающих фильтры перед ресурсоемкими вычислениями для ускорения выполнения до **54%+ по CPU**.
- **💎 Честная монадическая композиция**: Полное соответствие законам монад из теории категорий (Left Identity, Right Identity, Associativity). Поддержка оператора связывания `>>` (Haskell-style `>>=` / `flatMap`).
- **🔍 Выразительный DSL для запросов**: Запросы с использованием перегрузки операторов (`Field("age") >= 18`) или синтаксиса Django lookups (`Q(salary__gte=50000)`).
- **🌐 Универсальный и глубокий доступ к свойствам**: Чтение словарей, объектов, dataclass и вложенных структур по строковым путям (`"user.address.city"`) и рекурсивный поиск (`"..key"`).
- **📂 Универсальный ввод/вывод (I/O)**: Встроенные потоковые загрузчики и сериализаторы для **CSV, JSON, NDJSON/JSON Lines, YAML, TOML и Excel (.xlsx)**, а также бесшовная интеграция с **Pandas**.
- **⚡ Параллелизм и асинхронность**: Многопоточный и многопроцессорный маппинг (`parallel_map`), а также встроенная поддержка `async for` и `await collect_async()`.
- **📊 Диагностика и телеметрия**: Визуализация планов выполнения с помощью `.explain()` и профилирование пропускной способности каждого шага с `.profile()`.

---

## 📊 Бенчмарки (1 000 000 записей)

Замеры проведены с использованием `tracemalloc` и `time.perf_counter` на 1 000 000 записей ([скрипт бенчмарка](benchmarks/benchmarks.py)):

| Сценарий | Чистый Python / `itertools` | FluxMonad | Использование памяти | Сравнение |
| :--- | :--- | :--- | :--- | :--- |
| **Stream ETL + Early Stop** <br> `Filter -> Map -> Take(10k)` | 0.1065 с | 0.1596 с | 2.60 МБ vs 2.62 МБ | Сопоставимая скорость при полной инкапсуляции |
| **Heavy Projection + Filter** <br> `Extend -> When(Predicate)` | 0.8852 с | **0.4065 с** | 2.91 МБ vs 2.90 МБ | **⚡ На 54.1% быстрее** (благодаря Predicate Pushdown) |
| **Full Stream Reduction** <br> `Sum по 1 000 000 строк` | 2.7208 с | 2.8061 с | 0.00 МБ vs 0.01 МБ | $O(1)$ потребление памяти |

---

## 📦 Установка

```bash
pip install fluxmonad
```

Для поддержки форматов YAML, Excel и TOML:

```bash
pip install "fluxmonad[all]"
```

---

## ⚡ Быстрый старт

```python
from fluxmonad import Flux, Field, Q

# 1. Создание ленивого пайплайна из коллекции или файла
users = [
    {"name": "Alice", "age": 28, "role": "engineer", "salary": 95000},
    {"name": "Bob", "age": 17, "role": "intern", "salary": 30000},
    {"name": "Charlie", "age": 35, "role": "manager", "salary": 120000},
    {"name": "Diana", "age": 31, "role": "engineer", "salary": 105000},
]

pipeline = (
    Flux(users)
    .when(Field("age") >= 18)                              # Фильтрация выражением
    .when(Q(role="engineer") | Q(salary__gte=100000))      # Фильтр в стиле Django Q
    .extend("bonus", lambda r: r["salary"] * 0.15)         # Вычисляемое поле
    .sortby("-salary")                                     # Сортировка по убыванию
    .select("name", "salary", "bonus")                     # Проекция полей
)

# 2. Инспекция плана выполнения
print(pipeline.explain(optimized=True))

# 3. Потоковая итерация или сбор результатов
for record in pipeline:
    print(record)
# Вывод:
# {'name': 'Charlie', 'salary': 120000, 'bonus': 18000.0}
# {'name': 'Diana', 'salary': 105000, 'bonus': 15750.0}
# {'name': 'Alice', 'salary': 95000, 'bonus': 14250.0}
```

---

## 💡 Основные возможности

### 1. Монадический пайплайн (`>>`)

`Flux` реализует стандартные законы монад и поддерживает оператор сдвига вправо `>>` как алиас для `bind` (flatMap):

```python
# Монадический bind: разворачивание и трансформация элементов
stream = (
    Flux(["apple,banana", "cherry,date"])
    >> (lambda line: Flux(line.split(",")))
    >> (lambda fruit: Flux([fruit.upper()]))
)

print(stream.collect())
# ['APPLE', 'BANANA', 'CHERRY', 'DATE']
```

### 2. Оптимизатор RBO и проталкивание предикатов (Predicate Pushdown)

FluxMonad анализирует зависимости полей в фильтрах. Если предикат фильтрации не зависит от колонок, создаваемых предшествующими `extend()` или `map()`, оптимизатор **перемещает фильтр выше по графу**, отсекая лишние записи до выполнения затратных вычислений:

```python
pipeline = (
    Flux.from_json("massive_dataset.json")
    .extend("expensive_hash", lambda r: heavy_crypto_calc(r))
    .when(Field("status") == "active")  # <-- Автоматически проталкивается ДО extend()!
    .take(100)                          # <-- Объединяется с ограничениями потока!
)

# Просмотр реорганизованного графа выполнения
print(pipeline.explain(optimized=True))
```

### 3. Декларативная фильтрация: `Field` и `Q`

Построение сложных логических условий с использованием перегрузки операторов или синтаксиса Django:

```python
from fluxmonad import Field, Q

# Синтаксис перегрузки операторов:
expr1 = (Field("age") >= 21) & (Field("country") == "US")
expr2 = Field("tags").contains("vip") | Field("score").is_in([90, 95, 100])

# Синтаксис Django-style Q:
expr3 = Q(age__gte=21, country="US") | Q(status__in=["priority", "verified"])

Flux(records).when(expr1 & expr3).to_list()
```

### 4. Реляционные соединения (Joins) и операции над множествами

Объединение независимых потоков `Flux` с помощью хеш-соединений в памяти с минимальными накладными расходами:

```python
users = Flux([{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}])
orders = Flux([{"user_id": 1, "total": 250}, {"user_id": 1, "total": 45}])

# Inner, Left, Right, Full или Cross join:
joined = users.left_join(orders, left_on="id", right_on="user_id").collect()
```

Операции над множествами:
```python
flux_a.union(flux_b)         # Конкатенация потоков
flux_a.intersection(flux_b)  # Общие элементы
flux_a.difference(flux_b)    # Элементы из A, отсутствующие в B
```

### 5. Оконные функции и последовательный анализ

Вычисление аналитических оконных функций над потоками без необходимости загружать весь датасет целиком:

```python
Flux(sales_data) \
    .enumerate(start=1, field="row_num") \
    .cumulative_sum("amount", target_field="running_total") \
    .lag("amount", offset=1, target_field="prev_amount") \
    .lead("amount", offset=1, target_field="next_amount") \
    .to_list()
```

### 6. Потоковые форматы файлов (I/O)

```python
# Чтение из любого формата:
stream = Flux.from_file("input.csv")  # Автоопределение: .csv, .json, .yaml, .toml, .xlsx

# Сохранение потока напрямую в требуемый формат:
stream.to_csv("output.csv")
stream.to_json("output.jsonl", lines=True)
stream.to_yaml("output.yaml")
stream.to_toml("output.toml")
stream.to_excel("output.xlsx", sheet_name="Report")
```

---

## 📖 Каталог документации

- [Архитектура и внутреннее устройство](docs/architecture_ru.md): Граф выполнения, законы монад и модели работы с памятью.
- [Оптимизация и проталкивание предикатов](docs/optimization_ru.md): Rule-based оптимизатор, слияние узлов и проверка безопасности зависимостей.
- [Бенчмарки производительности](docs/benchmarks_ru.md): Методология измерений, телеметрия `tracemalloc` и показатели масштабируемости.
- [Полный справочник API](docs/api_reference_ru.md): Все методы `Flux`, параметры, операторы и выражения.

---

## 🛠 Тестирование и строгая типизация

Библиотека полностью протестирована и поддерживает строгую статическую типизацию:

```bash
# Запуск тестов (106 тестов)
pytest

# Строгая проверка типов mypy
mypy src
```

---

## 📄 Лицензия

MIT License © 2026 Safoyeth
