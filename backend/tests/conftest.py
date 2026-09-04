import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://solvo:solvo-test-only@localhost:5432/solvo_test",
)

