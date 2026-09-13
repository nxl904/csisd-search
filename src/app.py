"""
Streamlit chat UI over the CSISD document index.

Usage:
    streamlit run src/app.py
"""
import streamlit as st

from rag import answer_question, get_clients, get_collection

st.set_page_config(page_title="CSISD Document Search", page_icon="🔎")
st.title("🔎 CSISD Document Search")
st.caption(
    "Ask questions about College Station ISD board agendas, budgets, "
    "policies, and contracts. Answers are grounded in indexed source "
    "documents and cited — not general knowledge."
)

DB_PATH = "data/chroma"

if "history" not in st.session_state:
    st.session_state.history = []

doc_type = st.sidebar.selectbox(
    "Filter by document type",
    ["(all)", "budget", "agenda", "minutes", "policy", "contract", "other"],
)
doc_type_filter = None if doc_type == "(all)" else doc_type

for turn in st.session_state.history:
    with st.chat_message(turn["role"]):
        st.markdown(turn["content"])

question = st.chat_input("Ask about CSISD budgets, board actions, policies...")

if question:
    st.session_state.history.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Searching indexed documents..."):
            openai_client, anthropic_client = get_clients()
            collection = get_collection(DB_PATH)
            answer, hits = answer_question(
                openai_client, anthropic_client, collection, question,
                doc_type=doc_type_filter,
            )
            st.markdown(answer)
            with st.expander("Sources retrieved"):
                for h in hits:
                    st.write(
                        f"- **{h['metadata'].get('source_file')}** "
                        f"(doc_type: {h['metadata'].get('doc_type')}, "
                        f"distance: {h['distance']:.3f})"
                    )
    st.session_state.history.append({"role": "assistant", "content": answer})
