# Справочник API FluxMonad

**[English](api_reference.md)** | **[Русский](api_reference_ru.md)**

Полный технический справочник по публичным классам, методам и выражениям библиотеки `fluxmonad`.

---

## 1. Класс: `Flux[T]`

Импорт:
```python
from fluxmonad import Flux
```

### 1.1 Загрузка данных и фабричные методы
- **`Flux(source)`**: Конструктор. Принимает любой `Iterable[T]` или узел графа выполнения `Node`.
- **`Flux.from_json(path_or_str, lines=False, encoding="utf-8")`**: Чтение JSON или NDJSON/JSON Lines.
- **`Flux.from_csv(filepath, encoding="utf-8", delimiter=",")`**: Потоковое чтение строк CSV в виде словарей.
- **`Flux.from_yaml(path_or_str, encoding="utf-8")`**: Чтение YAML-файла или сырой строки YAML.
- **`Flux.from_toml(path_or_str, encoding="utf-8")`**: Чтение документов в формате TOML.
- **`Flux.from_excel(filepath, sheet_name=0)`**: Построчное чтение таблиц `.xlsx` через библиотеку `openpyxl`.
- **`Flux.from_pandas(df)`**: Преобразование Pandas DataFrame в потоковый `Flux` словарей без лишнего копирования.
- **`Flux.from_file(filepath)`**: Автоматическое определение формата по расширению файла (`.csv`, `.json`, `.jsonl`, `.yaml`, `.toml`, `.xlsx`).

### 1.2 Трансформации
- **`.map(func: Callable[[T], R]) -> Flux[R]`**: Преобразует каждый элемент функцией `func`.
- **`.filter(predicate: Callable[[T], bool]) -> Flux[T]`**: Фильтрует элементы по предикату `predicate`.
- **`.bind(func: Callable[[T], Iterable[R]]) -> Flux[R]`**: Монадический flatMap ($M \gg= f$).
- **`flux >> func`**: Перегруженный оператор, алиас для `.bind(func)`.
- **`.extend(field_name: str, rule: Any) -> Flux[Dict[str, Any]]`**: Добавляет новое вычисляемое или статическое поле. `rule` может быть функцией `lambda r: ...`, списком сегментов путей для строковой интерполяции или константой. (Алиас: `.with_field()`).
- **`.select(*fields: str) -> Flux[Dict[str, Any]]`**: Оставляет в записях только указанные поля. (Алиас: `.project()`).
- **`.exclude(*fields: str) -> Flux[Dict[str, Any]]`**: Удаляет указанные поля из записей. (Алиас: `.drop()`).
- **`.rename(**mapping: str) -> Flux[Dict[str, Any]]`**: Переименовывает ключи или атрибуты (например, `old_name="new_name"`).
- **`.cast(target_type: Callable[[Any], R]) -> Flux[R]`**: Приводит каждый элемент к целевому типу (dataclass, Pydantic-модель, int и т.д.).
- **`.flatten(field: Optional[str] = None) -> Flux[Any]`**: Разворачивает вложенные последовательности в корне потока или внутри указанного поля.
- **`.fill_null(**defaults: Any) -> Flux[T]`**: Заменяет `None` или отсутствующие поля значениями по умолчанию. (Алиасы: `.fillna()`, `.fillNull()`).
- **`.compact() -> Flux[T]`**: Отфильтровывает значения `None`.
- **`.branch(predicate, if_true, if_false=None) -> Flux[Any]`**: Условное ветвление преобразования строк.
- **`.catch(handler=None, exceptions=(Exception,)) -> Flux[T]`**: Перехватывает исключения при обработке строк.

### 1.3 Декларативная фильтрация
- **`.when(predicate=None, **kwargs) -> Flux[T]`**: Фильтрация с использованием `Expression`, `Q` или синтаксиса Django (`age__gte=18`, `role="admin"`). (Алиасы: `.where()`, `.filterby()`, `.filter_by()`).

### 1.4 Срезы и оконные функции
- **`.take(count: int) -> Flux[T]`**: Извлекает первые `count` элементов с немедленной остановкой. (Алиасы: `.head()`, `.limit()`).
- **`.skip(count: int) -> Flux[T]`**: Пропускает первые `count` элементов. (Алиас: `.offset()`).
- **`.tail(count: int = 1) -> Flux[T]`**: Возвращает последние `count` элементов с использованием ограниченного буфера.
- **`.chunk(size: int) -> Flux[List[T]]`**: Группирует элементы в списки фиксированного размера `size`. (Алиас: `.batch()`).
- **`.window(size: int, step: int = 1) -> Flux[List[T]]`**: Скользящее окно элементов размера `size` с шагом `step`.

### 1.5 Сортировка, группировка и барьеры
- **`.sortby(*keys, reverse=False) -> Flux[T]`**: Сортирует элементы потока по полям или функциям. Поддерживает префикс `"-"` для сортировки по убыванию (например, `"-age"`). (Алиасы: `.sort_by()`, `.order_by()`).
- **`.groupby(key_selector) -> Flux[Group[T]]`**: Группирует элементы в объекты `Group` с изолированными подпотоками. (Алиас: `.group_by()`).
- **`.distinct(key_selector=None) -> Flux[T]`**: Удаляет дубликаты записей. (Алиас: `.unique()`).
- **`.reverse() -> Flux[T]`**: Разворачивает порядок элементов потока.
- **`.sample(n: int, seed=None) -> Flux[T]`**: Reservoir sampling (случайная выборка $n$ элементов с равномерной вероятностью).

### 1.6 Реляционные соединения (Joins) и операции над множествами
- **`.join(other, left_on, right_on, how="inner") -> Flux[Dict[str, Any]]`**: Хеш-соединение потоков с режимами `'inner'`, `'left'`, `'right'`, `'full'`.
- **`.inner_join(other, left_on, right_on)`**: Алиас для Inner Join.
- **`.left_join(other, left_on, right_on)`**: Алиас для Left Outer Join.
- **`.right_join(other, left_on, right_on)`**: Алиас для Right Outer Join.
- **`.full_join(other, left_on, right_on)`**: Алиас для Full Outer Join.
- **`.cross_join(other) -> Flux[Dict[str, Any]]`**: Декартово произведение двух потоков.
- **`.union(other: Flux[T]) -> Flux[T]`**: Ленивая конкатенация потоков.
- **`.intersection(other: Flux[T]) -> Flux[T]`**: Барьерное пересечение множеств.
- **`.difference(other: Flux[T]) -> Flux[T]`**: Барьерная разность множеств.
- **`.zip(other: Flux[R]) -> Flux[Tuple[T, R]]`**: Объединение двух потоков в пары кортежей.
- **`.partition(predicate, **kwargs) -> Tuple[Flux[T], Flux[T]]`**: Разделяет поток на кортеж `(matching_flux, not_matching_flux)`.

### 1.7 Аналитические операции
- **`.enumerate(start=0, field=None) -> Flux[Any]`**: Добавляет порядковый номер в поле или генерирует кортежи `(index, item)`.
- **`.cumulative_sum(field, target_field=None) -> Flux[Dict[str, Any]]`**: Нарастающий итог (кумулятивная сумма). (Алиасы: `.running_sum()`, `.cumulativeSum()`).
- **`.lag(field, offset=1, target_field=None, default=None)`**: Доступ к значению поля на `offset` позиций назад.
- **`.lead(field, offset=1, target_field=None, default=None)`**: Доступ к значению поля на `offset` позиций вперед.

### 1.8 Параллелизм и побочные эффекты
- **`.parallel_map(func, workers=None, chunksize=1, backend="thread") -> Flux[R]`**: Параллельное выполнение `func` в пуле потоков или процессов. (Алиасы: `.parallelMap()`, `.pmap()`).
- **`.tap(action: Callable[[T], None]) -> Flux[T]`**: Выполняет побочное действие (логирование, сбор метрик) без мутации элементов. (Алиас: `.peek()`).

### 1.9 Материализация и терминальные операции
- **`.collect() -> List[T]`**: Материализует поток в список Python. (Алиасы: `.to_list()`, `.toList()`).
- **`.first(default=None) -> Optional[T]`**: Возвращает первый элемент или значение по умолчанию.
- **`.last(default=None) -> Optional[T]`**: Возвращает последний элемент или значение по умолчанию.
- **`.count() -> int`**: Подсчитывает общее количество элементов в потоке.
- **`.exists() -> bool`**: Возвращает `True`, если в потоке есть хотя бы один элемент.
- **`.any(predicate=None) -> bool`**: Проверяет, удовлетворяет ли хотя бы один элемент предикату.
- **`.all(predicate) -> bool`**: Проверяет, удовлетворяют ли все элементы предикату.
- **`.reduce(func, *initial) -> Any`**: Свертка потока с аккумулятором.
- **`.sum(selector=None) -> Union[int, float]`**: Суммирует значения элементов.
- **`.average(selector=None) -> float`**: Вычисляет среднее арифметическое. (Алиас: `.avg()`).
- **`.min(selector=None) -> T`**: Находит минимальный элемент.
- **`.max(selector=None) -> T`**: Находит максимальный элемент.
- **`.median(selector=None) -> float`**: Вычисляет медиану.
- **`.mode(selector=None) -> Any`**: Находит моду (наиболее часто встречающееся значение).
- **`.std_dev(selector=None) -> float`**: Вычисляет выборочное стандартное отклонение. (Алиас: `.stdDev()`).
- **`.materialize() -> Flux[T]`**: Фиксирует поток в неизменяемый кортеж для безопасного многократного прохода.
- **`.to_json(filepath, lines=False, indent=2)`**: Сохраняет поток в файл JSON / JSON Lines.
- **`.to_csv(filepath, delimiter=",")`**: Сохраняет поток в файл CSV.
- **`.to_yaml(filepath)`**: Сохраняет поток в файл YAML.
- **`.to_toml(filepath, root_key="items")`**: Сохраняет поток в файл TOML.
- **`.to_excel(filepath, sheet_name="Sheet1")`**: Сохраняет поток в таблицу Excel.
- **`.to_file(filepath, **kwargs)`**: Сохраняет в файл с автоопределением формата по расширению.
- **`async for item in flux`**: Протокол асинхронной итерации.
- **`await flux.collect_async()`**: Асинхронно материализует поток в список. (Алиас: `.toListAsync()`).

### 1.10 Диагностика и телеметрия
- **`.explain(optimized=False) -> str`**: Возвращает ASCII-диаграмму графа плана выполнения.
- **`.profile() -> ProfileResult`**: Измеряет время выполнения и количество обработанных элементов на каждом шаге.

---

## 2. Класс: `Field`

Построение строго типизированных выражений фильтрации с перегрузкой операторов Python:

```python
from fluxmonad import Field

Field("age") >= 18
Field("name") == "Alice"
Field("status") != "archived"
Field("role").is_in(["admin", "manager"])
Field("tags").contains("staff")
```

Поддерживает логические операторы `&` (AND), `|` (OR) и `~` (NOT).

---

## 3. Класс: `Q`

Конструктор условий в стиле Django ORM:

```python
from fluxmonad import Q

q = Q(age__gte=18, status="active") | Q(role="superadmin")
Flux(users).when(q)
```

Поддерживаемые операторы поиска (lookups):
- `__exact` или `__eq`: Равно (`==`)
- `__ne`: Не равно (`!=`)
- `__gt`: Больше (`>`)
- `__gte`: Больше или равно (`>=`)
- `__lt`: Меньше (`<`)
- `__lte`: Меньше или равно (`<=`)
- `__in`: Вхождение в коллекцию (`in`)
- `__contains`: Содержит подстроку или элемент
