from fastapi import FastAPI
import os
import schemas
from dotenv import load_dotenv, find_dotenv
from langchain_community.vectorstores.pgvector import PGVector
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain.schema import AIMessage, HumanMessage, SystemMessage

load_dotenv(find_dotenv())

os.environ['LANGCHAIN_TRACING_V2'] = 'true'
os.environ['LANGCHAIN_ENDPOINT'] = 'https://api.smith.langchain.com'
os.environ['LANGCHAIN_PROJECT'] = 'news-summarizer-project'
os.environ['LANGCHAIN_API_KEY'] = os.getenv("LANGCHAIN_API_KEY")
os.environ['OPENAI_API_KEY'] = os.getenv("OPENAI_API_KEY")
os.environ["LANGCHAIN_TRACING_V2_ENABLED"] =  os.getenv("LANGCHAIN_TRACING_V2_ENABLED")
pg_user = os.getenv("PG_USER")
pg_password = os.getenv("PG_PASSWORD")

hf_embedding = HuggingFaceEmbeddings(
    model_name="cahya/bert-base-indonesian-522M"
)

connection_string = f"postgresql+psycopg2://{pg_user}:{pg_password}@localhost:5432/vector_db"
collection_name = "pg_vectorstore"
retriever_vectorstore = PGVector(
    collection_name=collection_name,
    connection_string=connection_string,
    embedding_function=hf_embedding
)

retriever = retriever_vectorstore.as_retriever(
    search_kwargs={
        "k": 10,
    }
)

# LLM
model = ChatOpenAI(model="gpt-4o", temperature=0) 

def is_real_question(input_text):
    return "?" in input_text or len(input_text.split()) > 6

# Chat prompt
def chat_prompt(query):
    chat_history = []
    # Set an initial system message (optional)
    system_message = SystemMessage(content="Anda adalah seorang AI Assistant yang membantu banyak hal")
    chat_history.append(system_message)  # Add system message to chat history

    if query.lower() == "exit":
        return 'Chat finished!'
    else:
        chat_history.append(HumanMessage(content=query))  # Add user message

        if is_real_question(query):
            retriever_docs = retriever.invoke(query)
            relevant_docs = '\n\n'.join(doc.page_content for doc in retriever_docs)
        else:
            relevant_docs = ""

        chat_history.append(HumanMessage(content=relevant_docs)) # Add relevant document

        # Get AI response using history
        result = model.invoke(chat_history)
        response = result.content
        chat_history.append(AIMessage(content=response))  # Add AI message

        return response


app = FastAPI(
    version='0.0.1'
)

@app.post("/post")
def rag(request:schemas.ChatRequest):
    print(request)
    query = request.question
    result = chat_prompt(query)
    return {
        "qustions": query,
        "answer": result
    }

