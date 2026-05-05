# Установка — cheap-llm-router

🌐 **Мови:** [English](INSTALL.md) · **Українська** · [Русский](INSTALL.ru.md)

Покрокова інструкція. Кожен крок самодостатній — якщо щось пішло не так, [UNINSTALL.uk.md](UNINSTALL.uk.md) показує, як відкотити саме той крок.

## Перш ніж почати

Вам знадобиться:

- **macOS або Linux.** Windows не тестувався.
- **Python 3.11 або новіше.** Перевірити: `python3 --version`.
- **`pipx`** — встановлює CLI-програми у власне ізольоване середовище, щоб вони не конфліктували з системним Python.
  - macOS: `brew install pipx`
  - Linux: `python3 -m pip install --user pipx && pipx ensurepath`
- **Акаунт на OpenRouter та API-ключ.** Безкоштовна реєстрація на <https://openrouter.ai/>, поповніть кілька доларів і скопіюйте ключ. Він має вигляд `sk-or-v1-…`. (Можна використовувати будь-якого іншого OpenAI-сумісного провайдера — DeepSeek напряму, локальний Ollama тощо.)

## Крок 1 — Встановити команду `cheap`

```bash
pipx install git+https://github.com/Lexus2016/cheap-llm-router.git
```

Після цього команда `cheap` доступна у вашому PATH:

```bash
cheap --help
which cheap          # → ~/.local/bin/cheap (або подібне)
```

Якщо `cheap` не знайшовся — у вашій оболонці може не бути `~/.local/bin` у PATH. Запустіть `pipx ensurepath` і відкрийте новий термінал.

## Крок 2 — Підказати `cheap`, де ваш API-ключ

Найпростіше — додайте цей рядок у файл запуску оболонки (`~/.zshrc` для zsh, `~/.bashrc` для bash, `~/.config/fish/config.fish` для fish):

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

Потім перезавантажте:

```bash
source ~/.zshrc        # або відкрийте новий термінал
cheap config check     # → OK
```

Якщо ви бачите `missing env: OPENROUTER_API_KEY` — змінна не видна; відкрийте новий термінал або перевірте, що ви зберегли правильний rc-файл.

**Альтернатива, якщо змінні середовища незручні** — покладіть ключ просто у файл налаштувань:

```bash
$EDITOR "$(cheap config path)"
```

Знайдіть рядок `api_key_env: OPENROUTER_API_KEY`, закоментуйте його (`# api_key_env: ...`) і нижче додайте:

```yaml
api_key: "sk-or-v1-..."
```

Працює так само, але секрет тепер у YAML-файлі. Тримайте його подалі від git, iCloud, Dropbox і скріншотів. `cheap config show` маскуватиме ключ автоматично; `cat` — ні.

## Крок 3 — Розповісти Claude / Codex про новий інструмент

Правило живе у файлі інструкцій вашого AI — `~/.claude/CLAUDE.md` для Claude Code, `~/.codex/AGENTS.md` для OpenAI Codex CLI. Виберіть один:

```bash
cheap install-rule                  # авто: кожна виявлена тека агента
cheap install-rule --target claude  # лише ~/.claude/CLAUDE.md
cheap install-rule --target codex   # лише ~/.codex/AGENTS.md
cheap install-rule --target all     # обидва, незалежно від наявності
```

Безпечно запускати повторно — не дублюватиме. Додайте `--force`, щоб перезаписати наявний блок свіжим текстом.

`cheap install-claude-rule` (стара назва Phase 1) досі працює як deprecated alias для `cheap install-rule --target claude`.

### (Необов'язково) Точніше визначення сесії Claude

Якщо ви користуєтеся `cheap extract` на сесіях Claude Code — див. [docs/HOOKS.md](docs/HOOKS.md) щодо необов'язкового 30-секундного SessionStart hook'а: він робить визначення сесії детермінованим, коли у вас одночасно кілька вікон Claude в одній директорії. Пропустіть, якщо у вас не буває паралельних сесій у одному проекті.

## Крок 4 — Спробувати на ділі

Зробіть резюме маленького файлу з проєкту:

```bash
cheap read tests/fixtures/sample_module/auth.py -q "що це робить?"
```

У відповідь — markdown-резюме у stdout і рядок телеметрії у stderr на кшталт:

```
[cheap] files=1 input_chars=4255 output_tokens=587 model=deepseek/deepseek-v4-pro elapsed_ms=2143
```

Готово. Відтепер, коли Claude або Codex збирався б прочитати 3+ файли просто заради контексту, правило підкаже їм спершу викликати `cheap`.

## (Необов'язково) Крок 5 — Запустити тести

Якщо ви склонували source та хочете переконатися, що все працює:

```bash
cd /path/to/cheap-llm-router
python3 -m venv .venv
.venv/bin/pip install -e ".[test]"
.venv/bin/pytest -q
# → 65 passed
```

Щоб запустити ще й тест із реальним мережевим викликом (вартує ~$0.01 з вашого балансу OpenRouter):

```bash
RUN_INTEGRATION=1 .venv/bin/pytest -k integration
```

## Поширені проблеми

| Проблема | Що робити |
|---|---|
| `command not found: cheap` | `pipx ensurepath`, відкрити новий термінал. |
| `missing env: OPENROUTER_API_KEY` | Експорт ще не у поточній оболонці. `source ~/.zshrc` або новий термінал. |
| `provider call failed: ... 401` | Неправильний або анульований API-ключ. Перевірте на <https://openrouter.ai/keys>. |
| `provider call failed: ... 402` | Закінчилися кошти. Поповніть на <https://openrouter.ai/credits>. |
| `cheap install-claude-rule` додає правило ще раз | У вас стара версія. Оновіть: `pipx reinstall cheap-llm-router`. |

## Як оновлювати потім

Якщо встановлювали з GitHub:

```bash
pipx reinstall cheap-llm-router
```

Якщо встановлювали з локальної копії:

```bash
cd /path/to/cheap-llm-router
git pull
pipx reinstall cheap-llm-router
```

Якщо встановлювали з прапорцем `--editable`, достатньо `git pull` — ваші локальні зміни підхоплюються одразу.
