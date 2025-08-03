from dotenv import load_dotenv, find_dotenv
import os
# from langchain import hub
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langchain_openai import OpenAIEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings
# from langchain.vectorstores.pgvector import PGVector
from langchain_openai import ChatOpenAI
from langchain.schema import AIMessage, HumanMessage, SystemMessage
from datetime import datetime, timedelta

from rag_utils import *

# Load Env (API Key, etc)
load_dotenv(find_dotenv())
os.environ['LANGCHAIN_TRACING_V2'] = 'true'
os.environ['LANGCHAIN_ENDPOINT'] = 'https://api.smith.langchain.com'
os.environ['LANGCHAIN_PROJECT'] = 'news-summarizer-project'
os.environ['LANGCHAIN_API_KEY'] = os.getenv("LANGCHAIN_API_KEY")
os.environ['OPENAI_API_KEY'] = os.getenv("OPENAI_API_KEY")
os.environ["LANGCHAIN_TRACING_V2_ENABLED"] =  os.getenv("LANGCHAIN_TRACING_V2_ENABLED")
pg_user = os.getenv("PG_USER")
pg_password = os.getenv("PG_PASSWORD")

# # Load Data
# df = pd.read_json('data.json')
# df['date_publish'] = df['date_publish'].apply(lambda x : format_date(x))
# df['detail_content'] = df['detail_content'].apply(lambda x : format_content(x) if len(x) != 0 else x)

# docs = format_data(df)

basepath = r'D:\Continuum\BNI'
qa_pairs = extract_qa_pairs(os.path.join(basepath, 'Kompilasi BNI.docx'))

from langchain.docstore.document import Document

qa_texts = [f"Question: {q}\nAnswer: {a}" for q, a in qa_pairs]

splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=50)

docs = []
for qa in qa_texts:
    chunks = splitter.create_documents([qa])
    docs.extend(chunks)

# for doc in docs:
#     print(doc)
#     print('--------------------------------------------------')

# Convert each row to Document chunks
# docs = []
# text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)

# docs_split = text_splitter.create_documents(docs)

# for _, row in df.iterrows():
#     full_text = row['detail_content']
    
#     # Split long articles
#     chunks = text_splitter.split_text(full_text)
    
#     # Add chunks as Documents
#     for chunk in chunks:
#         doc = Document(
#             page_content=f"\nTanggal terbit : {row['date_publish']}\nJudul : {row['title']}\n\n{chunk}",
#             metadata={
#                 "title": row["title"],
#                 "date_published": str(row["date_publish"]),
#                 "publisher": row["publiser"]
#             }
#         )
#         docs.append(doc)

# # Check docs
# for i, doc in enumerate(docs):
#     print(f"--- Document {i+1} ---")
#     print("Content:", doc.page_content)
#     print("Metadata:", doc.metadata)
#     print()

# Embed
# embeddings = OpenAIEmbeddings(
#     model="text-embedding-3-small"
# )
hf_embedding = HuggingFaceEmbeddings(
    model_name="cahya/bert-base-indonesian-522M"
)
# hf_embedding = HuggingFaceEmbeddings(
#     model_name="indobenchmark/indobert-base-p1"
# )

# Create Vectorestore and Retriever
# today = datetime.today()
# days_ago = (today - timedelta(days=90)).strftime("%Y-%m-%d")

vectorstore = FAISS.from_documents(documents=docs, 
                                    embedding=hf_embedding)
# retriever_vectorstore = vectorstore.as_retriever()

# connection_string = f"postgresql+psycopg2://{pg_user}:{pg_password}@localhost:5432/vector_db"
# collection_name = "pg_vectorstore"
# retriever_vectorstore = PGVector(
#     collection_name=collection_name,
#     connection_string=connection_string,
#     embedding_function=hf_embedding
# )

# retriever = retriever_vectorstore.as_retriever()

retriever = vectorstore.as_retriever(
    search_kwargs={
        "k": len(docs),
    }
) # Dense Retrieval - Embeddings/Context basedd

# # Prompt
# template = """
#     Jawab pertanyaan berikut hanya berdasarkan konteks dibawah ini, 
#     Sertakan juga tanggal publish dan sumber/publishernya

#     {context}

#     Pertanyaan: {question}
# """

# prompt_template = ChatPromptTemplate.from_template(template)

# # use messages template
# messages = [
#     ("system", "Anda adalah seorang AI Assistant yang membantu banyak hal"),
#     ("human", "Berdasasrkan konteks berita dibawah ini :\n\n{context}.\n\nJawab pertanyaan berikut : {question}")
# ]
# prompt_template = ChatPromptTemplate.from_messages(messages)

# LLM
model = ChatOpenAI(model="gpt-4o", temperature=0) 

# # Chain
# rag_chain = (
#     {"context": retriever, "question": RunnablePassthrough()}
#     | prompt
#     | llm
#     | StrOutputParser()
# )

# Question
# print(rag_chain.invoke("Apa saja topik yang hangat dibahas 1 minggu terakhir?"))

# question = "Apa saja topik yang baru-baru ini dibahas?"
# # relevant_docs = retriever.get_relevant_documents(question)
# relevant_docs = get_vector_from_db(question)
# prompt = prompt_template.invoke({
#     # "topic" : "politik",
#     "context" : relevant_docs,
#     "question" : question
# })

# print(relevant_docs)

chat_history = []

# Set an initial system message (optional)
system_message = SystemMessage(content="""
                               Anda adalah seorang AI Assistant yang bertugas untuk melakukan analisis pada data survey.

                               Data survey terdiri dari 'Question' atau pertanyaan dan 'Answer' atau jawaban.
                               Langkah yang harus anda lakukan adalah:
                               1. Pilih dokumen dengan 'Question' yang berhubungan dengan input prompt
                               2. Jawab berdasarkan dengan prompt dengan data 'Answer' yang berhasil diambil
                               3. Tampilkan hasil dalam bentuk angka dan persentase pada setiap poin jawaban
                               """)
chat_history.append(system_message)  # Add system message to chat history1

def is_real_question(input_text):
    return "?" in input_text or len(input_text.split()) > 6

# Chat loop
while True:
    query = input("You: ")
    if query.lower() == "exit":
        break
    
    chat_history.append(HumanMessage(content=query))  # Add user message

    if is_real_question(query):
        retriever_docs = retriever.invoke(query)
        relevant_docs = '\n\n'.join(doc.page_content for doc in retriever_docs)
    else:
        relevant_docs = ""

    # relevant_docs = retriever.get_relevant_documents(query)
    # relevant_docs = get_vector_from_db(query)
    # relevant_docs = '\n\n'.join(doc.page_content for doc in relevant_docs)
    chat_history.append(HumanMessage(content=relevant_docs)) # Add relevant document

    # Get AI response using history
    result = model.invoke(chat_history)
    response = result.content
    chat_history.append(AIMessage(content=response))  # Add AI message

    print(f"AI: {response}")

