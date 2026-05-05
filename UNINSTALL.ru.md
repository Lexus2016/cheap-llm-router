# Удаление — cheap-llm-router

🌐 **Языки:** [English](UNINSTALL.md) · [Українська](UNINSTALL.uk.md) · **Русский**

Откатывает то, что сделал [INSTALL.ru.md](INSTALL.ru.md). Шаги независимы — можно остановиться на любом. Идут от «самого лёгкого касания» (просто перестать использовать) до «никакого следа не осталось».

## Шаг 1 — Запретить Claude / Codex автоматически использовать `cheap`

Правило живёт в `~/.claude/CLAUDE.md` между заголовком `## Cheap LLM Delegation — Mandatory Checkpoint` и следующим `## `. Два варианта:

**(а) Руками** — откройте файл и удалите этот блок:

```bash
$EDITOR ~/.claude/CLAUDE.md
```

**(б) Автоматически, с резервной копией** — скопируйте этот блок в терминал:

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

Если у вас также есть `AGENTS.md` (для Codex) с таким же блоком, повторите это для него.

Проверьте, что ничего не осталось:

```bash
grep -n "Cheap LLM" ~/.claude/CLAUDE.md || echo "clean"
```

После этого команда `cheap` ещё будет работать, если вызвать её руками, но Claude / Codex больше не будут использовать её автоматически.

## Шаг 2 — Удалить файл настроек и кеши

```bash
rm -rf ~/.config/cheap-llm
rm -rf "${XDG_CACHE_HOME:-$HOME/.cache}/cheap-llm"
```

Первая строка удаляет `config.yaml`. Вторая чистит журнал использования (одна JSON-строка на каждый вызов `cheap read` / `cheap extract`) и per-PID hint-файлы, которые пишет SessionStart hook. И то, и другое — observability, критичного состояния там нет.

Если вы устанавливали SessionStart hook (см. `docs/HOOKS.md`), дополнительно удалите bundled-скрипт и уберите его из `~/.claude/settings.json`:

```bash
rm -f ~/.claude/hooks/cheap-llm-session.sh
$EDITOR ~/.claude/settings.json    # уберите SessionStart-запись, указывавшую на этот скрипт
```

## Шаг 3 — Удалить саму команду `cheap`

```bash
pipx uninstall cheap-llm-router
```

Проверить:

```bash
which cheap || echo "gone"
```

Если ставили иначе:

```bash
pip uninstall -y cheap-llm-router      # обычный pip
sudo pip uninstall -y cheap-llm-router # если ставили в системный Python как root
```

## Шаг 4 — Убрать API-ключ из оболочки

Откройте rc-файл, который редактировали при установке:

```bash
$EDITOR ~/.zshrc        # или ~/.bashrc, ~/.config/fish/config.fish
```

Удалите строку `export OPENROUTER_API_KEY=…`, затем откройте новый терминал.

Проверьте:

```bash
echo "${OPENROUTER_API_KEY:-(unset)}"
# → (unset)
```

**Рекомендуемый бонус:** отзовите или смените ключ на <https://openrouter.ai/keys>, чтобы старая сохранённая копия не могла быть использована.

## Шаг 5 (Необязательно) — Удалить папку проекта

Если вы клонировали репозиторий локально и хотите убрать всё:

```bash
rm -rf /path/to/cheap-llm-router
```

Удаляет README, инструкции по установке/удалению, исходный код, тесты, дизайн-документы и историю `.git`. После этого на диске не остаётся ни следа.

## Быстрая проверка, что всё удалено

Если выполнили все 5 шагов, строки ниже должны вывести «gone»-подобные сообщения:

```bash
which cheap                                                  # → not found
test -e ~/.config/cheap-llm && echo "config" || echo "config gone"
grep -c "Cheap LLM" ~/.claude/CLAUDE.md                       # → 0
echo "${OPENROUTER_API_KEY:-(unset)}"                         # → (unset)
test -e /path/to/cheap-llm-router && echo "src" || echo "src gone"
```

## Куда проект пишет, а куда — нет

Для спокойствия — `cheap` пишет только сюда:

- `~/.local/bin/cheap` (сама команда; удаляется на шаге 3)
- `~/.config/cheap-llm/config.yaml` (создаётся при первом запуске; удаляется на шаге 2)
- `~/.claude/CLAUDE.md` и / или `AGENTS.md` (только если вы запускали `install-claude-rule`; удаляется на шаге 1)

Никаких системных файлов, никаких демонов, никаких запланированных задач, никаких сетевых обращений кроме тех вызовов OpenRouter, которые вы сделали сами.
