import json

def check_repetition(file_name):
    """
    Checks for question repetition in a JSON file of multiple-choice questions.

    Args:
        file_name (str): The path to the JSON file.
    """
    try:
        with open(file_name, 'r') as file:
            data = json.load(file)
    except FileNotFoundError:
        print(f"Error: The file '{file_name}' was not found.")
        return

    # Extract all questions
    questions = [item['question'] for item in data]

    # Count the frequency of each question
    question_counts = {}
    for question in questions:
        if question in question_counts:
            question_counts[question] += 1
        else:
            question_counts[question] = 1

    # Filter for repeated questions
    repeated_questions = {q: c for q, c in question_counts.items() if c > 1}

    # Calculate total number of questions and repetitions
    total_questions = len(questions)
    total_repetitions = sum(count - 1 for count in repeated_questions.values())

    # Calculate the percentage of repetition
    if total_questions > 0:
        percentage_repetition = (total_repetitions / total_questions) * 100
    else:
        percentage_repetition = 0

    print(f"Total number of questions: {total_questions}")
    print(f"Number of unique questions: {len(question_counts)}")
    print(f"Total number of repeated questions (instances): {total_repetitions}")

    print("\nRepeated Questions and their counts:")
    if repeated_questions:
        for question, count in repeated_questions.items():
            print(f"  Question: '{question}'")
            print(f"  Repetitions: {count}")
    else:
        print("  No questions were repeated.")

    print(f"\nPercentage of repetition: {percentage_repetition:.2f}%")

# Replace 'generated_100_mcqs-3' with your file name
check_repetition('generated_100_mcqs-3.json')