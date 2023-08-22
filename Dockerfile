# Используем базовый образ Python
FROM python:3.9

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Копируем файлы проекта в контейнер
COPY . /app

# Устанавливаем зависимости проекта
RUN pip install -r requirements.txt

# Запускаем команду python bot.py при старте контейнера
CMD ["python", "bot.py"]