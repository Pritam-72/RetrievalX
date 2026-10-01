import numpy as np

from app.services.embedding_service import get_embedding_service

CORPUS = {
    "france.txt": (
        "Paris is the capital city of France. France uses the euro and its national "
        "holiday is Bastille Day on July 14."
    ),
    "python_history.txt": (
        "Guido van Rossum created the Python programming language. Python emphasizes "
        "readability and was first published in 1991."
    ),
    "operating_systems.txt": (
        "A process is a program in execution. The scheduler assigns CPU time to "
        "processes, and a thread is a smaller unit of execution within a process."
    ),
}

QUESTIONS = {
    "answerable": [
        "Which city serves as France's capital?",
        "What currency is used by France?",
        "When is Bastille Day celebrated in France?",
        "Who developed the Python programming language?",
        "What quality does Python emphasize?",
        "In what year was Python first published?",
        "What is a process in operating systems?",
        "What does the scheduler assign to processes?",
        "What is a thread described as?",
    ],
    "unrelated": [
        "What is the boiling point of water at sea level?",
        "Who painted the Mona Lisa?",
        "How do vaccines train the immune system?",
        "What is the tallest mountain in South America?",
        "How does photosynthesis convert sunlight?",
        "What causes a lunar eclipse?",
        "Which composer wrote the Ninth Symphony?",
        "What are the stages of the water cycle?",
        "How is coffee traditionally roasted?",
    ],
    "near_miss": [
        "In what year was Python first released?",
        "Who is the current president of France?",
        "What is France's largest city by population?",
        "Who designed the Python logo?",
        "What was Python's original project code name?",
        "Which Python version introduced async and await?",
        "What is the difference between a process and a thread in practice?",
        "Which scheduling algorithm is used by the operating system?",
        "How much memory does a typical process require?",
    ],
}


def test_print_real_bge_cosine_scores_for_refusal_a_to_d() -> None:
    """Prints class ranges with and without BGE's query instruction prefix."""
    embedder = get_embedding_service("BAAI/bge-small-en-v1.5")
    chunks = list(CORPUS.values())
    questions = [question for group in QUESTIONS.values() for question in group]

    chunk_vectors = embedder.embed_passages(chunks)
    prefixed_vectors = np.vstack(
        [embedder.embed_query(question) for question in questions]
    )
    unprefixed_vectors = embedder.embed_passages(questions)

    for label, question_vectors in (
        ("with query prefix", prefixed_vectors),
        ("without query prefix", unprefixed_vectors),
    ):
        scores = question_vectors @ chunk_vectors.T
        print(f"\n{label}")
        print("class       | min    | mean   | max")
        print("------------|--------|--------|--------")
        offset = 0
        for group, group_questions in QUESTIONS.items():
            top_scores = scores[offset : offset + len(group_questions)].max(axis=1)
            print(
                f"{group:<11} | {top_scores.min():.4f} | "
                f"{top_scores.mean():.4f} | {top_scores.max():.4f}"
            )
            offset += len(group_questions)

    assert chunk_vectors.shape == (3, 384)
    assert prefixed_vectors.shape == (27, 384)
    assert unprefixed_vectors.shape == (27, 384)
