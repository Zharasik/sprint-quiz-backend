import re
import pathlib
import sys

DATA_DIR = pathlib.Path(__file__).parent
RAW_PATH = DATA_DIR / "midterm.txt"


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
                continue  # пропустить пустые

            # вариант ответа?
            if re.match(r"^[A-E]\)", line):
                choices.append(line)
                continue

            # защитное: если строка - ОДНА буква (твоя ошибка)
            if len(line) == 1 and line.upper() in "ABCDE":
                continue

            # если это нормальная строка — это вопрос
            if question == "":
                question = line

        if question and choices:
            questions.append({
                "question": question,
                "choices": choices,
                "answer": answer
            })
        else:
            print("⚠ Ошибка при парсинге блока, пропущен.")
            print("Блок был:", block_lines)

    return questions



def ask_question(q):
    while True:
        print("\n-----------------------------")
        print(q["question"])           # Вопрос чётко отделён
        print("-----------------------------")

        for c in q["choices"]:
            print(c)

        user = input("Ваш ответ (A-E): ").strip().upper()
        correct = q["answer"].upper()

        if user == correct:
            print("Правильно ✅")
            break
        else:
            print("Неправильно ❌ Попробуйте снова.\n")

def main():
    if not RAW_PATH.exists():
        print("Файл raw_questions.txt не найден. Создаю пустой.")
        RAW_PATH.write_text("", encoding="utf-8")
        print("Теперь вставьте туда свои вопросы и перезапустите.")
        return

    raw_text = RAW_PATH.read_text(encoding="utf-8")

    if not raw_text.strip():
        print("Файл raw_questions.txt пуст. Вставьте вопросы и перезапустите.")
        return

    questions = parse_raw_questions(raw_text)

    print(f"Загружено вопросов: {len(questions)}")
    print("Начинаем тест...\n")

    for q in questions:
        ask_question(q)

    print("\nТест завершён.")


if __name__ == "__main__":
    main()
