import re
import pathlib

DATA_DIR = pathlib.Path(__file__).parent
RAW_PATH = DATA_DIR / "final2.txt"


def parse_raw_questions(text):
    blocks = re.split(r'\bANSWER:', text)
    questions = []

    for i in range(len(blocks) - 1):
        block_lines = [line.strip() for line in blocks[i].split("\n")]
        answer = blocks[i + 1].strip().split("\n")[0].strip().upper()

        question = ""
        choices = []

        for line in block_lines:
            if not line:
                continue

            # A–E)
            if re.match(r"^[A-E]\)", line):
                choices.append(line)
                continue

            # защитный фильтр от “D”
            if len(line) == 1 and line.upper() in "ABCDE":
                continue

            if question == "":
                question = line

        if question and choices:
            questions.append({
                "question": question,
                "choices": choices,
                "answer": answer
            })

    return questions


def ask_question(q):
    while True:
        print("\n-----------------------------")
        print(q["question"])
        print("-----------------------------")

        for c in q["choices"]:
            print(c)

        user = input("Ваш ответ (A-E): ").strip().upper()
        correct = q["answer"].upper()

        if user == correct:
            print("Правильно ✅")
            break
        else:
            print("Жоғале ❌ .\n")


def paginate(questions, page_size=15):
    """Разделяет вопросы на страницы по page_size."""
    pages = []
    for i in range(0, len(questions), page_size):
        pages.append(questions[i:i + page_size])
    return pages


def main():
    if not RAW_PATH.exists():
        print("Файл raw_questions.txt не найден.")
        return

    raw_text = RAW_PATH.read_text(encoding="utf-8")
    if not raw_text.strip():
        print("Файл пуст.")
        return

    questions = parse_raw_questions(raw_text)

    # создаём пакеты по 15
    pages = paginate(questions, page_size=15)

    print(f"Всего вопросов: {len(questions)}")
    print(f"Пакетов по 15: {len(pages)}\n")

    # предложить выбор пакета
    while True:
        try:
            page = int(input(f"Выберите номер пакета (1–{len(pages)}): "))
            if 1 <= page <= len(pages):
                break
        except ValueError:
            pass
        print("Неверный ввод. Введите число.")

    selected = pages[page - 1]

    print(f"\nНачинаем пакет №{page} (вопросы { (page-1)*15 + 1 }–{ (page-1)*15 + len(selected) })\n")

    for q in selected:
        ask_question(q)

    print("\nПакет завершён.")


if __name__ == "__main__":
    main()
