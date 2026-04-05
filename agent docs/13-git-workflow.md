# 13-git-workflow.md

## Git и работа с репозиторием

### Общая концепция

Настройка Git для монорепозитория с правильной структурой ветвления, правилами коммитов и защитой основных веток.

---

### Инициализация репозитория

```bash
# Перейти в корень проекта
cd rod-system-designer

# Инициализация Git
git init

# Создание .gitignore (см. ниже)
# Первый коммит
git add .
git commit -m "Initial commit: rod system designer mono-repo with FEM solver and neural network"

# Добавление удаленного репозитория (пример)
git remote add origin https://github.com/your-org/rod-system-designer.git
git branch -M main
git push -u origin main
```
