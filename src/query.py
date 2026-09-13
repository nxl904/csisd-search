"""
Ask a question against the built index from the command line.

Usage:
    python src/query.py --db data/chroma --q "What was the CFO's salary in 2023?"
"""
import argparse

from rag import answer_question, get_clients, get_collection


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--q", required=True, help="Question to ask")
    parser.add_argument("--doc-type", default=None, help="Optional filter: budget/agenda/minutes/policy/contract/other")
    args = parser.parse_args()

    openai_client, anthropic_client = get_clients()
    collection = get_collection(args.db)

    answer, hits = answer_question(
        openai_client, anthropic_client, collection, args.q, doc_type=args.doc_type
    )

    print("\n=== ANSWER ===\n")
    print(answer)
    print("\n=== SOURCES RETRIEVED ===\n")
    for h in hits:
        print(f"- {h['metadata'].get('source_file')} (distance: {h['distance']:.3f})")


if __name__ == "__main__":
    main()
