#!/bin/sh
set -e

# 🧭 Шляхи
ALEMBIC_CONFIG="/usr/src/alembic.ini"
MIGRATIONS_DIR="/usr/src/src/database/migrations/versions"

echo "🧩 Checking for changes before generating a migration..."

# PYTHONPATH для доступу до src/config, src/models тощо
export PYTHONPATH=/usr/src/src
export PGPASSWORD="$POSTGRES_PASSWORD"

# 🗂️ Якщо папка міграцій не існує — створюємо
if [ ! -d "$MIGRATIONS_DIR" ]; then
    echo "📁 Migrations folder not found. Creating..."
    mkdir -p "$MIGRATIONS_DIR"
fi

# 🧱 Перевіряємо, чи є таблиця alembic_version (чи база порожня)
if ! psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\dt" | grep -q "alembic_version"; then
    echo "🆕 Alembic version table not found. Applying initial migration..."

    # Якщо немає жодних міграцій — створюємо першу
    if [ -z "$(ls -A "$MIGRATIONS_DIR")" ]; then
        echo "🧱 No migration files found. Generating initial migration..."
        poetry run alembic -c $ALEMBIC_CONFIG revision --autogenerate -m "initial migration"
    fi

    echo "🚀 Applying migrations..."
    poetry run alembic -c $ALEMBIC_CONFIG upgrade head

    echo "✅ Database is up to date!"
    exit 0
fi

# 🧪 Генеруємо тимчасову міграцію для перевірки змін
if ! poetry run alembic -c $ALEMBIC_CONFIG revision --autogenerate -m "temp_migration"; then
    echo "❌ Error generating migration."
    exit 1
fi

# 🧾 Визначаємо останню створену міграцію
LAST_MIGRATION=$(find "$MIGRATIONS_DIR" -type f -printf '%T+ %p\n' | sort | tail -n 1 | awk '{print $2}')

echo "🧾 Generated migration content:"
cat "$LAST_MIGRATION"

# 🟢 Якщо змін немає — видаляємо тимчасову міграцію
if grep -qE '^\s*pass\s*$' "$LAST_MIGRATION"; then
    echo "🟢 No changes detected. Removing temp migration."
    rm "$LAST_MIGRATION"
else
    echo "🔺 Changes detected. Applying migration..."
    poetry run alembic -c $ALEMBIC_CONFIG upgrade head
fi

echo "✅ Migration process complete."
