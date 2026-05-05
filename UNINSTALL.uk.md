# Видалення — cheap-llm-router

🌐 **Мови:** [English](UNINSTALL.md) · **Українська** · [Русский](UNINSTALL.ru.md)

Відкочує те, що зробив [INSTALL.uk.md](INSTALL.uk.md). Кроки незалежні — можна зупинитися на будь-якому. Йдуть від «найлегшого торкання» (просто перестати використовувати) до «жодного сліду».

## Крок 1 — Заборонити Claude / Codex автоматично використовувати `cheap`

Правило живе у `~/.claude/CLAUDE.md` між заголовком `## Cheap LLM Delegation — Mandatory Checkpoint` та наступним `## `. Два варіанти:

**(а) Ручкою** — відкрийте файл і видаліть цей блок:

```bash
$EDITOR ~/.claude/CLAUDE.md
```

**(б) Автоматично, з резервною копією** — скопіюйте цей блок у термінал:

```bash
cp ~/.claude/CLAUDE.md ~/.claude/CLAUDE.md.bak
python3 - <<'PY'
import re, pathlib
p = pathlib.Path.home() / ".claude" / "CLAUDE.md"
text = p.read_text(encoding="utf-8")
m = re.search(r"^##\s+Cheap LLM\b.*$", text, re.MULTILINE | re.IGNORECASE)
if m:
    start = m.start()
    rest = text[m.end():]
    nm = re.search(r"^##\s", rest, re.MULTILINE)
    body_end = m.end() + nm.start() if nm else len(text)
    new = text[:start].rstrip() + "\n"
    if nm:
        new += "\n" + text[body_end:]
    p.write_text(new, encoding="utf-8")
    print("removed")
else:
    print("section not present — nothing to do")
PY
```

Якщо у вас також є `AGENTS.md` (для Codex) з тим самим блоком, повторіть це для нього.

Перевірте, що нічого не лишилося:

```bash
grep -n "Cheap LLM" ~/.claude/CLAUDE.md || echo "clean"
```

Після цього команда `cheap` ще працюватиме, якщо викликати її руками, але Claude / Codex більше не використовуватимуть її автоматично.

## Крок 2 — Видалити файл налаштувань і кеші

```bash
rm -rf ~/.config/cheap-llm
rm -rf "${XDG_CACHE_HOME:-$HOME/.cache}/cheap-llm"
```

Перший рядок видаляє `config.yaml`. Другий очищає журнал використання (по одному JSON-рядку на кожен виклик `cheap read` / `cheap extract`) і per-PID hint-файли, які записує SessionStart hook. І те, й те — observability, критичного стану там немає.

Якщо ви встановлювали SessionStart hook (див. `docs/HOOKS.md`), додатково видаліть bundled-скрипт і приберіть його з `~/.claude/settings.json`:

```bash
rm -f ~/.claude/hooks/cheap-llm-session.sh
$EDITOR ~/.claude/settings.json    # приберіть SessionStart-запис, який вказував на цей скрипт
```

## Крок 3 — Видалити саму команду `cheap`

```bash
pipx uninstall cheap-llm-router
```

Перевірити:

```bash
which cheap || echo "gone"
```

Якщо ви ставили інакше:

```bash
pip uninstall -y cheap-llm-router      # звичайний pip
sudo pip uninstall -y cheap-llm-router # якщо ставили в системний Python як root
```

## Крок 4 — Прибрати API-ключ із оболонки

Відкрийте rc-файл, який редагували при установці:

```bash
$EDITOR ~/.zshrc        # або ~/.bashrc, ~/.config/fish/config.fish
```

Видаліть рядок `export OPENROUTER_API_KEY=…`, потім відкрийте новий термінал.

Перевірте:

```bash
echo "${OPENROUTER_API_KEY:-(unset)}"
# → (unset)
```

**Рекомендований бонус:** анулюйте або змініть ключ на <https://openrouter.ai/keys>, щоб стара збережена копія не могла бути використана.

## Крок 5 (Необов'язково) — Видалити теку проєкту

Якщо ви клонували репозиторій локально й хочете прибрати геть усе:

```bash
rm -rf /path/to/cheap-llm-router
```

Видаляє README, інструкції з установки/видалення, вихідний код, тести, дизайн-документи та історію `.git`. Після цього на диску не лишається жодного сліду.

## Швидка перевірка, що все прибрано

Якщо виконали всі 5 кроків, нижчі рядки мають вивести «gone»-подібні повідомлення:

```bash
which cheap                                                  # → not found
test -e ~/.config/cheap-llm && echo "config" || echo "config gone"
grep -c "Cheap LLM" ~/.claude/CLAUDE.md                       # → 0
echo "${OPENROUTER_API_KEY:-(unset)}"                         # → (unset)
test -e /path/to/cheap-llm-router && echo "src" || echo "src gone"
```

## Куди проєкт пише, а куди — ні

Для спокою — `cheap` пише лише сюди:

- `~/.local/bin/cheap` (сама команда; видаляється на кроці 3)
- `~/.config/cheap-llm/config.yaml` (створюється при першому запуску; видаляється на кроці 2)
- `~/.claude/CLAUDE.md` та / або `AGENTS.md` (тільки якщо ви запускали `install-claude-rule`; видаляється на кроці 1)

Жодних системних файлів, жодних демонів, жодних запланованих завдань, жодних мережевих звернень окрім тих викликів OpenRouter, які ви зробили самі.
