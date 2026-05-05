# Установка — cheap-llm-router

🌐 **Языки:** [English](INSTALL.md) · [Українська](INSTALL.uk.md) · **Русский**

Пошаговая инструкция. Каждый шаг самодостаточен — если что-то пошло не так, [UNINSTALL.ru.md](UNINSTALL.ru.md) показывает, как откатить именно этот шаг.

## Перед началом

Понадобится:

- **macOS или Linux.** Windows не тестировался.
- **Python 3.11 или новее.** Проверить: `python3 --version`.
- **`pipx`** — устанавливает CLI-программы в собственное изолированное окружение, чтобы они не конфликтовали с системным Python.
  - macOS: `brew install pipx`
  - Linux: `python3 -m pip install --user pipx && pipx ensurepath`
- **Аккаунт на OpenRouter и API-ключ.** Бесплатная регистрация на <https://openrouter.ai/>, пополните несколько долларов и скопируйте ключ. Он выглядит как `sk-or-v1-…`. (Можно использовать любого другого OpenAI-совместимого провайдера — DeepSeek напрямую, локальный Ollama и т. п.)

## Шаг 1 — Установить команду `cheap`

```bash
pipx install git+https://github.com/Lexus2016/cheap-llm-router.git
```

После этого команда `cheap` доступна в вашем PATH:

```bash
cheap --help
which cheap          # → ~/.local/bin/cheap (или похожее)
```

Если `cheap` не найден — в вашей оболочке может не быть `~/.local/bin` в PATH. Запустите `pipx ensurepath` и откройте новый терминал.

## Шаг 2 — Указать `cheap`, где ваш API-ключ

Самый простой способ — добавьте эту строку в файл запуска оболочки (`~/.zshrc` для zsh, `~/.bashrc` для bash, `~/.config/fish/config.fish` для fish):

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

Затем перезагрузите:

```bash
source ~/.zshrc        # или откройте новый терминал
cheap config check     # → OK
```

Если видите `missing env: OPENROUTER_API_KEY` — переменная не видна; откройте новый терминал или проверьте, что сохранили правильный rc-файл.

**Альтернатива, если переменные окружения неудобны** — положите ключ прямо в файл настроек:

```bash
$EDITOR "$(cheap config path)"
```

Найдите строку `api_key_env: OPENROUTER_API_KEY`, закомментируйте её (`# api_key_env: ...`) и ниже добавьте:

```yaml
api_key: "sk-or-v1-..."
```

Работает так же, но секрет теперь в YAML-файле. Держите его подальше от git, iCloud, Dropbox и скриншотов. `cheap config show` будет маскировать ключ автоматически; `cat` — нет.

## Шаг 3 — Сообщить Claude / Codex о новом инструменте

Это добавит блок в `~/.claude/CLAUDE.md` (и в `AGENTS.md` для Codex, если такой файл есть) с чётким правилом, когда применять `cheap`. Безопасно запускать повторно — не задублирует.

```bash
cheap install-claude-rule
```

Повторный запуск печатает `already installed at …` и ничего не меняет. Чтобы перезаписать блок свежим текстом правила:

```bash
cheap install-claude-rule --force
```

## Шаг 4 — Попробовать в деле

Сделайте резюме небольшого файла из проекта:

```bash
cheap read tests/fixtures/sample_module/auth.py -q "что это делает?"
```

В ответ — markdown-резюме в stdout и строка телеметрии в stderr вида:

```
[cheap] files=1 input_chars=4255 output_tokens=587 model=deepseek/deepseek-v4-pro elapsed_ms=2143
```

Готово. Теперь, когда Claude или Codex собирался бы прочитать 3+ файла просто ради контекста, правило подскажет им сначала вызвать `cheap`.

## (Необязательно) Шаг 5 — Запустить тесты

Если вы склонировали исходники и хотите убедиться, что всё работает:

```bash
cd /path/to/cheap-llm-router
python3 -m venv .venv
.venv/bin/pip install -e ".[test]"
.venv/bin/pytest -q
# → 65 passed
```

Чтобы запустить ещё и тест с реальным сетевым вызовом (стоит ~$0.01 с баланса OpenRouter):

```bash
RUN_INTEGRATION=1 .venv/bin/pytest -k integration
```

## Частые проблемы

| Проблема | Что делать |
|---|---|
| `command not found: cheap` | `pipx ensurepath`, открыть новый терминал. |
| `missing env: OPENROUTER_API_KEY` | Экспорт ещё не в текущей оболочке. `source ~/.zshrc` или новый терминал. |
| `provider call failed: ... 401` | Неправильный или отозванный API-ключ. Проверьте на <https://openrouter.ai/keys>. |
| `provider call failed: ... 402` | Закончились средства. Пополните на <https://openrouter.ai/credits>. |
| `cheap install-claude-rule` добавляет правило снова | У вас старая версия. Обновите: `pipx reinstall cheap-llm-router`. |

## Как обновлять дальше

Если ставили из GitHub:

```bash
pipx reinstall cheap-llm-router
```

Если ставили из локальной копии:

```bash
cd /path/to/cheap-llm-router
git pull
pipx reinstall cheap-llm-router
```

Если ставили с флагом `--editable`, достаточно `git pull` — ваши локальные изменения подхватятся сразу.
