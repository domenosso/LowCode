<p align="center">
  <img src="https://i.ibb.co/jPJ5KPmk/header.png" alt="LowCode Header"/>
</p>

<h1 align="center">LowCode</h1>

<p align="center">
  <b>Onlysq-powered project assistant for managing files and code with natural language</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-1.0-blue">
  <img src="https://img.shields.io/badge/python-3.8+-yellow">
  <img src="https://img.shields.io/badge/status-active-success">
</p>

---

# ✨ About

**LowCode** — это CLI-утилита, которая позволяет управлять проектом с помощью AI.

Ты просто пишешь запрос вроде:

> "Создай Flask API"
> "Прочитай файл config.py"
> "Добавь Dockerfile"

AI:

* читает файлы
* редактирует код
* создает структуру проекта
* запускает команды
* анализирует репозиторий

и делает это **прямо внутри твоего проекта**.

---

# 🚀 Features

* 📂 управление файлами проекта
* 🧠 AI анализ кода
* ⚡ выполнение shell команд
* 🔒 sandbox внутри проекта
* 🖥 удобный CLI интерфейс
* 🎨 цветной вывод
* 🧩 поддержка любых OpenAI-совместимых API

---

# 📦 Installation

```bash
git clone https://github.com/domenosso/LowCode.git

cd lowcode

pip install openai
```

или просто скачай `main.py`.

---

# ⚙ Usage

Запуск:

```bash
python lowcode.py
```

Далее CLI попросит:

```
Введите API ключ
Введите ID модели
Введите путь к проекту
```

После этого можно писать команды AI.

---

# 💬 Example

```
Enter your AI request:

Создай простой FastAPI сервер
```

AI может выполнить действия:

```
[+] Created main.py
[+] Created requirements.txt
⚡ Running: pip install fastapi uvicorn
```

---

# 🔐 Safety

LowCode имеет защиту:

* запрет доступа **вне проекта**
* блокировка опасных команд
* sandbox shell execution
* ограничение stdout
* фильтр системных путей

---

# 🗂 Supported Actions

| Action        | Description             |
| ------------- | ----------------------- |
| read_file     | прочитать файл          |
| create_file   | создать файл            |
| edit_file     | изменить файл           |
| delete_file   | удалить файл            |
| create_folder | создать папку           |
| delete_folder | удалить папку           |
| list_folder   | список файлов           |
| run_command   | выполнить shell         |
| read_base64   | прочитать бинарный файл |
| message       | сообщение пользователю  |



# 🛠 Example prompts

```
Создай REST API на FastAPI
```

```
Добавь Dockerfile для проекта
```

```
Оптимизируй структуру проекта
```

```
Найди баги в коде
```

---

# 👨‍💻 Author

**@req_dev**(TELEGRAM)

---

# ⭐ Support

Если проект понравился:

```
⭐ Star the repository
```


